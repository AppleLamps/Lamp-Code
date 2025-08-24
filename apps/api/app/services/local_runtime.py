import subprocess
import socket
import signal
import os
import time
import hashlib
import threading
import re
import sys
import asyncio
from contextlib import closing
from typing import Optional, Dict
from app.core.config import settings


# Global process registry to track running Next.js processes
_running_processes: Dict[str, subprocess.Popen] = {}
_process_logs: Dict[str, list] = {}  # Store process logs for each project
_process_ports: Dict[str, int] = {}  # Store port information for each project

async def _monitor_preview_errors(project_id: str, process: subprocess.Popen, manager):
    """Async Preview server error monitoring"""
    error_patterns = [
        "Build Error",
        "Failed to compile",
        "Syntax Error",
        "TypeError:",
        "ReferenceError:",
        "Module not found",
        "Expected",
        "⨯",  # Next.js error symbol
        "Error:",  # Generic error
        "runtime error",
        "Runtime Error",
        "Uncaught",
        "Cannot read",
        "Cannot access",
        "is not defined",
        "is not a function",
        "Cannot resolve module",
        "Error occurred prerendering",
        "Unhandled Runtime Error",
        "GET / 500",  # HTTP 500 errors
        "POST / 500",
        "Internal server error",
        "Application error"
    ]

    success_patterns = [
        "✓ Ready in",
        "○ Compiling",
        "✓ Compiled",
        "✓ Starting"
    ]

    recent_errors = {}     # Last send time per error ID
    error_contexts = {}    # Context collection per error
    current_error = None   # Currently processing error
    error_lines = []       # Error-related lines

    def generate_error_id(error_line):
        """Generate unique ID from error line"""
        import hashlib
        # Extract core error part to generate ID
        core_error = error_line.strip()
        # Remove time and file path variations
        core_error = re.sub(r'\d{2}:\d{2}:\d{2}', '', core_error)  # Remove time
        core_error = re.sub(r'at .*?:\d+:\d+', '', core_error)     # Remove location info
        return hashlib.md5(core_error.encode()).hexdigest()[:8]

    def should_send_error(error_id):
        """Determine whether to send error (prevent duplicates within 5 seconds)"""
        now = time.time()
        if error_id in recent_errors:
            if now - recent_errors[error_id] < 5:  # Prevent duplicates within 5 seconds
                return False
        recent_errors[error_id] = now
        return True

    async def collect_error_context(line_text):
        """Collect error-related context asynchronously"""
        nonlocal current_error, error_lines

        # Store logs per project (for full log collection)
        if project_id not in _process_logs:
            _process_logs[project_id] = []

        # Remove duplicate logs (when same line comes consecutively)
        stripped_line = line_text.strip()
        if not stripped_line:  # Ignore empty lines
            return

        # Ignore if same as last log (duplicate removal)
        if _process_logs[project_id] and _process_logs[project_id][-1] == stripped_line:
            return

        _process_logs[project_id].append(stripped_line)
        # Store maximum 1000 lines only
        if len(_process_logs[project_id]) > 1000:
            _process_logs[project_id] = _process_logs[project_id][-1000:]

        # Detect success patterns - clear error state
        for pattern in success_patterns:
            if pattern in line_text:
                # Send success status
                success_message = {
                    "type": "preview_success",
                    "success": {
                        "message": line_text.strip(),
                        "timestamp": int(time.time() * 1000)
                    }
                }

                try:
                    await manager.send_message(project_id, success_message)
                except Exception as e:
                    print(f"[PreviewSuccess] WebSocket transmission failed: {e}")

                # Clear current error state
                current_error = None
                error_lines = []
                return

        # Detect new error start
        for pattern in error_patterns:
            if pattern in line_text:
                # Send previous error if exists
                if current_error and error_lines:
                    await send_error_with_context(current_error, error_lines)

                # Start new error
                current_error = generate_error_id(line_text)
                error_lines = [line_text.strip()]
                return

        # Collect lines related to current error
        if current_error and (line_text.strip() and
                              any(x in line_text.lower() for x in ['error', 'failed', 'expected', 'at ', 'module', 'cannot', 'uncaught', 'undefined', 'null'])):
            error_lines.append(line_text.strip())
            if len(error_lines) > 15:  # Runtime errors can have long stack traces, so up to 15 lines
                error_lines = error_lines[-15:]

    async def send_error_with_context(error_id, lines):
        """Send error with context asynchronously"""
        if not should_send_error(error_id):
            return

        # Compose error message and context
        main_message = lines[0] if lines else "Unknown error"
        full_context = '\n'.join(lines[:5])  # Maximum 5 lines of context

        message_data = {
            "type": "preview_error",
            "error": {
                "id": error_id,
                "message": main_message[:200],
                "context": full_context,
                "timestamp": int(time.time() * 1000)
            }
        }

        try:
            await manager.send_message(project_id, message_data)
        except Exception as e:
            print(f"[PreviewError] WebSocket transmission failed: {e}")

    # Async monitoring loop
    while process.poll() is None:
        try:
            if process.stdout:
                line = await asyncio.get_event_loop().run_in_executor(None, process.stdout.readline)
                if line:
                    line_text = line if isinstance(line, str) else line.decode('utf-8', errors='ignore')
                    await collect_error_context(line_text)

            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[PreviewError] Monitoring error: {e}")
            break

    # Send last error when process terminates
    if current_error and error_lines:
        await send_error_with_context(current_error, error_lines)

    print(f"[PreviewError] {project_id} monitoring terminated")


def _is_port_free(port: int) -> bool:
    """Check if a port is available"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def find_free_preview_port() -> int:
    """Find a free port in the preview range"""
    for port in range(settings.preview_port_start, settings.preview_port_end + 1):
        if _is_port_free(port):
            return port
    raise RuntimeError("No free preview port available")


def _should_install_dependencies(repo_path: str) -> bool:
    """
    Check if dependencies need to be installed.
    Returns True if:
    - node_modules doesn't exist
    - package.json or package-lock.json has changed since last install
    """
    node_modules_path = os.path.join(repo_path, "node_modules")
    package_json_path = os.path.join(repo_path, "package.json")
    package_lock_path = os.path.join(repo_path, "package-lock.json")
    install_hash_path = os.path.join(repo_path, ".lovable_install_hash")
    
    # If node_modules doesn't exist, definitely need to install
    if not os.path.exists(node_modules_path):
        print(f"node_modules not found, will install dependencies")
        return True
    
    # Calculate current hash of package files
    current_hash = ""
    
    # Hash package.json
    if os.path.exists(package_json_path):
        with open(package_json_path, 'rb') as f:
            current_hash += hashlib.md5(f.read()).hexdigest()
    
    # Hash package-lock.json if it exists
    if os.path.exists(package_lock_path):
        with open(package_lock_path, 'rb') as f:
            current_hash += hashlib.md5(f.read()).hexdigest()
    
    # Create final hash
    final_hash = hashlib.md5(current_hash.encode()).hexdigest()
    
    # Check if hash file exists and matches
    if os.path.exists(install_hash_path):
        with open(install_hash_path, 'r') as f:
            stored_hash = f.read().strip()
            if stored_hash == final_hash:
                print(f"Dependencies are up to date (hash: {final_hash[:8]}...)")
                return False
    
    print(f"Package files changed, will install dependencies (new hash: {final_hash[:8]}...)")
    return True


def _save_install_hash(repo_path: str) -> None:
    """Save the current hash of package files after successful install"""
    package_json_path = os.path.join(repo_path, "package.json")
    package_lock_path = os.path.join(repo_path, "package-lock.json")
    install_hash_path = os.path.join(repo_path, ".lovable_install_hash")
    
    # Calculate current hash
    current_hash = ""
    
    # Hash package.json
    if os.path.exists(package_json_path):
        with open(package_json_path, 'rb') as f:
            current_hash += hashlib.md5(f.read()).hexdigest()
    
    # Hash package-lock.json if it exists
    if os.path.exists(package_lock_path):
        with open(package_lock_path, 'rb') as f:
            current_hash += hashlib.md5(f.read()).hexdigest()
    
    # Create final hash and save
    final_hash = hashlib.md5(current_hash.encode()).hexdigest()
    
    with open(install_hash_path, 'w') as f:
        f.write(final_hash)


def _get_install_lock_path(repo_path: str) -> str:
    """Return path to the install lock file"""
    return os.path.join(repo_path, ".lovable_install.lock")


def _acquire_install_lock(repo_path: str) -> bool:
    """
    Try to acquire a lock to prevent concurrent npm installs.
    Returns True if lock acquired, False if another install is in progress.
    """
    lock_path = _get_install_lock_path(repo_path)
    try:
        # Atomic create lock file
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as f:
            f.write(f"{os.getpid()} {int(time.time())}\n")
        return True
    except FileExistsError:
        # If a lock file exists, check its age and consider it stale after a timeout
        try:
            if os.path.exists(lock_path):
                mtime = os.path.getmtime(lock_path)
                age = time.time() - mtime
                STALE_SECONDS = 600  # 10 minutes
                if age > STALE_SECONDS:
                    print(f"Install lock stale (age {int(age)}s). Removing stale lock at {lock_path} and attempting to acquire lock.")
                    try:
                        os.remove(lock_path)
                    except Exception as e:
                        print(f"Failed to remove stale lock at {lock_path}: {e}")
                        return False
                    # Try to acquire lock again after removing stale file
                    try:
                        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                        with os.fdopen(fd, "w") as f:
                            f.write(f"{os.getpid()} {int(time.time())}\n")
                        return True
                    except Exception as e:
                        print(f"Failed to acquire lock after removing stale lock: {e}")
                        return False
                else:
                    print(f"Install lock present at {lock_path}, another install may be in progress (age {int(age)}s)")
                    return False
            else:
                # Lock disappeared between check; try again
                return _acquire_install_lock(repo_path)
        except Exception as e:
            print(f"Error checking install lock at {lock_path}: {e}")
            return False
    except Exception as e:
        print(f"Failed to create install lock at {lock_path}: {e}")
        return False


def _release_install_lock(repo_path: str) -> None:
    """Release the npm install lock if present"""
    lock_path = _get_install_lock_path(repo_path)
    try:
        if os.path.exists(lock_path):
            os.remove(lock_path)
    except Exception as e:
        print(f"Failed to remove install lock at {lock_path}: {e}")


def start_preview_process(project_id: str, repo_path: str, port: Optional[int] = None) -> tuple[str, int]:
    """
    Start a Next.js development server using subprocess
    
    Args:
        project_id: Unique project identifier
        repo_path: Path to the project repository
        port: Optional port number, will auto-assign if not provided
    
    Returns:
        Tuple of (process_name, port)
    """
    # Stop existing process if any
    stop_preview_process(project_id)
    
    # Clear previous logs for this project
    if project_id in _process_logs:
        _process_logs[project_id] = []
        print(f"[PreviewError] Cleared previous logs for {project_id}")
    
    # Assign port
    port = port or find_free_preview_port()
    process_name = f"next-dev-{project_id}"
    
    # Validate repository path
    if not repo_path or not isinstance(repo_path, str):
        raise RuntimeError("Project repository path is not set. Please initialize the project first.")
    if not os.path.isdir(repo_path):
        raise RuntimeError(f"Repository path does not exist: {repo_path}")
    
    # Check if project has package.json
    package_json_path = os.path.join(repo_path, "package.json")
    if not os.path.exists(package_json_path):
        raise RuntimeError(f"No package.json found in {repo_path}")
    
    # Install dependencies and start dev server
    env = os.environ.copy()
    env.update({
        "NODE_ENV": "development",
        "NEXT_TELEMETRY_DISABLED": "1",
        "NPM_CONFIG_UPDATE_NOTIFIER": "false",
        "PORT": str(port)
    })

    # On Windows, ensure npm paths are included (same as filesystem.py)
    if os.name == "nt":
        # Common npm installation paths on Windows
        potential_paths = [
            os.path.expanduser("~\\AppData\\Roaming\\npm"),
            os.path.expanduser("~\\AppData\\Local\\npm"),
            "C:\\Program Files\\nodejs",
            "C:\\Program Files (x86)\\nodejs"
        ]

        current_path = env.get("PATH", "")
        for path in potential_paths:
            if os.path.exists(path) and path not in current_path:
                env["PATH"] = f"{path};{current_path}"
    
    try:
        # Find npm executable with enhanced environment
        import shutil
        npm_path = shutil.which("npm", path=env.get("PATH"))
        if not npm_path:
            raise RuntimeError("npm not found. Please install Node.js and ensure npm is in your PATH.")

        # Only install dependencies if needed
        if _should_install_dependencies(repo_path):
            # Prevent duplicate installs (e.g., background + preview)
            if _acquire_install_lock(repo_path):
                try:
                    print(f"Installing dependencies for project {project_id}...")
                    install_result = subprocess.run(
                        [npm_path, "install"],
                        cwd=repo_path,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=120  # 2 minutes timeout for npm install
                    )
                    
                    if install_result.returncode != 0:
                        raise RuntimeError(f"npm install failed: {install_result.stderr}")
                    
                    # Save hash after successful install
                    _save_install_hash(repo_path)
                    print(f"Dependencies installed successfully for project {project_id}")
                finally:
                    _release_install_lock(repo_path)
            else:
                print(f"Another install in progress for project {project_id}, skipping npm install")
        else:
            print(f"Dependencies already up to date for project {project_id}, skipping npm install")
        
        # Start development server
        print(f"Starting Next.js dev server for project {project_id} on port {port}...")
        # Cross-platform process group handling
        creationflags = 0
        preexec_fn = None
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            preexec_fn = os.setsid
        process = subprocess.Popen(
            [npm_path, "run", "dev", "--", "-p", str(port)],
            cwd=repo_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            preexec_fn=preexec_fn,
            creationflags=creationflags
        )
        
        # Wait a moment for the server to start
        time.sleep(2)
        
        # Check if process is still running
        if process.poll() is not None:
            stdout, _ = process.communicate()
            raise RuntimeError(f"Next.js server failed to start: {stdout}")
        
        # Start async error monitoring task
        try:
            from app.core.di_setup import get_cli_dependencies
            dependencies = get_cli_dependencies()
            manager = dependencies.websocket_manager

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_monitor_preview_errors(project_id, process, manager))
                print(f"[PreviewError] {project_id} async error monitoring task scheduled on running loop")
            except RuntimeError:
                # No running loop in this thread; start a dedicated loop in a daemon thread
                def _runner():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    new_loop.create_task(_monitor_preview_errors(project_id, process, manager))
                    new_loop.run_forever()

                t = threading.Thread(target=_runner, name=f"preview-monitor-{project_id}", daemon=True)
                t.start()
                print(f"[PreviewError] {project_id} async error monitoring loop started in background thread")
        except Exception as e:
            print(f"[PreviewError] Failed to start async monitoring: {e}")
        
        # Store process reference and port information
        _running_processes[project_id] = process
        _process_ports[project_id] = port

        print(f"Next.js dev server started for {project_id} on port {port} (PID: {process.pid})")
        return process_name, port
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("npm install timed out after 2 minutes")
    except Exception as e:
        raise RuntimeError(f"Failed to start preview process: {str(e)}")


def stop_preview_process(project_id: str, cleanup_cache: bool = False) -> None:
    """
    Stop the Next.js development server for a project
    
    Args:
        project_id: Project identifier
        cleanup_cache: Whether to cleanup npm cache (optional)
    """
    process = _running_processes.get(project_id)
    
    if process:
        try:
            # Terminate the process (cross-platform)
            if os.name == "nt":
                try:
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                except Exception:
                    process.terminate()
            else:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            
            # Wait for process to terminate gracefully
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate gracefully
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait()
                
            print(f"Stopped Next.js dev server for project {project_id} (PID: {process.pid})")
            
        except (OSError, ProcessLookupError):
            # Process already terminated
            pass
        finally:
            # Remove from registry
            del _running_processes[project_id]
            # Clear port information
            if project_id in _process_ports:
                del _process_ports[project_id]
            # Clear logs when process stops
            if project_id in _process_logs:
                del _process_logs[project_id]
                print(f"[PreviewStop] Cleared logs for {project_id}")
    
    # Optionally cleanup npm cache
    if cleanup_cache:
        try:
            repo_path = os.path.join(settings.projects_root, project_id, "repo")
            if os.path.exists(repo_path):
                subprocess.run(
                    ["npm", "cache", "clean", "--force"],
                    cwd=repo_path,
                    capture_output=True,
                    timeout=30
                )
                print(f"Cleaned npm cache for project {project_id}")
        except Exception as e:
            print(f"Failed to clean npm cache for {project_id}: {e}")


def cleanup_project_resources(project_id: str) -> None:
    """Cleanup all resources for a project"""
    stop_preview_process(project_id, cleanup_cache=True)


def preview_status(project_id: str) -> str:
    """
    Get the status of a preview process
    
    Returns:
        "running", "stopped", or "not_found"
    """
    process = _running_processes.get(project_id)
    
    if not process:
        return "not_found"
    
    # Check if process is still alive
    if process.poll() is None:
        return "running"
    else:
        # Process has terminated, remove from registry
        del _running_processes[project_id]
        if project_id in _process_ports:
            del _process_ports[project_id]
        return "stopped"


def get_preview_port(project_id: str) -> int | None:
    """
    Get the port number for a running preview server

    Returns:
        Port number if running, None otherwise
    """
    if project_id in _process_ports and preview_status(project_id) == "running":
        return _process_ports[project_id]
    return None


def get_preview_process_id(project_id: str) -> int | None:
    """
    Get the process ID for a running preview server

    Returns:
        Process ID if running, None otherwise
    """
    if project_id in _running_processes:
        process = _running_processes[project_id]
        if process.poll() is None:  # Process is still running
            return process.pid
    return None


def get_running_processes() -> Dict[str, int]:
    """Get all currently running processes with their PIDs"""
    active_processes = {}
    for project_id, process in list(_running_processes.items()):
        if process.poll() is None:
            active_processes[project_id] = process.pid
        else:
            # Clean up terminated processes
            del _running_processes[project_id]
    
    return active_processes


def get_all_preview_logs(project_id: str) -> str:
    """
    Get all stored logs from the preview process
    
    Args:
        project_id: Project identifier
    
    Returns:
        String containing all stored logs
    """
    if project_id not in _process_logs:
        return "No logs available for this project"
    
    # Additional duplicate removal: when same error blocks repeat
    logs = _process_logs[project_id]
    if not logs:
        return "No logs available for this project"

    # Remove large duplicate blocks (when same error repeats multiple times)
    unique_logs = []
    seen_blocks = set()
    current_block = []

    for line in logs:
        current_block.append(line)

        # Detect end of error block (GET requests or new start)
        if line.startswith('GET /') or line.startswith('> ') or len(current_block) > 50:
            block_str = '\n'.join(current_block)
            block_hash = hash(block_str)

            if block_hash not in seen_blocks:
                seen_blocks.add(block_hash)
                unique_logs.extend(current_block)

            current_block = []

    # Process last block
    if current_block:
        block_str = '\n'.join(current_block)
        block_hash = hash(block_str)
        if block_hash not in seen_blocks:
            unique_logs.extend(current_block)
    
    return '\n'.join(unique_logs) if unique_logs else "No unique logs available"

def get_preview_error_logs(project_id: str) -> str:
    """
    Get error logs from the preview process
    
    Args:
        project_id: Project identifier
    
    Returns:
        String containing all error logs
    """
    process = _running_processes.get(project_id)
    
    if not process:
        return "No preview process running"
    
    # Get all available output
    logs = []
    try:
        if process.stdout and hasattr(process.stdout, 'read'):
            # Read all available data
            import fcntl
            import os
            fd = process.stdout.fileno()
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    logs.append(line)
            except (IOError, OSError):
                pass  # No more data available
    except Exception as e:
        return f"Error reading logs: {str(e)}"
    
    if not logs:
        return "No error logs available"
    
    # Join all logs and return
    return ''.join(logs)

def get_preview_logs(project_id: str, lines: int = 100) -> str:
    """
    Get logs from the preview process
    
    Args:
        project_id: Project identifier
        lines: Number of lines to return
    
    Returns:
        String containing the logs
    """
    process = _running_processes.get(project_id)
    
    if not process or not process.stdout:
        return "No logs available - process not running or no output"
    
    # Read available output without blocking
    logs = []
    # Windows does not support fcntl-based non-blocking reads
    if os.name == "nt":
        return "No recent logs available"
    try:
        # Set stdout to non-blocking mode
        import fcntl
        import os
        fd = process.stdout.fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        # Read available lines
        while len(logs) < lines:
            line = process.stdout.readline()
            if not line:
                break
            logs.append(line)
        
    except (IOError, OSError):
        # No more data available
        pass
    
    return ''.join(logs[-lines:]) if logs else "No recent logs available"

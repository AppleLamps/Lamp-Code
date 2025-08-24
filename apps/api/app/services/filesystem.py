import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def init_git_repo(repo_path: str) -> None:
    """Initialize git repository, handling case where it already exists"""
    import os

    git_dir = os.path.join(repo_path, ".git")

    # If .git directory already exists (created by create-next-app), just add and commit
    if os.path.exists(git_dir):
        try:
            # Add all files and commit
            subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)
        except subprocess.CalledProcessError:
            # If commit fails (e.g., nothing to commit), that's okay
            pass
    else:
        # Initialize new git repository
        subprocess.run(["git", "init"], cwd=repo_path, check=True)
        subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)


def scaffold_nextjs_minimal(repo_path: str) -> None:
    """Create Next.js project using official create-next-app"""
    import subprocess
    import tempfile
    import shutil

    # Get parent directory to create project in
    parent_dir = Path(repo_path).parent
    project_name = Path(repo_path).name

    try:
        # Enhanced environment setup for better npm/npx detection
        env = os.environ.copy()
        env["CI"] = "true"  # Force non-interactive mode

        # On Windows, ensure npm/npx paths are included
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

        # Preflight: Ensure npx and npm are available with enhanced environment
        import shutil as _shutil
        npx_path = _shutil.which("npx", path=env.get("PATH"))
        npm_path = _shutil.which("npm", path=env.get("PATH"))

        if not npx_path:
            raise Exception(
                "npx not found. Please install Node.js (includes npm/npx) and ensure it's in your PATH. "
                "On Windows, install with winget: 'winget install OpenJS.NodeJS.LTS' or download from https://nodejs.org/."
            )
        if not npm_path:
            raise Exception(
                "npm not found. Please install Node.js (includes npm) and ensure it's in your PATH."
            )

        # Create Next.js app with TypeScript and Tailwind CSS
        cmd = [
            npx_path,  # Use full path to npx
            "create-next-app@latest",
            project_name,
            "--typescript",
            "--tailwind",
            "--eslint",
            "--app",
            "--import-alias", "@/*",
            "--use-npm",
            "--skip-install",  # We'll install dependencies later
            "--yes"            # Auto-accept all prompts
        ]

        from app.core.terminal_ui import ui
        ui.info(f"Running create-next-app with command: {' '.join(cmd)}", "Filesystem")

        # Run create-next-app in the parent directory with timeout
        result = subprocess.run(
            cmd,
            cwd=parent_dir,
            check=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=300  # 5 minute timeout
        )

        ui.success(f"Created Next.js app: {result.stdout}", "Filesystem")

        # Skip npm install for faster project creation
        # Users can run 'npm install' manually when needed
        ui.info("Skipped dependency installation for faster setup", "Filesystem")

    except subprocess.TimeoutExpired as e:
        ui.error("create-next-app timed out after 5 minutes", "Filesystem")
        raise Exception(f"Project creation timed out. This might be due to slow network or hung process.")
    except FileNotFoundError as e:
        # Binary (npx/npm) not found at runtime
        raise Exception(
            "Failed to execute create-next-app. 'npx' or 'npm' was not found. "
            "Please install Node.js LTS and ensure your terminal PATH includes npm."
        )
    except subprocess.CalledProcessError as e:
        ui.error(f"Error creating Next.js app: {e}", "Filesystem")
        ui.debug(f"stdout: {e.stdout}", "Filesystem")
        ui.debug(f"stderr: {e.stderr}", "Filesystem")

        # Provide more specific error messages
        if "EACCES" in str(e.stderr):
            error_msg = "Permission denied. Please check directory permissions."
        elif "ENOENT" in str(e.stderr):
            error_msg = "Command not found. Please ensure Node.js and npm are installed."
        elif "network" in str(e.stderr).lower():
            error_msg = "Network error. Please check your internet connection."
        else:
            error_msg = f"Failed to create Next.js project: {e.stderr or e.stdout or str(e)}"

        raise Exception(error_msg)


def scaffold_minimal_project(repo_path: str) -> None:
    """Create minimal project structure that Claude can build upon"""
    from app.core.terminal_ui import ui

    ui.info(f"Creating minimal project structure at {repo_path}", "Filesystem")

    # Ensure the directory exists
    ensure_dir(repo_path)

    # Create basic package.json
    package_json = {
        "name": Path(repo_path).name,
        "version": "1.0.0",
        "description": "Project created with Claudable",
        "main": "index.js",
        "scripts": {
            "dev": "echo 'Development server will be configured by AI'",
            "build": "echo 'Build script will be configured by AI'",
            "start": "echo 'Start script will be configured by AI'"
        },
        "keywords": [],
        "author": "",
        "license": "ISC"
    }

    package_json_path = os.path.join(repo_path, "package.json")
    with open(package_json_path, 'w', encoding='utf-8') as f:
        json.dump(package_json, f, indent=2)

    # Create basic README.md
    readme_content = f"""# {Path(repo_path).name}

This project was created with Claudable and will be configured by AI based on your requirements.

## Getting Started

The AI will set up the appropriate development environment and scripts based on your project needs.
"""

    readme_path = os.path.join(repo_path, "README.md")
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    # Create basic .gitignore
    gitignore_content = """# Dependencies
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Runtime data
pids
*.pid
*.seed
*.pid.lock

# Coverage directory used by tools like istanbul
coverage/

# nyc test coverage
.nyc_output

# Grunt intermediate storage
.grunt

# Bower dependency directory
bower_components

# node-waf configuration
.lock-wscript

# Compiled binary addons
build/Release

# Dependency directories
jspm_packages/

# Optional npm cache directory
.npm

# Optional REPL history
.node_repl_history

# Output of 'npm pack'
*.tgz

# Yarn Integrity file
.yarn-integrity

# dotenv environment variables file
.env
.env.local
.env.development.local
.env.test.local
.env.production.local

# IDE files
.vscode/
.idea/
*.swp
*.swo

# OS generated files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
"""

    gitignore_path = os.path.join(repo_path, ".gitignore")
    with open(gitignore_path, 'w', encoding='utf-8') as f:
        f.write(gitignore_content)

    ui.success(f"Created minimal project structure with package.json, README.md, and .gitignore", "Filesystem")


def write_env_file(project_dir: str, content: str) -> None:
    (Path(project_dir) / ".env").write_text(content)

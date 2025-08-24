"""
Unified CLI Manager for Multi-AI Agent Support
Supports Claude Code SDK, Cursor Agent, Qwen Code, Gemini CLI, and Codex CLI
"""
import asyncio
import json
import os
import subprocess
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Callable, Dict, Any, AsyncGenerator, List
from enum import Enum
import tempfile
import base64
from app.core.validation import InputValidator


def get_project_root() -> str:
    """Get project root directory using relative path navigation"""
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    # unified_manager.py is in: app/services/cli/
    # Navigate: cli -> services -> app -> api -> apps -> project-root
    project_root = os.path.join(current_file_dir, "..", "..", "..", "..", "..")
    return os.path.abspath(project_root)


def get_display_path(file_path: str) -> str:
    """Convert absolute path to relative display path"""
    try:
        project_root = get_project_root()
        if file_path.startswith(project_root):
            # Remove project root from path - use os.path.sep for cross-platform compatibility
            display_path = file_path.replace(project_root + os.path.sep, "")
            # Normalize path separators for display
            display_path = display_path.replace(os.path.sep + "data" + os.path.sep + "projects" + os.path.sep, "…" + os.path.sep)
            return display_path
    except Exception:
        pass
    return file_path

from app.models.messages import Message
from app.models.sessions import Session
from app.core.interfaces import CLIDependencies, WebSocketManagerProtocol, LoggerProtocol
from app.core.terminal_ui import ui

# Claude Code CLI imports
import subprocess
import json
import tempfile
import os


# Model mapping from unified names to CLI-specific names
MODEL_MAPPING = {
    "claude": {
        "opus-4.1": "claude-opus-4-1-20250805",
        "sonnet-4": "claude-sonnet-4-20250514", 
        "opus-4": "claude-opus-4-20250514",
        "haiku-3.5": "claude-3-5-haiku-20241022",
        # Handle claude-prefixed model names
        "claude-sonnet-4": "claude-sonnet-4-20250514",
        "claude-opus-4.1": "claude-opus-4-1-20250805",
        "claude-opus-4": "claude-opus-4-20250514",
        "claude-haiku-3.5": "claude-3-5-haiku-20241022",
        # Support direct full model names
        "claude-opus-4-1-20250805": "claude-opus-4-1-20250805",
        "claude-sonnet-4-20250514": "claude-sonnet-4-20250514",
        "claude-opus-4-20250514": "claude-opus-4-20250514",
        "claude-3-5-haiku-20241022": "claude-3-5-haiku-20241022"
    },
    "cursor": {
        "gpt-5": "gpt-5",
        "sonnet-4": "sonnet-4",
        "opus-4.1": "opus-4.1",
        "sonnet-4-thinking": "sonnet-4-thinking",
        # Handle mapping from unified Claude model names
        "claude-sonnet-4": "sonnet-4",
        "claude-opus-4.1": "opus-4.1",
        "claude-sonnet-4-20250514": "sonnet-4",
        "claude-opus-4-1-20250805": "opus-4.1"
    }
}


class CLIType(str, Enum):
    CLAUDE = "claude"
    CURSOR = "cursor"


class BaseCLI(ABC):
    """Abstract base class for all CLI implementations"""

    def __init__(self, cli_type: CLIType, dependencies: Optional[CLIDependencies] = None):
        self.cli_type = cli_type
        self.dependencies = dependencies

        # Fallback to direct imports if no dependencies provided (for backward compatibility)
        if dependencies is None:
            from app.core.websocket.manager import manager as ws_manager
            from app.core.interfaces import CLIDependencies
            self.dependencies = CLIDependencies(websocket_manager=ws_manager, logger=ui)
    
    def _get_cli_model_name(self, model: Optional[str]) -> Optional[str]:
        """Convert unified model name to CLI-specific model name"""
        if not model:
            return None
        
        from app.core.terminal_ui import ui
        
        ui.debug(f"Input model: '{model}' for CLI: {self.cli_type.value}", "Model")
        cli_models = MODEL_MAPPING.get(self.cli_type.value, {})
        
        # Try exact match first
        if model in cli_models:
            mapped_model = cli_models[model]
            ui.info(f"Mapped '{model}' to '{mapped_model}' for {self.cli_type.value}", "Model")
            return mapped_model
        
        # Try direct model name (already CLI-specific)
        if model in cli_models.values():
            ui.info(f"Using direct model name '{model}' for {self.cli_type.value}", "Model")
            return model
        
        # For debugging: show available models
        available_models = list(cli_models.keys())
        ui.warning(f"Model '{model}' not found in mapping for {self.cli_type.value}", "Model")
        ui.debug(f"Available models for {self.cli_type.value}: {available_models}", "Model")
        ui.warning(f"Using model as-is: '{model}'", "Model")
        return model
    
    def get_supported_models(self) -> List[str]:
        """Get list of supported models for this CLI"""
        cli_models = MODEL_MAPPING.get(self.cli_type.value, {})
        return list(cli_models.keys()) + list(cli_models.values())

    @property
    def websocket_manager(self) -> WebSocketManagerProtocol:
        """Get WebSocket manager from dependencies"""
        return self.dependencies.websocket_manager

    @property
    def logger(self) -> LoggerProtocol:
        """Get logger from dependencies"""
        return self.dependencies.logger or ui
    
    def is_model_supported(self, model: str) -> bool:
        """Check if a model is supported by this CLI"""
        return model in self.get_supported_models() or model in MODEL_MAPPING.get(self.cli_type.value, {}).values()
    
    @abstractmethod
    async def check_availability(self) -> Dict[str, Any]:
        """Check if CLI is available and configured"""
        pass
    
    @abstractmethod
    async def execute_with_streaming(
        self,
        instruction: str,
        project_path: str,
        session_id: Optional[str] = None,
        log_callback: Optional[Callable] = None,
        images: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        is_initial_prompt: bool = False
    ) -> AsyncGenerator[Message, None]:
        """Execute instruction and yield messages in real-time"""
        pass
    
    @abstractmethod
    async def get_session_id(self, project_id: str) -> Optional[str]:
        """Get current session ID for project"""
        pass
    
    @abstractmethod
    async def set_session_id(self, project_id: str, session_id: str) -> None:
        """Set session ID for project"""
        pass
    
    
    def parse_message_data(self, data: Dict[str, Any], project_id: str, session_id: str) -> Message:
        """Parse CLI-specific message data to unified Message format"""
        return Message(
            id=str(uuid.uuid4()),
            project_id=project_id,
            role=self._normalize_role(data.get("role", "assistant")),
            message_type="chat",
            content=self._extract_content(data),
            metadata_json={
                **data,
                "cli_type": self.cli_type.value,
                "original_format": data
            },
            session_id=session_id,
            created_at=datetime.now(timezone.utc)
        )
    
    def _normalize_role(self, role: str) -> str:
        """Normalize different CLI role formats"""
        role_mapping = {
            "model": "assistant",
            "ai": "assistant", 
            "human": "user",
            "bot": "assistant"
        }
        return role_mapping.get(role.lower(), role.lower())
    
    def _extract_content(self, data: Dict[str, Any]) -> str:
        """Extract content from CLI-specific data format"""
        
        # Handle Claude's complex content array structure
        if "content" in data and isinstance(data["content"], list):
            content = ""
            for item in data["content"]:
                if item.get("type") == "text":
                    content += item.get("text", "")
                elif item.get("type") == "tool_use":
                    tool_name = item.get("name", "Unknown")
                    tool_input = item.get("input", {})
                    
                    # Create simplified tool use summary
                    summary = self._create_tool_summary(tool_name, tool_input)
                    content += f"{summary}\n"
            return content
        
        # Handle simple content string
        elif "content" in data:
            return str(data["content"])
        
        # Handle Gemini parts format
        elif "parts" in data:
            content = ""
            for part in data["parts"]:
                if "text" in part:
                    content += part.get("text", "")
                elif "functionCall" in part:
                    func_call = part["functionCall"]
                    tool_name = func_call.get('name', 'Unknown')
                    tool_input = func_call.get("args", {})
                    summary = self._create_tool_summary(tool_name, tool_input)
                    content += f"{summary}\n"
            return content
        
        # Handle OpenAI/Codex format with choices
        elif "choices" in data and data["choices"]:
            choice = data["choices"][0]
            if "message" in choice:
                return choice["message"].get("content", "")
            elif "text" in choice:
                return choice.get("text", "")
        
        # Handle direct text fields
        elif "text" in data:
            return str(data["text"])
        elif "message" in data:
            # Handle nested message structure
            if isinstance(data["message"], dict):
                return self._extract_content(data["message"])
            return str(data["message"])
        
        # Handle response field (common in many APIs)
        elif "response" in data:
            return str(data["response"])
        
        # Handle delta streaming format
        elif "delta" in data and "content" in data["delta"]:
            return str(data["delta"]["content"])
        
        # Fallback: convert entire data to string
        else:
            return str(data)
    
    def _normalize_tool_name(self, tool_name: str) -> str:
        """Normalize different CLI tool names to unified format"""
        tool_mapping = {
            # File operations
            "read_file": "Read", "read": "Read",
            "write_file": "Write", "write": "Write",
            "edit_file": "Edit",
            "replace": "Edit", "edit": "Edit",
            "delete": "Delete",

            # Terminal operations
            "shell": "Bash",
            "run_terminal_command": "Bash",

            # Search operations
            "search_file_content": "Grep",
            "codebase_search": "Grep", "grep": "Grep",
            "find_files": "Glob", "glob": "Glob",
            "list_directory": "LS",
            "list_dir": "LS", "ls": "LS",
            "semSearch": "SemSearch",

            # Web operations
            "google_web_search": "WebSearch",
            "web_search": "WebSearch",
            "web_fetch": "WebFetch",

            # Task/Memory operations
            "save_memory": "SaveMemory",
        }

        return tool_mapping.get(tool_name, tool_name)

    def _get_clean_tool_display(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Create a clean tool display like Claude Code"""
        normalized_name = self._normalize_tool_name(tool_name)
        
        if normalized_name == "Read":
            file_path = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("file", "")
            if file_path:
                filename = file_path.split("/")[-1]
                return f"Reading {filename}"
            return "Reading file"
        elif normalized_name == "Write":
            file_path = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("file", "")
            if file_path:
                filename = file_path.split("/")[-1]
                return f"Writing {filename}"
            return "Writing file"
        elif normalized_name == "Edit":
            file_path = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("file", "")
            if file_path:
                filename = file_path.split("/")[-1]
                return f"Editing {filename}"
            return "Editing file"
        elif normalized_name == "Bash":
            command = tool_input.get("command") or tool_input.get("cmd") or tool_input.get("script", "")
            if command:
                cmd_display = command.split()[0] if command.split() else command
                return f"Running {cmd_display}"
            return "Running command"
        elif normalized_name == "LS":
            return "Listing directory"
        elif normalized_name == "TodoWrite":
            return "Planning next steps"
        elif normalized_name == "WebSearch":
            query = tool_input.get("query", "")
            if query:
                return f"Searching: {query[:50]}..."
            return "Web search"
        elif normalized_name == "WebFetch":
            url = tool_input.get("url", "")
            if url:
                domain = url.split("//")[-1].split("/")[0] if "//" in url else url.split("/")[0]
                return f"Fetching from {domain}"
            return "Fetching web content"
        else:
            return f"Using {tool_name}"

    def _create_tool_summary(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Create a visual markdown summary for tool usage"""
        # Normalize the tool name first
        normalized_name = self._normalize_tool_name(tool_name)
        
        if normalized_name == "Edit":
            # Handle different argument names from different CLIs
            file_path = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("file", "")
            if file_path:
                display_path = get_display_path(file_path)
                if len(display_path) > 40:
                    display_path = "…/" + "/".join(display_path.split("/")[-2:])
                return f"**Edit** `{display_path}`"
            return "**Edit** `file`"
        elif normalized_name == "Read":
            # Handle different argument names from different CLIs
            file_path = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("file", "")
            if file_path:
                display_path = get_display_path(file_path)
                if len(display_path) > 40:
                    display_path = "…/" + "/".join(display_path.split("/")[-2:])
                return f"**Read** `{display_path}`"
            return "**Read** `file`"
        elif normalized_name == "Bash":
            # Handle different command argument names
            command = tool_input.get("command") or tool_input.get("cmd") or tool_input.get("script", "")
            if command:
                display_cmd = command[:40] + "..." if len(command) > 40 else command
                return f"**Bash** `{display_cmd}`"
            return "**Bash** `command`"
        elif normalized_name == "TodoWrite":
            return "`Planning for next moves...`"
        elif normalized_name == "SaveMemory":
            # Handle save_memory from Gemini CLI
            fact = tool_input.get("fact", "")
            if fact:
                return f"**SaveMemory** `{fact[:40]}{'...' if len(fact) > 40 else ''}`"
            return "**SaveMemory** `storing information`"
        elif normalized_name == "Grep":
            # Handle different search tool arguments
            pattern = tool_input.get("pattern") or tool_input.get("query") or tool_input.get("search", "")
            path = tool_input.get("path") or tool_input.get("file") or tool_input.get("directory", "")
            if pattern:
                if path:
                    display_path = get_display_path(path)
                    return f"**Search** `{pattern}` in `{display_path}`"
                return f"**Search** `{pattern}`"
            return "**Search** `pattern`"
        elif normalized_name == "Glob":
            # Handle find_files from Cursor Agent
            if tool_name == "find_files":
                name = tool_input.get("name", "")
                if name:
                    return f"**Glob** `{name}`"
                return "**Glob** `finding files`"
            pattern = tool_input.get("pattern", "") or tool_input.get("globPattern", "")
            if pattern:
                return f"**Glob** `{pattern}`"
            return "**Glob** `pattern`"
        elif normalized_name == "Write":
            # Handle different argument names from different CLIs
            file_path = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("file", "")
            if file_path:
                display_path = get_display_path(file_path)
                if len(display_path) > 40:
                    display_path = "…/" + "/".join(display_path.split("/")[-2:])
                return f"**Write** `{display_path}`"
            return "**Write** `file`"
        elif normalized_name == "MultiEdit":
            # Handle different argument names from different CLIs
            file_path = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("file", "")
            if file_path:
                display_path = get_display_path(file_path)
                if len(display_path) > 40:
                    display_path = "…/" + "/".join(display_path.split("/")[-2:])
                return f"🔧 **MultiEdit** `{display_path}`"
            return "🔧 **MultiEdit** `file`"
        elif normalized_name == "LS":
            # Handle list_dir from Cursor Agent and list_directory from Gemini
            path = tool_input.get("path") or tool_input.get("directory") or tool_input.get("dir", "")
            if path:
                display_path = get_display_path(path)
                if len(display_path) > 40:
                    display_path = "…/" + display_path[-37:]
                return f"📁 **LS** `{display_path}`"
            return "📁 **LS** `directory`"
        elif normalized_name == "Delete":
            file_path = tool_input.get("path", "")
            if file_path:
                display_path = get_display_path(file_path)
                if len(display_path) > 40:
                    display_path = "…/" + "/".join(display_path.split("/")[-2:])
                return f"**Delete** `{display_path}`"
            return "**Delete** `file`"
        elif normalized_name == "SemSearch":
            query = tool_input.get("query", "")
            if query:
                short_query = query[:40] + "..." if len(query) > 40 else query
                return f"**SemSearch** `{short_query}`"
            return "**SemSearch** `query`"
        elif normalized_name == "WebFetch":
            # Handle web_fetch from Gemini CLI
            url = tool_input.get("url", "")
            prompt = tool_input.get("prompt", "")
            if url and prompt:
                domain = url.split("//")[-1].split("/")[0] if "//" in url else url.split("/")[0]
                short_prompt = prompt[:30] + "..." if len(prompt) > 30 else prompt
                return f"**WebFetch** [{domain}]({url})\n> {short_prompt}"
            elif url:
                domain = url.split("//")[-1].split("/")[0] if "//" in url else url.split("/")[0]
                return f"**WebFetch** [{domain}]({url})"
            return "**WebFetch** `url`"
        elif normalized_name == "WebSearch":
            # Handle google_web_search from Gemini CLI and web_search from Cursor Agent
            query = tool_input.get("query") or tool_input.get("search_query", "")
            query = tool_input.get("query", "")
            if query:
                short_query = query[:40] + "..." if len(query) > 40 else query
                return f"**WebSearch** `{short_query}`"
            return "**WebSearch** `query`"
        elif normalized_name == "Task":
            # Handle Task tool from Claude Code
            description = tool_input.get("description", "")
            subagent_type = tool_input.get("subagent_type", "")
            if description and subagent_type:
                return f"🤖 **Task** `{subagent_type}`\n> {description[:50]}{'...' if len(description) > 50 else ''}"
            elif description:
                return f"🤖 **Task** `{description[:40]}{'...' if len(description) > 40 else ''}`"
            return "🤖 **Task** `subtask`"
        elif normalized_name == "ExitPlanMode":
            # Handle ExitPlanMode from Claude Code
            return "✅ **ExitPlanMode** `planning complete`"
        elif normalized_name == "NotebookEdit":
            # Handle NotebookEdit from Claude Code
            notebook_path = tool_input.get("notebook_path", "")
            if notebook_path:
                filename = notebook_path.split("/")[-1]
                return f"📓 **NotebookEdit** `{filename}`"
            return "📓 **NotebookEdit** `notebook`"
        else:
            return f"**{tool_name}** `executing...`"


class ClaudeCodeCLI(BaseCLI):
    """Claude Code Python SDK implementation"""

    def __init__(self, dependencies: Optional[CLIDependencies] = None):
        super().__init__(CLIType.CLAUDE, dependencies)
        self.session_mapping: Dict[str, str] = {}
    
    async def check_availability(self) -> Dict[str, Any]:
        """Check if Claude Code CLI is available"""
        try:
            # First try to check if claude CLI is installed and working
            import platform
            if platform.system() == "Windows":
                # On Windows, use shell execution to handle PowerShell scripts
                result = await asyncio.create_subprocess_shell(
                    "claude -h",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            else:
                # On Unix systems, try exec first
                result = await asyncio.create_subprocess_exec(
                    "claude", "-h",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                return {
                    "available": False,
                    "configured": False,
                    "error": "Claude Code CLI not installed or not working.\n\nTo install:\n1. Install Claude Code: npm install -g @anthropic-ai/claude-code\n2. Login to Claude: claude login\n3. Try running your prompt again"
                }
            
            # Check if help output contains expected content
            help_output = stdout.decode() + stderr.decode()
            if "claude" not in help_output.lower():
                return {
                    "available": False,
                    "configured": False,
                    "error": "Claude Code CLI not responding correctly.\n\nPlease try:\n1. Reinstall: npm install -g @anthropic-ai/claude-code\n2. Login: claude login\n3. Check installation: claude -h"
                }
            
            return {
                "available": True,
                "configured": True,
                "mode": "CLI",
                "models": self.get_supported_models(),
                "default_models": ["claude-sonnet-4-20250514", "claude-opus-4-1-20250805"]
            }
        except Exception as e:
            return {
                "available": False,
                "configured": False,
                "error": f"Failed to check Claude Code CLI: {str(e)}\n\nTo install:\n1. Install Claude Code: npm install -g @anthropic-ai/claude-code\n2. Login to Claude: claude login"
            }
    
    async def execute_with_streaming(
        self,
        instruction: str,
        project_path: str,
        session_id: Optional[str] = None,
        log_callback: Optional[Callable] = None,
        images: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        is_initial_prompt: bool = False
    ) -> AsyncGenerator[Message, None]:
        """Execute instruction using Claude Code CLI directly"""
        from app.core.terminal_ui import ui

        ui.info("Starting Claude Code CLI execution", "Claude CLI")
        ui.debug(f"Instruction: {instruction[:100]}...", "Claude CLI")
        ui.debug(f"Project path: {project_path}", "Claude CLI")
        ui.debug(f"Session ID: {session_id}", "Claude CLI")
        
        if log_callback:
            await log_callback("Starting execution...")
        
        # Load system prompt
        try:
            from app.services.claude_act import get_system_prompt
            system_prompt = get_system_prompt()
            ui.debug(f"System prompt loaded: {len(system_prompt)} chars", "Claude SDK")
        except Exception as e:
            ui.error(f"Failed to load system prompt: {e}", "Claude SDK")
            system_prompt = "You are Claude Code, an AI coding assistant specialized in building modern web applications."
        
        # Get CLI-specific model name
        cli_model = self._get_cli_model_name(model) or "claude-sonnet-4-20250514"
        
        # Add project directory structure for initial prompts
        if is_initial_prompt:
            project_structure_info = """
<initial_context>
## Project Directory Structure (node_modules are already installed)
.eslintrc.json
.gitignore
next.config.mjs
next-env.d.ts
package.json
postcss.config.mjs
README.md
tailwind.config.ts
tsconfig.json
.env
src/app/favicon.ico
src/app/globals.css
src/app/layout.tsx
src/app/page.tsx
public/
node_modules/
</initial_context>"""
            instruction = instruction + project_structure_info
            ui.info(f"Added project structure info to initial prompt", "Claude SDK")
        
        ui.info(f"Using model: {cli_model}", "Claude CLI")
        ui.debug(f"Project path: {project_path}", "Claude CLI")
        ui.debug(f"Instruction: {instruction[:100]}...", "Claude CLI")
        
        try:
            # Validate project path before changing directory
            if not project_path:
                raise ValueError("Project path is None or empty. Project may not have been created successfully.")

            if not os.path.exists(project_path):
                raise ValueError(f"Project path does not exist: {project_path}")

            # Change to project directory
            original_cwd = os.getcwd()
            os.chdir(project_path)

            ui.info("Executing Claude Code CLI directly", "Claude CLI")

            # Create a temporary file for the instruction
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(instruction)
                instruction_file = f.name
            
            try:
                # Validate inputs before execution
                validated_model = InputValidator.validate_model_name(cli_model)
                validated_message = InputValidator.validate_message_content(instruction)

                # Execute Claude Code CLI directly
                cmd = [
                    "claude",
                    "--model", validated_model,
                    "-p", validated_message
                ]

                # Validate the entire command
                cmd = InputValidator.validate_cli_command(cmd)

                ui.info(f"Running command: {' '.join(cmd[:3])} [prompt]", "Claude CLI")

                # Run the command and capture output
                # Use shell=True on Windows to handle PowerShell scripts
                import platform
                if platform.system() == "Windows":
                    # On Windows, use shell execution to handle .ps1 scripts
                    cmd_str = " ".join([f'"{arg}"' if " " in arg else arg for arg in cmd])
                    process = await asyncio.create_subprocess_shell(
                        cmd_str,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=project_path
                    )
                else:
                    # On Unix systems, use exec
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=project_path
                    )

                # Send initial message
                init_message = Message(
                    id=str(uuid.uuid4()),
                    project_id=project_path,
                    role="system",
                    message_type="system",
                    content=f"Claude Code CLI started (Model: {cli_model})",
                    metadata_json={
                        "cli_type": self.cli_type.value,
                        "mode": "CLI",
                        "model": cli_model,
                        "hidden_from_ui": True
                    },
                    session_id=session_id,
                    created_at=datetime.now(timezone.utc)
                )
                yield init_message

                # Wait for completion and get output
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    # Success - yield the output
                    output = stdout.decode('utf-8', errors='ignore')
                    if output.strip():
                        response_message = Message(
                            id=str(uuid.uuid4()),
                            project_id=project_path,
                            role="assistant",
                            message_type="chat",
                            content=output.strip(),
                            metadata_json={
                                "cli_type": self.cli_type.value,
                                "mode": "CLI"
                            },
                            session_id=session_id,
                            created_at=datetime.now(timezone.utc)
                        )
                        yield response_message
                else:
                    # Error - yield error message
                    error_output = stderr.decode('utf-8', errors='ignore')
                    error_message = Message(
                        id=str(uuid.uuid4()),
                        project_id=project_path,
                        role="system",
                        message_type="error",
                        content=f"Claude CLI error: {error_output}",
                        metadata_json={
                            "cli_type": self.cli_type.value,
                            "mode": "CLI",
                            "error_code": process.returncode
                        },
                        session_id=session_id,
                        created_at=datetime.now(timezone.utc)
                    )
                    yield error_message

                # Clean up temporary file
                try:
                    os.unlink(instruction_file)
                except:
                    pass

            finally:
                # Restore original working directory
                os.chdir(original_cwd)

        except Exception as e:
            ui.error(f"Exception occurred: {str(e)}", "Claude CLI")
            if log_callback:
                await log_callback(f"Claude CLI Exception: {str(e)}")
            raise
    
    
    async def get_session_id(self, project_id: str) -> Optional[str]:
        """Get current session ID for project from database"""
        try:
            # Try to get from database if available (we'll need to pass db session)
            return self.session_mapping.get(project_id)
        except Exception as e:
            ui.warning(f"Failed to get session ID from DB: {e}", "Claude SDK")
            return self.session_mapping.get(project_id)
    
    async def set_session_id(self, project_id: str, session_id: str) -> None:
        """Set session ID for project in database and memory"""
        try:
            # Store in memory as fallback
            self.session_mapping[project_id] = session_id
            ui.debug(f"Session ID stored for project {project_id}", "Claude SDK")
        except Exception as e:
            ui.warning(f"Failed to save session ID: {e}", "Claude SDK")
            # Fallback to memory storage
            self.session_mapping[project_id] = session_id


class CursorAgentCLI(BaseCLI):
    """Cursor Agent CLI implementation with stream-json support and session continuity"""

    def __init__(self, db_session=None, dependencies: Optional[CLIDependencies] = None):
        super().__init__(CLIType.CURSOR, dependencies)
        self.db_session = db_session
        self._session_store = {}  # Fallback for when db_session is not available
    
    async def check_availability(self) -> Dict[str, Any]:
        """Check if Cursor Agent CLI is available"""
        try:
            # Check if cursor-agent is installed and working
            result = await asyncio.create_subprocess_shell(
                "cursor-agent -h",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                return {
                    "available": False,
                    "configured": False,
                    "error": "Cursor Agent CLI not installed or not working.\n\nTo install:\n1. Install Cursor: curl https://cursor.com/install -fsS | bash\n2. Login to Cursor: cursor-agent login\n3. Try running your prompt again"
                }
            
            # Check if help output contains expected content
            help_output = stdout.decode() + stderr.decode()
            if "cursor-agent" not in help_output.lower():
                return {
                    "available": False,
                    "configured": False,
                    "error": "Cursor Agent CLI not responding correctly.\n\nPlease try:\n1. Reinstall: curl https://cursor.com/install -fsS | bash\n2. Login: cursor-agent login\n3. Check installation: cursor-agent -h"
                }
            
            return {
                "available": True,
                "configured": True,
                "models": self.get_supported_models(),
                "default_models": ["gpt-5", "sonnet-4"]
            }
        except Exception as e:
            return {
                "available": False,
                "configured": False,
                "error": f"Failed to check Cursor Agent: {str(e)}\n\nTo install:\n1. Install Cursor: curl https://cursor.com/install -fsS | bash\n2. Login to Cursor: cursor-agent login"
            }
    
    def _handle_cursor_stream_json(self, event: Dict[str, Any], project_path: str, session_id: str) -> Optional[Message]:
        """Handle Cursor stream-json format (NDJSON events) to be compatible with Claude Code CLI output"""
        event_type = event.get("type")

        if event_type == "system":
            # System initialization event
            return Message(
                id=str(uuid.uuid4()),
                project_id=project_path,
                role="system",
                message_type="system",
                content=f"🔧 Cursor Agent initialized (Model: {event.get('model', 'unknown')})",
                metadata_json={
                    "cli_type": self.cli_type.value,
                    "event_type": "system",
                    "cwd": event.get("cwd"),
                    "api_key_source": event.get("apiKeySource"),
                    "original_event": event,
                    "hidden_from_ui": True  # Hide system init messages
                },
                session_id=session_id,
                created_at=datetime.now(timezone.utc)
            )

        elif event_type == "user":
            # Cursor echoes back the user's prompt. Suppress it to avoid duplicates.
            return None

        elif event_type == "assistant":
            # Assistant response event (text delta)
            message_content = event.get("message", {}).get("content", [])
            content = ""

            if message_content and isinstance(message_content, list):
                for part in message_content:
                    if part.get("type") == "text":
                        content += part.get("text", "")

            if content:
                return Message(
                    id=str(uuid.uuid4()),
                    project_id=project_path,
                    role="assistant",
                    message_type="chat",
                    content=content,
                    metadata_json={
                        "cli_type": self.cli_type.value,
                        "event_type": "assistant",
                        "original_event": event
                    },
                    session_id=session_id,
                    created_at=datetime.now(timezone.utc)
                )

        elif event_type == "tool_call":
            subtype = event.get("subtype")
            tool_call_data = event.get("tool_call", {})
            if not tool_call_data:
                return None

            tool_name_raw = next(iter(tool_call_data), None)
            if not tool_name_raw:
                return None

            # Normalize tool name: lsToolCall -> ls
            tool_name = tool_name_raw.replace("ToolCall", "")

            if subtype == "started":
                tool_input = tool_call_data[tool_name_raw].get("args", {})
                summary = self._create_tool_summary(tool_name, tool_input)

                return Message(
                    id=str(uuid.uuid4()),
                    project_id=project_path,
                    role="assistant",
                    message_type="chat",
                    content=summary,
                    metadata_json={
                        "cli_type": self.cli_type.value,
                        "event_type": "tool_call_started",
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "original_event": event
                    },
                    session_id=session_id,
                    created_at=datetime.now(timezone.utc)
                )

            elif subtype == "completed":
                result = tool_call_data[tool_name_raw].get("result", {})
                content = ""
                if "success" in result:
                    content = json.dumps(result["success"])
                elif "error" in result:
                    content = json.dumps(result["error"])

                return Message(
                    id=str(uuid.uuid4()),
                    project_id=project_path,
                    role="system",
                    message_type="tool_result",
                    content=content,
                    metadata_json={
                        "cli_type": self.cli_type.value,
                        "original_format": event,
                        "tool_name": tool_name,
                        "hidden_from_ui": True
                    },
                    session_id=session_id,
                    created_at=datetime.now(timezone.utc)
                )

        elif event_type == "result":
            # Final result event
            duration = event.get("duration_ms", 0)
            result_text = event.get("result", "")

            if result_text:
                return Message(
                    id=str(uuid.uuid4()),
                    project_id=project_path,
                    role="system",
                    message_type="system",
                    content=f"Execution completed in {duration}ms. Final result: {result_text}",
                    metadata_json={
                        "cli_type": self.cli_type.value,
                        "event_type": "result",
                        "duration_ms": duration,
                        "original_event": event,
                        "hidden_from_ui": True
                    },
                    session_id=session_id,
                    created_at=datetime.now(timezone.utc)
                )

        return None
    
    async def _ensure_agent_md(self, project_path: str) -> None:
        """Ensure AGENT.md exists in project repo with system prompt"""
        # Determine the repo path
        project_repo_path = os.path.join(project_path, "repo")
        if not os.path.exists(project_repo_path):
            project_repo_path = project_path
        
        agent_md_path = os.path.join(project_repo_path, "AGENT.md")
        
        # Check if AGENT.md already exists
        if os.path.exists(agent_md_path):
            print(f"📝 [Cursor] AGENT.md already exists at: {agent_md_path}")
            return
        
        try:
            # Read system prompt from the source file using relative path
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            # unified_manager.py is in: app/services/cli/
            # Navigate: cli -> services -> app
            app_dir = os.path.join(current_file_dir, "..", "..")
            app_dir = os.path.abspath(app_dir)
            system_prompt_path = os.path.join(app_dir, "prompt", "system-prompt.md")
            
            if os.path.exists(system_prompt_path):
                with open(system_prompt_path, 'r', encoding='utf-8') as f:
                    system_prompt_content = f.read()
                
                # Write to AGENT.md in the project repo
                with open(agent_md_path, 'w', encoding='utf-8') as f:
                    f.write(system_prompt_content)
                
                print(f"📝 [Cursor] Created AGENT.md at: {agent_md_path}")
            else:
                print(f"⚠️ [Cursor] System prompt file not found at: {system_prompt_path}")
        except Exception as e:
            print(f"❌ [Cursor] Failed to create AGENT.md: {e}")

    async def execute_with_streaming(
        self,
        instruction: str,
        project_path: str,
        session_id: Optional[str] = None,
        log_callback: Optional[Callable] = None,
        images: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        is_initial_prompt: bool = False
    ) -> AsyncGenerator[Message, None]:
        """Execute Cursor Agent CLI with stream-json format and session continuity"""
        # Ensure AGENT.md exists for system prompt
        await self._ensure_agent_md(project_path)
        
        # Extract project ID from path (format: .../projects/{project_id}/repo)
        # We need the project_id, not "repo"
        path_parts = project_path.split("/")
        if "repo" in path_parts and len(path_parts) >= 2:
            # Get the folder before "repo"
            repo_index = path_parts.index("repo")
            if repo_index > 0:
                project_id = path_parts[repo_index - 1]
            else:
                project_id = path_parts[-1] if path_parts else project_path
        else:
            project_id = path_parts[-1] if path_parts else project_path
        
        stored_session_id = await self.get_session_id(project_id)
        
        
        # Validate inputs before building command
        validated_instruction = InputValidator.validate_message_content(instruction)

        cmd = [
            "cursor-agent", "--force",
            "-p", validated_instruction,
            "--output-format", "stream-json"  # Use stream-json format
        ]

        # Add session resume if available (prefer stored session over parameter)
        active_session_id = stored_session_id or session_id
        if active_session_id:
            # Validate session ID format
            validated_session_id = InputValidator.sanitize_cli_argument(active_session_id)
            cmd.extend(["--resume", validated_session_id])
            print(f"🔗 [Cursor] Resuming session: {validated_session_id}")

        # Add API key if available
        cursor_api_key = os.getenv("CURSOR_API_KEY")
        if cursor_api_key:
            validated_api_key = InputValidator.sanitize_cli_argument(cursor_api_key)
            cmd.extend(["--api-key", validated_api_key])

        # Add model - prioritize parameter over environment variable
        cli_model = self._get_cli_model_name(model) or os.getenv("CURSOR_MODEL")
        if cli_model:
            validated_model = InputValidator.validate_model_name(cli_model)
            cmd.extend(["-m", validated_model])
            print(f"🔧 [Cursor] Using model: {validated_model}")

        # Validate the entire command
        cmd = InputValidator.validate_cli_command(cmd)
        
        project_repo_path = os.path.join(project_path, "repo")
        if not os.path.exists(project_repo_path):
            project_repo_path = project_path # Fallback to project_path if repo subdir doesn't exist

        try:
            # Use platform-specific process execution for Windows compatibility
            import platform
            if platform.system() == "Windows":
                # On Windows, use shell execution to handle scripts
                cmd_str = " ".join([f'"{arg}"' if " " in arg else arg for arg in cmd])
                process = await asyncio.create_subprocess_shell(
                    cmd_str,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=project_repo_path
                )
            else:
                # On Unix systems, use exec
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=project_repo_path
                )
            
            cursor_session_id = None
            assistant_message_buffer = ""
            result_received = False  # Track if we received result event
            
            async for line in process.stdout:
                line_str = line.decode().strip()
                if not line_str:
                    continue
                    
                try:
                    # Parse NDJSON event
                    event = json.loads(line_str)
                    
                    event_type = event.get("type")
                    
                    # Priority: Extract session ID from type: "result" event (most reliable)
                    if event_type == "result" and not cursor_session_id:
                        print(f"🔍 [Cursor] Result event received: {event}")
                        session_id_from_result = event.get("session_id")
                        if session_id_from_result:
                            cursor_session_id = session_id_from_result
                            await self.set_session_id(project_id, cursor_session_id)
                            print(f"💾 [Cursor] Session ID extracted from result event: {cursor_session_id}")
                        
                        # Mark that we received result event
                        result_received = True
                    
                    # Extract session ID from various event types
                    if not cursor_session_id:
                        # Try to extract session ID from any event that contains it
                        potential_session_id = (
                            event.get("sessionId") or 
                            event.get("chatId") or 
                            event.get("session_id") or 
                            event.get("chat_id") or
                            event.get("threadId") or
                            event.get("thread_id")
                        )
                        
                        # Also check in nested structures
                        if not potential_session_id and isinstance(event.get("message"), dict):
                            potential_session_id = (
                                event["message"].get("sessionId") or
                                event["message"].get("chatId") or
                                event["message"].get("session_id") or
                                event["message"].get("chat_id")
                            )
                        
                        if potential_session_id and potential_session_id != active_session_id:
                            cursor_session_id = potential_session_id
                            await self.set_session_id(project_id, cursor_session_id)
                            print(f"💾 [Cursor] Updated session ID for project {project_id}: {cursor_session_id}")
                            print(f"   Previous: {active_session_id}")
                            print(f"   New: {cursor_session_id}")
                    
                    # If we receive a non-assistant message, flush the buffer first
                    if event.get("type") != "assistant" and assistant_message_buffer:
                        yield Message(
                            id=str(uuid.uuid4()),
                            project_id=project_path,
                            role="assistant",
                            message_type="chat",
                            content=assistant_message_buffer,
                            metadata_json={"cli_type": "cursor", "event_type": "assistant_aggregated"},
                            session_id=session_id,
                            created_at=datetime.now(timezone.utc)
                        )
                        assistant_message_buffer = ""

                    # Process the event
                    message = self._handle_cursor_stream_json(event, project_path, session_id)
                    
                    if message:
                        if message.role == "assistant" and message.message_type == "chat":
                            assistant_message_buffer += message.content
                        else:
                            if log_callback:
                                await log_callback(f"📝 [Cursor] {message.content}")
                            yield message
                    
                    # ★ CRITICAL: Break after result event to end streaming
                    if result_received:
                        print(f"🏁 [Cursor] Result event received, terminating stream early")
                        try:
                            process.terminate()
                            print(f"🔪 [Cursor] Process terminated")
                        except Exception as e:
                            print(f"⚠️ [Cursor] Failed to terminate process: {e}")
                        break
                    
                except json.JSONDecodeError as e:
                    # Handle malformed JSON
                    print(f"⚠️ [Cursor] JSON decode error: {e}")
                    print(f"⚠️ [Cursor] Raw line: {line_str}")
                    
                    # Still yield as raw output
                    message = Message(
                        id=str(uuid.uuid4()),
                        project_id=project_path,
                        role="assistant",
                        message_type="chat",
                        content=line_str,
                        metadata_json={"cli_type": "cursor", "raw_output": line_str, "parse_error": str(e)},
                        session_id=session_id,
                        created_at=datetime.now(timezone.utc)
                    )
                    yield message
            
            # Flush any remaining content in the buffer
            if assistant_message_buffer:
                yield Message(
                    id=str(uuid.uuid4()),
                    project_id=project_path,
                    role="assistant",
                    message_type="chat",
                    content=assistant_message_buffer,
                    metadata_json={"cli_type": "cursor", "event_type": "assistant_aggregated"},
                    session_id=session_id,
                    created_at=datetime.now(timezone.utc)
                )

            await process.wait()
            
            # Log completion
            if cursor_session_id:
                print(f"✅ [Cursor] Session completed: {cursor_session_id}")
            
        except FileNotFoundError:
            error_msg = "❌ Cursor Agent CLI not found. Please install with: curl https://cursor.com/install -fsS | bash"
            yield Message(
                id=str(uuid.uuid4()),
                project_id=project_path,
                role="assistant",
                message_type="error",
                content=error_msg,
                metadata_json={"error": "cli_not_found", "cli_type": "cursor"},
                session_id=session_id,
                created_at=datetime.now(timezone.utc)
            )
        except Exception as e:
            error_msg = f"❌ Cursor Agent execution failed: {str(e)}"
            yield Message(
                id=str(uuid.uuid4()),
                project_id=project_path,
                role="assistant",
                message_type="error",
                content=error_msg,
                metadata_json={"error": "execution_failed", "cli_type": "cursor", "exception": str(e)},
                session_id=session_id,
                created_at=datetime.now(timezone.utc)
            )
    
    async def get_session_id(self, project_id: str) -> Optional[str]:
        """Get stored session ID for project to enable session continuity"""
        if self.db_session:
            try:
                from app.models.projects import Project
                project = self.db_session.query(Project).filter(Project.id == project_id).first()
                if project and project.active_cursor_session_id:
                    print(f"💾 [Cursor] Retrieved session ID from DB: {project.active_cursor_session_id}")
                    return project.active_cursor_session_id
            except Exception as e:
                print(f"⚠️ [Cursor] Failed to get session ID from DB: {e}")
        
        # Fallback to in-memory storage
        return self._session_store.get(project_id)
    
    async def set_session_id(self, project_id: str, session_id: str) -> None:
        """Store session ID for project to enable session continuity"""
        # Store in database if available
        if self.db_session:
            try:
                from app.models.projects import Project
                project = self.db_session.query(Project).filter(Project.id == project_id).first()
                if project:
                    project.active_cursor_session_id = session_id
                    self.db_session.commit()
                    print(f"💾 [Cursor] Session ID saved to DB for project {project_id}: {session_id}")
                    return
                else:
                    print(f"⚠️ [Cursor] Project {project_id} not found in DB")
            except Exception as e:
                print(f"⚠️ [Cursor] Failed to save session ID to DB: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️ [Cursor] No DB session available")
        
        # Fallback to in-memory storage
        self._session_store[project_id] = session_id
        print(f"💾 [Cursor] Session ID stored in memory for project {project_id}: {session_id}")





class UnifiedCLIManager:
    """Unified manager for all CLI implementations"""

    def __init__(
        self,
        project_id: str,
        project_path: str,
        session_id: str,
        conversation_id: str,
        db: Any,  # SQLAlchemy Session
        dependencies: Optional[CLIDependencies] = None
    ):
        self.project_id = project_id
        self.project_path = project_path
        self.session_id = session_id
        self.conversation_id = conversation_id
        self.db = db
        self.dependencies = dependencies

        # Fallback to direct imports if no dependencies provided
        if dependencies is None:
            from app.core.websocket.manager import manager as ws_manager
            from app.core.interfaces import CLIDependencies
            self.dependencies = CLIDependencies(websocket_manager=ws_manager, logger=ui)

        # Initialize CLI adapters with database session and dependencies
        self.cli_adapters = {
            CLIType.CLAUDE: ClaudeCodeCLI(dependencies=self.dependencies),
            CLIType.CURSOR: CursorAgentCLI(db_session=db, dependencies=self.dependencies)
        }
    
    async def execute_instruction(
        self,
        instruction: str,
        cli_type: CLIType,
        fallback_enabled: bool = True,  # Kept for backward compatibility but not used
        images: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        is_initial_prompt: bool = False
    ) -> Dict[str, Any]:
        """Execute instruction with specified CLI"""
        
        # Try the specified CLI
        if cli_type in self.cli_adapters:
            cli = self.cli_adapters[cli_type]
            
            # Check if CLI is available
            status = await cli.check_availability()
            if status.get("available") and status.get("configured"):
                try:
                    return await self._execute_with_cli(
                        cli, instruction, images, model, is_initial_prompt
                    )
                except Exception as e:
                    ui.error(f"CLI {cli_type.value} failed: {e}", "CLI")
                    return {
                        "success": False,
                        "error": str(e),
                        "cli_attempted": cli_type.value
                    }
            else:
                return {
                    "success": False,
                    "error": status.get("error", "CLI not available"),
                    "cli_attempted": cli_type.value
                }
        
        return {
            "success": False,
            "error": f"CLI type {cli_type.value} not implemented",
            "cli_attempted": cli_type.value
        }
    
    async def _execute_with_cli(
        self,
        cli,
        instruction: str,
        images: Optional[List[Dict[str, Any]]],
        model: Optional[str] = None,
        is_initial_prompt: bool = False
    ) -> Dict[str, Any]:
        """Execute instruction with a specific CLI"""
        
        ui.info(f"Starting {cli.cli_type.value} execution", "CLI")
        if model:
            ui.debug(f"Using model: {model}", "CLI")
        
        messages_collected = []
        has_changes = False
        has_error = False  # Track if any error occurred
        result_success = None  # Track result event success status
        
        # Log callback
        async def log_callback(message: str):
            # CLI output logs are now only printed to console, not sent to UI
            pass

        # Create session record first to avoid foreign key constraint errors
        await self._ensure_session_exists(cli.cli_type.value, model, instruction)

        message_count = 0
        
        async for message in cli.execute_with_streaming(
            instruction=instruction,
            project_path=self.project_path,
            session_id=self.session_id,
            log_callback=log_callback,
            images=images,
            model=model,
            is_initial_prompt=is_initial_prompt
        ):
            message_count += 1
            
            # Check for error messages or result status
            if message.message_type == "error":
                has_error = True
                ui.error(f"CLI error detected: {message.content[:100]}", "CLI")
            
            # Check for Cursor result event (stored in metadata)
            if message.metadata_json:
                event_type = message.metadata_json.get("event_type")
                original_event = message.metadata_json.get("original_event", {})
                
                if event_type == "result" or original_event.get("type") == "result":
                    # Cursor sends result event with success/error status
                    is_error = original_event.get("is_error", False)
                    subtype = original_event.get("subtype", "")
                    
                    # ★ DEBUG: Log the complete result event structure
                    ui.info(f"🔍 [Cursor] Result event received:", "DEBUG")
                    ui.info(f"   Full event: {original_event}", "DEBUG")
                    ui.info(f"   is_error: {is_error}", "DEBUG")
                    ui.info(f"   subtype: '{subtype}'", "DEBUG")
                    ui.info(f"   has event.result: {'result' in original_event}", "DEBUG")
                    ui.info(f"   has event.status: {'status' in original_event}", "DEBUG")
                    ui.info(f"   has event.success: {'success' in original_event}", "DEBUG")
                    
                    if is_error or subtype == "error":
                        has_error = True
                        result_success = False
                        ui.error(f"Cursor result: error (is_error={is_error}, subtype='{subtype}')", "CLI")
                    elif subtype == "success":
                        result_success = True
                        ui.success(f"Cursor result: success (subtype='{subtype}')", "CLI")
                    else:
                        # ★ NEW: Handle case where subtype is not "success" but execution was successful
                        ui.warning(f"Cursor result: no explicit success subtype (subtype='{subtype}', is_error={is_error})", "CLI")
                        # If there's no error indication, assume success
                        if not is_error:
                            result_success = True
                            ui.success(f"Cursor result: assuming success (no error detected)", "CLI")
            
            # Save message to database
            message.project_id = self.project_id
            message.conversation_id = self.conversation_id
            self.db.add(message)
            self.db.commit()
            
            messages_collected.append(message)
            
            # Check if message should be hidden from UI
            should_hide = message.metadata_json and message.metadata_json.get("hidden_from_ui", False)
            
            # Send message via WebSocket only if not hidden
            if not should_hide:
                ws_message = {
                    "type": "message",
                    "data": {
                        "id": message.id,
                        "role": message.role,
                        "message_type": message.message_type,
                        "content": message.content,
                        "metadata": message.metadata_json,
                        "parent_message_id": getattr(message, 'parent_message_id', None),
                        "session_id": message.session_id,
                        "conversation_id": self.conversation_id,
                        "created_at": message.created_at.isoformat()
                    },
                    "timestamp": message.created_at.isoformat()
                }
                try:
                    await self.dependencies.websocket_manager.send_message(self.project_id, ws_message)
                except Exception as e:
                    self.dependencies.logger.error(f"WebSocket send failed: {e}", "Message")
            
            # Check if changes were made
            if message.metadata_json and "changes_made" in message.metadata_json:
                has_changes = True
        
        # Determine final success status
        # For Cursor: check result_success if available, otherwise check has_error
        # For Claude: check has_error
        ui.info(f"🔍 Final success determination: cli_type={cli.cli_type}, result_success={result_success}, has_error={has_error}", "CLI")
        
        if cli.cli_type == CLIType.CURSOR and result_success is not None:
            success = result_success
            ui.info(f"Using Cursor result_success: {result_success}", "CLI")
        else:
            success = not has_error
            ui.info(f"Using has_error logic: not {has_error} = {success}", "CLI")
        
        if success:
            ui.success(f"Streaming completed successfully. Total messages: {len(messages_collected)}", "CLI")
        else:
            ui.error(f"Streaming completed with errors. Total messages: {len(messages_collected)}", "CLI")
        
        return {
            "success": success,
            "cli_used": cli.cli_type.value,
            "has_changes": has_changes,
            "message": f"{'Successfully' if success else 'Failed to'} execute with {cli.cli_type.value}",
            "error": "Execution failed" if not success else None,
            "messages_count": len(messages_collected)
        }
    
    async def check_cli_status(self, cli_type: CLIType, selected_model: Optional[str] = None) -> Dict[str, Any]:
        """Check status of a specific CLI"""
        if cli_type in self.cli_adapters:
            status = await self.cli_adapters[cli_type].check_availability()
            
            # Add model validation if model is specified
            if selected_model and status.get("available"):
                cli = self.cli_adapters[cli_type]
                if not cli.is_model_supported(selected_model):
                    status["model_warning"] = f"Model '{selected_model}' may not be supported by {cli_type.value}"
                    status["suggested_models"] = status.get("default_models", [])
                else:
                    status["selected_model"] = selected_model
                    status["model_valid"] = True
            
            return status
        return {
            "available": False,
            "configured": False,
            "error": f"CLI type {cli_type.value} not implemented"
        }

    async def _ensure_session_exists(self, cli_type: str, model: Optional[str], instruction: str) -> None:
        """Ensure a session record exists in the database before creating messages"""
        try:
            from app.models.sessions import Session
            from datetime import datetime

            # Check if session already exists
            existing_session = self.db.query(Session).filter(Session.id == self.session_id).first()
            if existing_session:
                ui.debug(f"Session {self.session_id} already exists", "Session")
                return

            # Create new session record
            session = Session(
                id=self.session_id,
                project_id=self.project_id,
                claude_session_id=None,  # Will be set later if needed
                status="active",
                model=model,
                cli_type=cli_type,
                instruction=instruction[:500] if instruction else None,  # Truncate long instructions
                started_at=datetime.utcnow()
            )

            self.db.add(session)
            self.db.commit()
            ui.debug(f"Created session record: {self.session_id}", "Session")

        except Exception as e:
            ui.error(f"Failed to create session record: {str(e)}", "Session")
            # Don't fail the entire process if session creation fails
            # The foreign key constraint will still fail, but we'll get a clearer error

"""
Input validation and sanitization utilities
"""
import re
import shlex
from typing import List, Optional
from pathlib import Path


class InputValidator:
    """Validates and sanitizes user inputs"""
    
    # Safe characters for CLI arguments
    SAFE_CLI_PATTERN = re.compile(r'^[a-zA-Z0-9\-_\.\s\/\\:]+$')
    
    # Dangerous command patterns
    DANGEROUS_PATTERNS = [
        r'[;&|`$()]',  # Command injection characters
        r'\.\.',       # Directory traversal
        r'rm\s+',      # Delete commands
        r'del\s+',     # Windows delete
        r'format\s+',  # Format commands
        r'shutdown',   # System shutdown
        r'reboot',     # System reboot
    ]
    
    @classmethod
    def sanitize_cli_argument(cls, arg: str, is_message_content: bool = False) -> str:
        """Sanitize a CLI argument"""
        if not isinstance(arg, str):
            raise ValueError("CLI argument must be a string")

        # For message content, use more lenient validation
        if is_message_content:
            return cls.validate_message_content(arg)

        # Check for dangerous patterns for other CLI arguments
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, arg, re.IGNORECASE):
                raise ValueError(f"Potentially dangerous pattern detected: {pattern}")

        # Basic sanitization - remove null bytes and control characters
        sanitized = arg.replace('\x00', '').replace('\r', '').replace('\n', ' ')

        # Limit length
        if len(sanitized) > 10000:
            raise ValueError("CLI argument too long (max 10000 characters)")

        return sanitized.strip()
    
    @classmethod
    def validate_cli_command(cls, command: List[str]) -> List[str]:
        """Validate and sanitize a CLI command"""
        if not isinstance(command, list):
            raise ValueError("Command must be a list of strings")

        if len(command) == 0:
            raise ValueError("Command cannot be empty")

        if len(command) > 50:
            raise ValueError("Command has too many arguments (max 50)")

        # Validate each argument
        sanitized_command = []
        for i, arg in enumerate(command):
            # Check if this is a message content argument (usually after --message flag)
            is_message = (i > 0 and command[i-1] in ['--message', '-p'])
            sanitized_arg = cls.sanitize_cli_argument(arg, is_message_content=is_message)
            sanitized_command.append(sanitized_arg)

        return sanitized_command
    
    @classmethod
    def validate_project_path(cls, path: str) -> str:
        """Validate a project path"""
        if not isinstance(path, str):
            raise ValueError("Path must be a string")
        
        # Sanitize path
        sanitized_path = cls.sanitize_cli_argument(path)
        
        # Convert to Path object for validation
        try:
            path_obj = Path(sanitized_path)
        except Exception as e:
            raise ValueError(f"Invalid path format: {e}")
        
        # Check for directory traversal
        if '..' in path_obj.parts:
            raise ValueError("Directory traversal not allowed")
        
        # Check if path is absolute (should be relative to projects root)
        if path_obj.is_absolute():
            raise ValueError("Absolute paths not allowed")
        
        return sanitized_path
    
    @classmethod
    def validate_model_name(cls, model: str) -> str:
        """Validate AI model name"""
        if not isinstance(model, str):
            raise ValueError("Model name must be a string")
        
        # Allow only alphanumeric, hyphens, dots, and underscores
        if not re.match(r'^[a-zA-Z0-9\-\._]+$', model):
            raise ValueError("Invalid model name format")
        
        if len(model) > 100:
            raise ValueError("Model name too long (max 100 characters)")
        
        return model.strip()
    
    @classmethod
    def validate_message_content(cls, message: str) -> str:
        """Validate message content - more lenient for user instructions"""
        if not isinstance(message, str):
            raise ValueError("Message must be a string")

        # Remove null bytes and excessive whitespace
        sanitized = message.replace('\x00', '').strip()

        if len(sanitized) == 0:
            raise ValueError("Message cannot be empty")

        if len(sanitized) > 100000:  # 100KB limit
            raise ValueError("Message too long (max 100KB)")

        # Check for extremely dangerous patterns only (not parentheses)
        extremely_dangerous = [
            r'rm\s+-rf\s+/',  # Dangerous delete commands
            r'del\s+/[sq]',   # Windows dangerous delete
            r'format\s+c:',   # Format system drive
            r'shutdown\s+',   # System shutdown
            r'reboot\s+',     # System reboot
            r'sudo\s+rm',     # Sudo delete
        ]

        for pattern in extremely_dangerous:
            if re.search(pattern, sanitized, re.IGNORECASE):
                raise ValueError(f"Potentially dangerous command detected: {pattern}")

        return sanitized


def validate_environment_variables():
    """Validate critical environment variables on startup"""
    import os
    from app.core.config import settings
    
    errors = []
    
    # Check encryption key in production
    if os.getenv("ENVIRONMENT") == "production":
        if not settings.encryption_key:
            errors.append("ENCRYPTION_KEY is required in production")
    
    # Validate projects root path
    try:
        projects_path = Path(settings.projects_root)
        if not projects_path.exists():
            projects_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        errors.append(f"Invalid PROJECTS_ROOT path: {e}")
    
    # Validate port ranges
    if settings.preview_port_start >= settings.preview_port_end:
        errors.append("PREVIEW_PORT_START must be less than PREVIEW_PORT_END")
    
    if settings.preview_port_start < 1024:
        errors.append("PREVIEW_PORT_START should be >= 1024 (non-privileged ports)")
    
    if errors:
        raise ValueError("Environment validation failed:\n" + "\n".join(f"- {error}" for error in errors))

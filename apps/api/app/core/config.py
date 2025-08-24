from pydantic import BaseModel
import os
from pathlib import Path


def find_project_root() -> Path:
    """
    Find the project root directory by looking for specific marker files.
    This ensures consistent behavior regardless of where the API is executed from.
    """
    current_path = Path(__file__).resolve()
    
    # Start from current file and go up
    for parent in [current_path] + list(current_path.parents):
        # Check if this directory has both apps/ and Makefile (project root indicators)
        if (parent / 'apps').is_dir() and (parent / 'Makefile').exists():
            return parent
    
    # Fallback: navigate up from apps/api to project root
    # Current path is likely: /project-root/apps/api/app/core/config.py
    # So we need to go up 4 levels: config.py -> core -> app -> api -> apps -> project-root
    api_dir = current_path.parent.parent.parent  # /project-root/apps/api
    if api_dir.name == 'api' and api_dir.parent.name == 'apps':
        return api_dir.parent.parent  # /project-root
    
    # Last resort: current working directory
    return Path.cwd()


# Get project root once at module load
PROJECT_ROOT = find_project_root()


class Settings(BaseModel):
    api_port: int = int(os.getenv("API_PORT", "8080"))

    # SQLite database URL
    database_url: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{PROJECT_ROOT / 'data' / 'cc.db'}",
    )

    # Project directory - use relative path by default for cross-platform compatibility
    projects_root: str = os.getenv("PROJECTS_ROOT", str(PROJECT_ROOT / "data" / "projects"))
    projects_root_host: str = os.getenv("PROJECTS_ROOT_HOST", os.getenv("PROJECTS_ROOT", str(PROJECT_ROOT / "data" / "projects")))

    preview_port_start: int = int(os.getenv("PREVIEW_PORT_START", "3100"))
    preview_port_end: int = int(os.getenv("PREVIEW_PORT_END", "3999"))

    # Encryption key validation
    encryption_key: str = os.getenv("ENCRYPTION_KEY", "")

    # CORS origins (comma-separated or JSON array); "*" to allow all
    _cors_env: str = os.getenv("CORS_ALLOWED_ORIGINS", "*")
    cors_allow_origins: list[str] = []

    def validate_encryption_key(self) -> None:
        """Validate encryption key is provided in production"""
        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production" and not self.encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY environment variable is required in production. "
                "Generate a secure key with: python -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())'"
            )


settings = Settings()

# Validate configuration on startup
try:
    settings.validate_encryption_key()
except ValueError as e:
    import sys
    from app.core.terminal_ui import ui
    ui.error(f"Configuration Error: {e}", "Config")
    if os.getenv("ENVIRONMENT") == "production":
        sys.exit(1)
    else:
        ui.warn("Running in development mode without explicit encryption key", "Config")

# Initialize CORS origins after settings object creation
raw = settings._cors_env.strip()
if raw == "*":
    settings.cors_allow_origins = ["*"]
else:
    import json
    try:
        if raw.startswith("["):
            settings.cors_allow_origins = json.loads(raw)
        else:
            settings.cors_allow_origins = [o.strip() for o in raw.split(",") if o.strip()]
    except Exception:
        # Fallback to single origin string
        settings.cors_allow_origins = [raw]
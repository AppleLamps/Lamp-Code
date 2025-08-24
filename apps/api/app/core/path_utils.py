import os
from pathlib import Path
from app.core.config import PROJECT_ROOT, settings


def mask_path(p: str) -> str:
    """Return a safe, relative-looking path for responses/logs.

    - Replaces absolute projects_root prefix with '...'
    - If under the project repo, return path relative to repo root
    - Otherwise, just return basename as a fallback
    """
    if not p:
        return p
    try:
        path = Path(p)
        # If under projects_root, show relative to individual project root
        projects_root = Path(settings.projects_root)
        if path.is_absolute() and str(path).startswith(str(projects_root)):
            try:
                rel_to_projects = path.relative_to(projects_root)
                # For repo and assets, keep subdir; else compress
                parts = rel_to_projects.parts
                if len(parts) >= 2 and parts[1] in {"repo", "assets", "data"}:
                    return str(rel_to_projects)
                return str(Path(parts[0]) / Path(*parts[1:]))
            except Exception:
                pass
        # If under PROJECT_ROOT, return relative
        project_root = Path(PROJECT_ROOT)
        try:
            rel = path.relative_to(project_root)
            return str(rel)
        except Exception:
            pass
        # Fallback to basename
        return path.name
    except Exception:
        return os.path.basename(p)

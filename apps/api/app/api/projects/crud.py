"""
Project CRUD Operations
Handles create, read, update, delete operations for projects
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
import re
import uuid
import asyncio
import os

from app.api.deps import get_db
from app.models.projects import Project as ProjectModel
from app.models.messages import Message
from app.models.project_services import ProjectServiceConnection
from app.models.sessions import Session as SessionModel
from app.services.project.initializer import initialize_project
from app.core.di_setup import get_cli_dependencies
from app.services.cli.unified_manager import UnifiedCLIManager, CLIType

# Project ID validation regex
PROJECT_ID_REGEX = re.compile(r"^[a-z0-9-]{3,}$")

# Pydantic models
class ProjectCreate(BaseModel):
    project_id: str = Field(..., pattern=PROJECT_ID_REGEX.pattern)
    name: str
    initial_prompt: Optional[str] = None
    preferred_cli: Optional[str] = "claude"
    selected_model: Optional[str] = None
    fallback_enabled: Optional[bool] = True
    cli_settings: Optional[dict] = None

class ProjectUpdate(BaseModel):
    name: str

class ServiceConnection(BaseModel):
    provider: str
    status: str
    connected: bool

class Project(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str = "idle"
    preview_url: Optional[str] = None
    created_at: datetime
    last_active_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    services: Optional[dict] = None
    features: Optional[List[str]] = None
    tech_stack: Optional[List[str]] = None
    ai_generated: Optional[bool] = None
    initial_prompt: Optional[str] = None
    preferred_cli: Optional[str] = None
    selected_model: Optional[str] = None

router = APIRouter()

# Use the global WebSocket manager instance shared across the app

# Metadata generation removed - using initial prompt directly in chat

async def process_initial_prompt_with_ai(project_id: str, initial_prompt: str, project_path: str, websocket_manager, db_session):
    """Process the initial prompt with AI to generate project structure"""
    try:
        from app.core.terminal_ui import ui
        from app.api.deps import get_db

        ui.info(f"Processing initial prompt for project {project_id}: {initial_prompt[:100]}...", "AI Generation")

        # Use a fresh database session to avoid transaction conflicts
        fresh_db = next(get_db())
        try:
            # Get project from database to get CLI preferences
            project = fresh_db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            if not project:
                raise Exception("Project not found")

            # Create CLI manager with fresh session
            cli_manager = UnifiedCLIManager(
                project_id=project_id,
                project_path=project_path,
                session_id=f"init-{project_id}",
                conversation_id=f"init-{project_id}",
                db=fresh_db
            )

            # Enhanced prompt for initial project generation
            enhanced_prompt = f"""Based on this request: "{initial_prompt}"

Please create a complete project structure. You have a minimal starting point with just package.json, README.md, and .gitignore.

Your task:
1. Analyze the request and determine the best technology stack
2. Create all necessary files and directories
3. Set up proper project configuration (package.json, build scripts, etc.)
4. Create initial source code files
5. Add appropriate dependencies to package.json
6. Create a working application that matches the request

The project should be ready to run with npm install && npm run dev (or equivalent).

Current project structure:
- package.json (basic template)
- README.md (basic template)
- .gitignore (basic template)

Please build upon this foundation to create: {initial_prompt}"""

            # Execute with Claude
            cli_type = CLIType.CLAUDE if project.preferred_cli == "claude" else CLIType.CURSOR

            result = await cli_manager.execute_instruction(
                instruction=enhanced_prompt,
                cli_type=cli_type,
                fallback_enabled=project.fallback_enabled or True,
                images=[],
                model=project.selected_model,
                is_initial_prompt=True
            )

            if result and result.get("success"):
                ui.success(f"Successfully generated project structure for {project_id}", "AI Generation")
            else:
                ui.error(f"Failed to generate project structure: {result.get('error', 'Unknown error')}", "AI Generation")

        except Exception as inner_e:
            ui.error(f"Error during AI generation: {str(inner_e)}", "AI Generation")
        finally:
            # Always close the fresh database session
            fresh_db.close()

    except Exception as e:
        ui.error(f"Error processing initial prompt: {str(e)}", "AI Generation")
        # Don't fail the entire initialization if AI generation fails
        # The user can still manually trigger it later


async def initialize_project_background(project_id: str, project_name: str, body: ProjectCreate):
    """Initialize project in background with WebSocket progress updates"""
    try:
        # Get WebSocket manager through dependency injection
        dependencies = get_cli_dependencies()
        websocket_manager = dependencies.websocket_manager

        # Send initial status update
        await websocket_manager.broadcast_to_project(project_id, {
            "type": "project_status",
            "data": {
                "status": "initializing",
                "message": "Initializing project files..."
            }
        })
        
        # Initialize the project using the AI-driven initializer
        from app.services.project.initializer import initialize_project_with_ai
        from app.api.deps import get_db
        
        # Create new database session for background task
        db_session = next(get_db())
        
        try:
            # Start both tasks concurrently for faster initialization
            tasks = []
            
            # Task 1: Initialize project files with AI
            async def init_project_task():
                try:
                    # Get the initial prompt from the project
                    project = db_session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
                    initial_prompt = project.initial_prompt if project else None

                    project_path = await initialize_project_with_ai(project_id, project_name, initial_prompt)

                    # Update project with repo path using fresh session
                    project = db_session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
                    if project:
                        project.repo_path = project_path
                        db_session.commit()

                    return project_path
                except Exception as e:
                    # Even if initialization partially fails, try to set the expected project path
                    # This handles cases where the Next.js project is created but git init fails
                    from app.core.config import settings
                    expected_path = os.path.join(settings.projects_root, project_id, "repo")

                    if os.path.exists(expected_path):
                        # Project directory exists, update database with path
                        project = db_session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
                        if project:
                            project.repo_path = expected_path
                            db_session.commit()

                        from app.core.terminal_ui import ui
                        ui.warn(f"Project {project_id} partially initialized (path set despite errors): {e}", "Projects")
                        return expected_path
                    else:
                        # Project directory doesn't exist, re-raise the exception
                        raise e
            
            tasks.append(init_project_task())
            
            # Skip metadata generation - will use initial prompt directly
            
            # Wait for project initialization to complete
            project_path = await asyncio.gather(*tasks)
            project_path = project_path[0]  # Get the actual path from the task result

            # Ensure project is committed to database before AI processing
            project = db_session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            if project:
                db_session.commit()  # Commit the project to database first

            # Now process the initial prompt if it exists
            if project and project.initial_prompt:
                await websocket_manager.broadcast_to_project(project_id, {
                    "type": "project_status",
                    "data": {
                        "status": "generating",
                        "message": "AI is generating your project structure..."
                    }
                })

                # Process the initial prompt with Claude (using a fresh session)
                await process_initial_prompt_with_ai(project_id, project.initial_prompt, project_path, websocket_manager, db_session)

            # Set status to active and send final completion message
            if project:
                project.status = "active"
                db_session.commit()

            # Send final completion status
            await websocket_manager.broadcast_to_project(project_id, {
                "type": "project_status",
                "data": {
                    "status": "active",
                    "message": "Project ready!"
                }
            })
            
            from app.core.terminal_ui import ui
            ui.success(f"Project {project_id} initialized successfully", "Projects")
            
        finally:
            db_session.close()
        
    except Exception as e:
        # Create separate session for error handling
        error_db = next(get_db())
        try:
            # Update project status to failed
            project = error_db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            if project:
                project.status = "failed"
                error_db.commit()
        finally:
            error_db.close()
        
        # Send error status
        await websocket_manager.broadcast_to_project(project_id, {
            "type": "project_status",
            "data": {
                "status": "failed",
                "message": f"Failed to initialize project: {str(e)}"
            }
        })
        from app.core.terminal_ui import ui
        ui.error(f"Failed to initialize project {project_id}: {e}", "Projects")
        return


async def install_dependencies_background(project_id: str, project_path: str):
    """Install dependencies in background"""
    try:
        import subprocess
        import os
        import shutil

        # Check if package.json exists
        package_json_path = os.path.join(project_path, "package.json")
        if os.path.exists(package_json_path):
            from app.core.terminal_ui import ui
            ui.info(f"Installing dependencies for project {project_id}...", "Projects")

            # Enhanced environment setup for better npm detection (same as filesystem.py)
            env = os.environ.copy()

            # On Windows, ensure npm paths are included
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

            # Find npm executable with enhanced environment
            npm_path = shutil.which("npm", path=env.get("PATH"))
            if not npm_path:
                from app.core.terminal_ui import ui
                ui.warn(f"npm not found for project {project_id} dependency installation", "Projects")
                return

            # Run npm install in background with enhanced environment
            from app.services.local_runtime import _acquire_install_lock, _release_install_lock, _save_install_hash
            if not _acquire_install_lock(project_path):
                from app.core.terminal_ui import ui
                ui.info(f"Another install in progress for project {project_id}, skipping background install", "Projects")
                return
            try:
                process = await asyncio.create_subprocess_exec(
                    npm_path, "install",
                    cwd=project_path,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    from app.core.terminal_ui import ui
                    ui.success(f"Dependencies installed successfully for project {project_id}", "Projects")
                    # Save hash so preview path can detect up-to-date deps
                    try:
                        _save_install_hash(project_path)
                    except Exception as e:
                        from app.core.terminal_ui import ui
                        ui.warn(f"Failed to save install hash for project {project_id}: {e}", "Projects")
                else:
                    from app.core.terminal_ui import ui
                    ui.error(f"Failed to install dependencies for project {project_id}: {stderr.decode()}", "Projects")
            finally:
                _release_install_lock(project_path)
    except Exception as e:
        from app.core.terminal_ui import ui
        ui.error(f"Error installing dependencies: {e}", "Projects")

@router.post("/{project_id}/install-dependencies")
async def install_project_dependencies(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Install project dependencies in background"""
    
    # Check if project exists
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project.repo_path:
        raise HTTPException(status_code=400, detail="Project repository path not found")
    
    # Add background task for dependency installation
    background_tasks.add_task(install_dependencies_background, project_id, project.repo_path)
    
    return {"message": "Dependency installation started in background", "project_id": project_id}


@router.get("/health")
async def projects_health():
    """Simple health check for projects router"""
    return {"status": "ok", "router": "projects"}



@router.get("/", response_model=List[Project])
async def list_projects(db: Session = Depends(get_db)) -> List[Project]:
    """List all projects with their status and last activity"""
    
    # Get projects with their last message time using subquery
    last_message_subquery = (
        db.query(
            Message.project_id,
            func.max(Message.created_at).label('last_message_at')
        )
        .group_by(Message.project_id)
        .subquery()
    )
    
    # Query projects with last message time
    projects_with_last_message = (
        db.query(ProjectModel, last_message_subquery.c.last_message_at)
        .outerjoin(
            last_message_subquery,
            ProjectModel.id == last_message_subquery.c.project_id
        )
        .order_by(desc(ProjectModel.created_at))
        .all()
    )
    
    result: List[Project] = []
    for project, last_message_at in projects_with_last_message:
        # Get service connections for this project
        services = {}
        service_connections = db.query(ProjectServiceConnection).filter(
            ProjectServiceConnection.project_id == project.id
        ).all()
        
        for conn in service_connections:
            services[conn.provider] = {
                "connected": True,
                "status": conn.status
            }
        
        # Ensure all service types are represented
        for provider in ["github", "supabase", "vercel"]:
            if provider not in services:
                services[provider] = {
                    "connected": False,
                    "status": "disconnected"
                }
        
        # Extract AI-generated info from settings
        ai_info = project.settings or {}
        
        result.append(Project(
            id=project.id,
            name=project.name,
            description=ai_info.get('description'),
            status=project.status or "idle",
            preview_url=project.preview_url,
            created_at=project.created_at,
            last_active_at=project.last_active_at,
            last_message_at=last_message_at,
            services=services,
            features=ai_info.get('features'),
            tech_stack=ai_info.get('tech_stack'),
            ai_generated=ai_info.get('ai_generated', False),
            initial_prompt=project.initial_prompt,
            preferred_cli=project.preferred_cli,
            selected_model=project.selected_model
        ))
    
    return result


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    """Get a specific project by ID"""
    
    try:
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Extract AI-generated info from settings
        ai_info = project.settings or {}
        
        return Project(
            id=project.id,
            name=project.name,
            description=ai_info.get('description'),
            status=project.status or "idle",
            preview_url=project.preview_url,
            created_at=project.created_at,
            last_active_at=project.last_active_at,
            last_message_at=None,  # Simplified for debugging
            services={},  # Simplified for debugging
            features=ai_info.get('features'),
            tech_stack=ai_info.get('tech_stack'),
            ai_generated=ai_info.get('ai_generated', False),
            initial_prompt=project.initial_prompt
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/", response_model=Project)
async def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db)
) -> Project:
    """Create a new project"""
    
    from app.core.terminal_ui import ui
    ui.info(f"[CreateProject] Received request", "Projects")
    from app.core.terminal_ui import ui
    ui.info(f"[CreateProject] CLI: {body.preferred_cli}, Model: {body.selected_model}", "Projects")
    
    # Check if project already exists
    existing = db.query(ProjectModel).filter(ProjectModel.id == body.project_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Project {body.project_id} already exists")
    
    # Create database record with initializing status
    preferred_cli = body.preferred_cli or "claude"
    # Set default model based on CLI
    selected_model = body.selected_model
    if not selected_model:
        if preferred_cli == "claude":
            selected_model = "sonnet-4"  # Use unified model name
        elif preferred_cli == "cursor":
            selected_model = "sonnet-4"  # Use unified model name
    fallback_enabled = body.fallback_enabled if body.fallback_enabled is not None else True
    
    from app.core.terminal_ui import ui
    ui.info(f"[CreateProject] Creating project {body.project_id} with CLI: {preferred_cli}, Model: {selected_model}, Fallback: {fallback_enabled}", "Projects")
    
    project = ProjectModel(
        id=body.project_id,
        name=body.name,
        repo_path=None,  # Will be set after initialization
        initial_prompt=body.initial_prompt,
        status="initializing",  # Set to initializing
        created_at=datetime.utcnow(),
        preferred_cli=preferred_cli,
        selected_model=selected_model,
        fallback_enabled=fallback_enabled
    )
    
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # Send immediate status update
    dependencies = get_cli_dependencies()
    websocket_manager = dependencies.websocket_manager
    await websocket_manager.broadcast_to_project(project.id, {
        "type": "project_status",
        "data": {
            "status": "initializing",
            "message": "Setting up workspace..."
        }
    })
    
    # Start project initialization in background
    asyncio.create_task(initialize_project_background(project.id, project.name, body))
    
    return Project(
        id=project.id,
        name=project.name,
        description="AI will generate description based on your prompt...",
        status=project.status,
        preview_url=project.preview_url,
        created_at=project.created_at,
        last_active_at=project.last_active_at,
        last_message_at=None,
        services={
            "github": {"connected": False, "status": "disconnected"},
            "supabase": {"connected": False, "status": "disconnected"},
            "vercel": {"connected": False, "status": "disconnected"}
        },
        features=[],
        tech_stack=["Next.js", "React", "TypeScript"],
        ai_generated=False,  # Will be updated after AI processing
        initial_prompt=project.initial_prompt
    )


@router.put("/{project_id}", response_model=Project)
async def update_project(
    project_id: str, 
    body: ProjectUpdate, 
    db: Session = Depends(get_db)
) -> Project:
    """Update a project"""
    
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Update project name
    project.name = body.name
    db.commit()
    db.refresh(project)
    
    # Get last message time
    last_message = db.query(Message).filter(
        Message.project_id == project_id
    ).order_by(desc(Message.created_at)).first()
    
    # Get service connections
    services = {}
    service_connections = db.query(ProjectServiceConnection).filter(
        ProjectServiceConnection.project_id == project.id
    ).all()
    
    for conn in service_connections:
        services[conn.provider] = {
            "connected": True,
            "status": conn.status
        }
    
    # Ensure all service types are represented
    for provider in ["github", "supabase", "vercel"]:
        if provider not in services:
            services[provider] = {
                "connected": False,
                "status": "disconnected"
            }
    
    # Extract AI-generated info from settings
    ai_info = project.settings or {}
    
    return Project(
        id=project.id,
        name=project.name,
        description=ai_info.get('description'),
        status=project.status or "idle",
        preview_url=project.preview_url,
        created_at=project.created_at,
        last_active_at=project.last_active_at,
        last_message_at=last_message.created_at if last_message else None,
        services=services,
        features=ai_info.get('features'),
        tech_stack=ai_info.get('tech_stack'),
        ai_generated=ai_info.get('ai_generated', False),
        initial_prompt=project.initial_prompt,
        preferred_cli=project.preferred_cli,
        selected_model=project.selected_model
    )


@router.delete("/{project_id}")
async def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Delete a project"""
    
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Delete associated messages
    db.query(Message).filter(Message.project_id == project_id).delete()
    
    # Delete service connections
    db.query(ProjectServiceConnection).filter(
        ProjectServiceConnection.project_id == project_id
    ).delete()
    
    # Delete project
    db.delete(project)
    db.commit()
    
    # Clean up project files from disk
    try:
        from app.services.project.initializer import cleanup_project
        cleanup_success = await cleanup_project(project_id)
        if cleanup_success:
            from app.core.terminal_ui import ui
            ui.success(f"Project files deleted successfully for {project_id}", "Projects")
        else:
            from app.core.terminal_ui import ui
            ui.warn(f"Project files may not have been fully deleted for {project_id}", "Projects")
    except Exception as e:
        from app.core.terminal_ui import ui
        ui.error(f"Error cleaning up project files for {project_id}: {e}", "Projects")
        # Don't fail the whole operation if file cleanup fails
    
    return {"message": f"Project {project_id} deleted successfully"}

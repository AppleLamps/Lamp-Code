from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import base64
import uuid
from app.api.deps import get_db
from app.core.config import settings
from app.models.projects import Project as ProjectModel
from app.services.assets import write_bytes
import logging
from app.core.path_utils import mask_path

router = APIRouter(prefix="/api/assets", tags=["assets"]) 


class LogoRequest(BaseModel):
    b64_png: str  # Accept base64-encoded PNG (fallback if no OpenAI key)


@router.post("/{project_id}/logo")
async def upload_logo(project_id: str, body: LogoRequest, db: Session = Depends(get_db)):
    row = db.get(ProjectModel, project_id)
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    project_assets = os.path.join(settings.projects_root, project_id, "assets")
    data = base64.b64decode(body.b64_png)
    logo_path = os.path.join(project_assets, "logo.png")
    write_bytes(logo_path, data)
    return {"path": f"assets/logo.png"}


MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB limit


@router.post("/{project_id}/upload")
async def upload_image(project_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload an image file to project assets directory"""
    logging.getLogger(__name__).info("Image upload: project_id=%s, filename=%s", project_id, file.filename)
    
    # Verify project exists
    row = db.get(ProjectModel, project_id)
    if not row:
        logging.getLogger(__name__).warning("Project not found: %s", project_id)
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if file is an image
    logging.getLogger(__name__).debug("File info: content_type=%s, size=%s", file.content_type, getattr(file, 'size', 'unknown'))
    if not file.content_type or not file.content_type.startswith('image/'):
        logging.getLogger(__name__).warning("Invalid file type: %s", file.content_type)
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Create assets directory if it doesn't exist
    project_assets = os.path.join(settings.projects_root, project_id, "assets")
    logging.getLogger(__name__).debug("Assets directory: %s", mask_path(project_assets))
    os.makedirs(project_assets, exist_ok=True)
    
    # Generate unique filename to avoid conflicts
    file_extension = os.path.splitext(file.filename or 'image.png')[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(project_assets, unique_filename)
    logging.getLogger(__name__).info("Saving asset to: %s", mask_path(file_path))
    
    try:
        # Save file
        content = await file.read()
        # Enforce size limits
        if len(content) > MAX_IMAGE_BYTES:
            logging.getLogger(__name__).warning("File too large: %s bytes", len(content))
            raise HTTPException(status_code=413, detail="File too large")
        
        write_bytes(file_path, content)
        logging.getLogger(__name__).info("File saved successfully: %s bytes", len(content))

        return {
            "path": f"assets/{unique_filename}",
            "filename": unique_filename,
            "original_filename": file.filename
        }
    except Exception as e:
        # Do not leak absolute paths or internal details
        logging.getLogger(__name__).exception("Failed to save file")
        raise HTTPException(status_code=500, detail="Failed to save file")

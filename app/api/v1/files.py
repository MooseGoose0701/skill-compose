"""File upload API endpoints"""
import base64
import mimetypes
import uuid
import aiofiles
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import get_settings, Settings

router = APIRouter(prefix="/files", tags=["Files"])


# ============ Skill Icon Serving ============

@router.get("/skill-icons/{filename}")
async def get_skill_icon(
    filename: str,
    settings: Settings = Depends(get_settings),
):
    """Serve a skill icon image."""
    # Validate filename (prevent path traversal)
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    icons_dir = Path(settings.upload_dir) / "skill-icons"
    icon_path = icons_dir / filename

    if not icon_path.exists():
        raise HTTPException(status_code=404, detail="Icon not found")

    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    return FileResponse(
        path=str(icon_path),
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"}  # Cache for 1 hour
    )

# Simple in-memory file registry (use database in production)
_file_registry: dict[str, dict] = {}


class FileInfo(BaseModel):
    file_id: str
    filename: str
    path: str  # Full path for agent to access
    size: int
    content_type: str
    uploaded_at: datetime


def get_upload_dir(settings: Settings = Depends(get_settings)) -> Path:
    """Get upload directory"""
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


@router.post("/upload", response_model=FileInfo)
async def upload_file(
    file: UploadFile = File(...),
    upload_dir: Path = Depends(get_upload_dir),
):
    """
    Upload a file for skill processing.
    Returns file_id to reference in execute requests.
    """
    file_id = str(uuid.uuid4())

    # Sanitize filename
    safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in (file.filename or "file"))
    file_path = upload_dir / file_id / safe_name
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Save file
    size = 0
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(8192):
            await f.write(chunk)
            size += len(chunk)

    # Register
    info = {
        "file_id": file_id,
        "filename": safe_name,
        "size": size,
        "content_type": file.content_type or "application/octet-stream",
        "path": str(file_path),
        "uploaded_at": datetime.utcnow(),
    }
    _file_registry[file_id] = info

    return FileInfo(**info)


@router.get("/{file_id}", response_model=FileInfo)
async def get_file_info(file_id: str):
    """Get uploaded file info"""
    info = _file_registry.get(file_id)
    if not info:
        raise HTTPException(status_code=404, detail="File not found")
    return FileInfo(**info)


@router.delete("/{file_id}", status_code=204)
async def delete_file(file_id: str):
    """Delete uploaded file"""
    info = _file_registry.get(file_id)
    if not info:
        raise HTTPException(status_code=404, detail="File not found")

    import shutil
    file_dir = Path(info["path"]).parent
    if file_dir.exists():
        shutil.rmtree(file_dir)

    del _file_registry[file_id]

# ============ Path-based Output File Download ============
# Works across all workers (reads from disk, no in-memory registry needed)

# Allowed base directories for output file downloads
def _get_allowed_dirs(settings: Settings) -> list[Path]:
    """Get the list of allowed base directories for output file downloads."""
    dirs = [
        Path("/app/workspaces"),       # Executor shared volume
        Path("/tmp/agent_workspaces"), # Local workspace temp dir
        Path(settings.upload_dir),     # Upload directory
    ]
    # Project working dir
    project_dir = Path(settings.project_dir)
    dirs.append(project_dir)
    return dirs


@router.get("/output/download")
async def download_output_file_by_path(
    path: str = Query(..., description="Base64url-encoded absolute file path"),
    settings: Settings = Depends(get_settings),
):
    """Download an output file by its base64url-encoded path.

    This endpoint works across all workers since it reads directly from disk.
    The path must resolve to a file under an allowed directory.
    """
    # Decode base64url path
    try:
        decoded_path = base64.urlsafe_b64decode(path.encode('ascii')).decode('utf-8')
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path encoding")

    filepath = Path(decoded_path).resolve()

    # Security: validate path is under an allowed directory
    allowed_dirs = _get_allowed_dirs(settings)
    is_allowed = False
    for allowed in allowed_dirs:
        try:
            allowed_resolved = allowed.resolve()
            if str(filepath).startswith(str(allowed_resolved)):
                is_allowed = True
                break
        except OSError:
            continue

    if not is_allowed:
        raise HTTPException(status_code=403, detail="Access denied: path not in allowed directories")

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not filepath.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    content_type = mimetypes.guess_type(filepath.name)[0] or "application/octet-stream"

    # Use inline disposition for browser-renderable types (HTML, images, etc.)
    # so they can be displayed in iframes and img tags instead of triggering download
    inline_types = {"text/html", "image/png", "image/jpeg", "image/gif", "image/svg+xml",
                    "image/webp", "video/mp4", "video/webm", "audio/mpeg", "audio/wav"}
    if content_type in inline_types:
        return FileResponse(
            path=str(filepath),
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{filepath.name}"'},
        )

    return FileResponse(
        path=str(filepath),
        filename=filepath.name,
        media_type=content_type,
    )

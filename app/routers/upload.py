from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from typing import Optional

from ..config import Settings
from ..services.storage import save_file, get_file_url

settings = Settings()
router = APIRouter(prefix="/upload", tags=["upload"])


class UploadResponse(BaseModel):
    url: str
    filename: str
    content_type: str
    size: int


@router.post("/", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    subdir: Optional[str] = Form("uploads"),
):
    """Uploads an image or video file directly to AWS S3 (or local storage fallback) and returns its public URL."""
    if not file:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided")

    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "file"

    # Validate file format (images and videos)
    is_image = content_type.startswith("image/")
    is_video = content_type.startswith("video/")

    if not (is_image or is_video):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid file type. Only images (PNG, JPG, WEBP, GIF) and videos (MP4, WEBM, MOV) are supported.",
        )

    data = await file.read()
    file_size = len(data)

    # Validate size limits
    max_mb = settings.MAX_VIDEO_SIZE_MB if is_video else settings.MAX_IMAGE_SIZE_MB
    if file_size > max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {max_mb} MB.",
        )

    # Save to S3 or local storage
    saved_result = save_file(data, filename, subdir=subdir or "uploads", content_type=content_type)
    url = get_file_url(saved_result)

    return UploadResponse(
        url=url,
        filename=filename,
        content_type=content_type,
        size=file_size,
    )

import os
import logging
from pathlib import Path
from uuid import uuid4
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ..config import Settings

settings = Settings()
logger = logging.getLogger(__name__)


def upload_to_s3(file_bytes: bytes, filename: str, content_type: str = "application/octet-stream", subdir: str = "uploads") -> str | None:
    """Uploads file_bytes to AWS S3 bucket and returns the public S3 URL."""
    bucket_name = settings.S3_BUCKET
    key_id = settings.S3_KEY_ID
    secret_key = settings.S3_SECRET_KEY
    region = settings.AWS_REGION or "ap-south-1"

    if not bucket_name or not key_id or not secret_key:
        logger.warning("AWS S3 credentials missing. Falling back to local storage.")
        return None

    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=key_id,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        ext = os.path.splitext(filename)[1]
        unique_name = f"{uuid4().hex}{ext}"
        s3_key = f"{subdir}/{unique_name}" if subdir else unique_name

        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
        )

        s3_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{s3_key}"
        logger.info(f"File uploaded successfully to S3: {s3_url}")
        return s3_url
    except (BotoCoreError, ClientError, Exception) as exc:
        logger.error(f"Error uploading file to S3: {exc}")
        return None


def save_file(file_bytes: bytes, filename: str, subdir: str = "", content_type: str = "application/octet-stream") -> str:
    """Saves file to AWS S3 if configured; falls back to local storage path if S3 fails or is unconfigured."""
    s3_url = upload_to_s3(file_bytes, filename, content_type=content_type, subdir=subdir or "uploads")
    if s3_url:
        return s3_url

    # Fallback to local file storage
    dest_dir = Path(settings.MEDIA_ROOT) / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid4().hex}_{filename}"
    dest_path = dest_dir / unique_name
    with open(dest_path, "wb") as f:
        f.write(file_bytes)
    return str(dest_path)


def get_file_url(path: str) -> str:
    """Returns the URL for a stored file. If path is already an S3 URL or HTTP URL, return as-is."""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    # For local storage we expose files under /media
    try:
        return f"/media/{os.path.relpath(path, settings.MEDIA_ROOT)}"
    except Exception:
        return path

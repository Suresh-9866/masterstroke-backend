from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    KEYCLOAK_SERVER_URL: str | None = None
    KEYCLOAK_REALM: str | None = None
    KEYCLOAK_CLIENT_ID: str | None = None
    KEYCLOAK_CLIENT_SECRET: str | None = None
    KEYCLOAK_ADMIN_CLIENT_ID: str | None = None
    KEYCLOAK_ADMIN: str | None = None
    KEYCLOAK_ADMIN_PASSWORD: str | None = None
    KEYCLOAK_ISSUER: str | None = None
    DEBUG_RETURN_OTP: bool = False

    # SMTP Email Configuration
    SMTP_SERVER: str | None = "smtp.gmail.com"
    SMTP_PORT: int | None = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None

    # Meta WhatsApp Configuration
    META_WA_PHONE_NUMBER_ID: str | None = None
    META_WA_ACCESS_TOKEN: str | None = None

    # AWS S3 Storage Configuration
    AWS_ACCESS_KEY_ID: str | None = Field(None, validation_alias="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str | None = Field(None, validation_alias="AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str | None = Field("ap-south-1", validation_alias="AWS_REGION")
    AWS_STORAGE_BUCKET_NAME: str | None = Field(None, validation_alias="AWS_STORAGE_BUCKET_NAME")

    # Alt Env Keys
    AWS_KEY_ID: str | None = Field(None, validation_alias="AWS_KEY_ID")
    AWS_SECRET_KEY_ACCESS: str | None = Field(None, validation_alias="AWS_SECRET_KEY_ACCESS")
    AWS_BUCKET: str | None = Field(None, validation_alias="AWS_BUCKET")

    @property
    def S3_KEY_ID(self) -> str | None:
        return self.AWS_ACCESS_KEY_ID or self.AWS_KEY_ID

    @property
    def S3_SECRET_KEY(self) -> str | None:
        return self.AWS_SECRET_ACCESS_KEY or self.AWS_SECRET_KEY_ACCESS

    @property
    def S3_BUCKET(self) -> str | None:
        return self.AWS_STORAGE_BUCKET_NAME or self.AWS_BUCKET

    # read raw env var MEDIA_ROOT into these fields; some environments may
    # provide `MEDIA_ROOT` which pydantic maps to `media_root` (lowercased),
    # so accept both names to avoid validation errors.
    RAW_MEDIA_ROOT: str | None = Field(None, validation_alias="MEDIA_ROOT")
    media_root: str | None = Field(None, validation_alias="MEDIA_ROOT")
    MAX_VIDEO_SIZE_MB: int = 50
    MAX_IMAGE_SIZE_MB: int = 5
    POINTS_PER_100_INR: int = 10





    @property
    def ASYNC_DATABASE_URL(self) -> str:
        url = str(self.DATABASE_URL)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def MEDIA_ROOT(self) -> str:
        """Resolve and return the media root path.

        Resolution order:
        - If `MEDIA_ROOT` is provided via environment (`RAW_MEDIA_ROOT`), use it.
        - If running inside Docker (simple detection), default to `/app/media`.
        - Otherwise (local dev), resolve to the `media/` directory at the project root.

        This property ensures the directory exists (creates it) so callers can safely
        mount or write files without additional checks.
        """
        # 1) explicit env-provided value (prefer explicit RAW_MEDIA_ROOT, then legacy media_root)
        env_value = self.RAW_MEDIA_ROOT or self.media_root
        if env_value:
            path = Path(env_value)
        else:
            # 2) simple Docker detection: presence of /.dockerenv or explicit env var
            if Path("/.dockerenv").exists() or os.environ.get("RUNNING_IN_DOCKER") or os.environ.get("DOCKER"):
                path = Path("/app/media")
            else:
                # 3) local development: place media folder next to the project root
                # this file lives in <project>/app/config.py -> ascend one level to project root
                project_root = Path(__file__).resolve().parents[1]
                path = project_root / "media"

        # ensure directory exists
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception:
            # best-effort: if creation fails, return the string path and let callers handle errors
            return str(path)

        return str(path)

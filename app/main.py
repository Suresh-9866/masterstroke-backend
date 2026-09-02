from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import health, auth
from .routers import otp_stub, category, business, admin, transactions, subscribers, beneficiaries
from .config import Settings
from pathlib import Path
import logging


settings = Settings()

app = FastAPI(title="WINGS Backend")

# Enable CORS for cross-origin requests from frontend (localhost and Netlify deployed app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "https://aquamarine-frangipane-02b784.netlify.app",
    ],
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(otp_stub.router)
app.include_router(category.router)
app.include_router(business.router)
app.include_router(admin.router)
app.include_router(transactions.router)
app.include_router(subscribers.router)
app.include_router(beneficiaries.router)

# mount media directory (ensure it exists first)
media_root = settings.MEDIA_ROOT
try:
    # settings.MEDIA_ROOT property ensures creation, but double-check here
    Path(media_root).mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=media_root), name="media")
except Exception as exc:
    # fallback: log and continue without mounting to avoid crashing the app
    logging.error("Failed to mount media directory %s: %s", media_root, exc)

@app.get("/ready")
async def ready():
    return {"status": "ok"}

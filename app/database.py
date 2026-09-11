import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from .config import Settings

settings = Settings()

engine = create_async_engine(settings.ASYNC_DATABASE_URL, future=True, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

from .models import Base

async def get_async_session() -> AsyncSession:
    async with async_session() as session:
        yield session

async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;"))
            await conn.execute(text("ALTER TABLE beneficiaries ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;"))
    except Exception as e:
        print("Database init_db error:", e)


async def check_db() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

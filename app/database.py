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
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS ad_image VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS ad_description VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS ad_start_date VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS ad_end_date VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS business_sub_category VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS established_year VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS gender VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS address VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS gst_number VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS about_business VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS target_customers VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS enrollment_duration VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS renewal_date VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS referrer_type VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS referrer_name VARCHAR;"))
            await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS referrer_phone VARCHAR;"))
    except Exception as e:
        print("Database init_db error:", e)


async def check_db() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

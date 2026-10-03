import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select

from .config import Settings

settings = Settings()

db_url = settings.ASYNC_DATABASE_URL
connect_args = {}
if "sqlite" not in db_url:
    connect_args["ssl"] = "require"

engine = create_async_engine(db_url, connect_args=connect_args, future=True, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

from .models import Base
from .models.user_profile import UserProfile

async def get_async_session() -> AsyncSession:
    async with async_session() as session:
        yield session

async def init_db():
    global engine, async_session
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if "sqlite" not in str(engine.url):
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
                await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS logo VARCHAR;"))
                await conn.execute(text("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS number_of_renewals INTEGER DEFAULT 0;"))
                await conn.execute(text("ALTER TABLE beneficiaries ADD COLUMN IF NOT EXISTS address VARCHAR;"))
                await conn.execute(text("ALTER TABLE beneficiaries ADD COLUMN IF NOT EXISTS qualification VARCHAR;"))
                await conn.execute(text("ALTER TABLE beneficiaries ADD COLUMN IF NOT EXISTS year_of_passing VARCHAR;"))
                await conn.execute(text("ALTER TABLE beneficiaries ADD COLUMN IF NOT EXISTS resume VARCHAR;"))
                await conn.execute(text("ALTER TABLE beneficiaries ADD COLUMN IF NOT EXISTS joined_date VARCHAR;"))
                await conn.execute(text("ALTER TABLE beneficiaries ADD COLUMN IF NOT EXISTS referrer_type VARCHAR;"))
                await conn.execute(text("ALTER TABLE beneficiaries ADD COLUMN IF NOT EXISTS referrer_name VARCHAR;"))
                await conn.execute(text("ALTER TABLE beneficiaries ADD COLUMN IF NOT EXISTS referrer_phone VARCHAR;"))
                await conn.execute(text("ALTER TABLE user_profile ALTER COLUMN role TYPE VARCHAR USING role::VARCHAR;"))
                await conn.execute(text("ALTER TABLE user_profile ALTER COLUMN status TYPE VARCHAR USING status::VARCHAR;"))
    except Exception as exc:
        logging.warning("Primary database connection unavailable (%s). Falling back to local SQLite database (wings.db)...", exc)
        sqlite_url = "sqlite+aiosqlite:///./wings.db"
        engine = create_async_engine(sqlite_url, future=True, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Seed default admin user if user_profile table is empty
    try:
        async with async_session() as session:
            res = await session.execute(select(UserProfile).where(UserProfile.username == "admin"))
            if not res.scalars().first():
                admin_user = UserProfile(
                    full_name="System Administrator",
                    username="admin",
                    email="wings.velloredigital@gmail.com",
                    phone_number="9876543210",
                    password_hash="admin",
                    role="admin",
                    status="active",
                )
                session.add(admin_user)
                await session.commit()
    except Exception as err:
        logging.warning("Admin seeding check skipped: %s", err)


async def check_db() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

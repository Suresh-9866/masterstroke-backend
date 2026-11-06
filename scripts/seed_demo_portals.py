import sys
import os
from pathlib import Path

# Add project root to path
backend_dir = str(Path(__file__).resolve().parents[1])
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import asyncio
from sqlalchemy import select
from app.database import async_session, init_db
from app.models.subscriber import Subscriber
from app.models.beneficiary import Beneficiary
from app.models.user_profile import UserProfile
from app.routers.portal import hash_password

async def seed():
    await init_db()
    pw_hash = hash_password("wings123")

    async with async_session() as session:
        # 1. Admin
        res = await session.execute(select(UserProfile).where(UserProfile.username == "admin"))
        admin = res.scalars().first()
        if not admin:
            admin = UserProfile(
                full_name="System Administrator",
                username="admin",
                email="wings.velloredigital@gmail.com",
                phone_number="9876543210",
                password_hash="admin",
                role="admin",
                status="active",
            )
            session.add(admin)
            print("Seeded demo admin: admin / admin")
        else:
            print("Verified demo admin: admin / admin")

        # 2. Subscriber
        res = await session.execute(select(Subscriber).where(Subscriber.phone.like("%9876543210%")))
        sub = res.scalars().first()
        if not sub:
            sub = Subscriber(
                business_name="Wings Tech Solutions",
                business_category="IT & Digital Services",
                owner_name="Suresh Kumar",
                phone="9876543210",
                whatsapp_number="9876543210",
                email="suresh.wings@gmail.com",
                password_hash=pw_hash,
                is_password_set=True,
                gender="Male",
                address="12 Anna Salai, Vellore, Tamil Nadu - 632001",
                established_year="2020",
                gst_number="33AAAAA0000A1Z5",
                about_business="Leading provider of custom web and mobile application solutions, digital marketing, and enterprise IT infrastructure.",
                target_customers="SMEs, Retailers, Healthcare Clinics, and Educational Institutions",
                total_business_taken=175000.0,
                total_business_given=95000.0,
                business_count=24,
                leads=16,
                total_rewards_gained=4500,
                is_deleted=False
            )
            session.add(sub)
            print("Seeded demo subscriber: 9876543210 / wings123")
        else:
            sub.password_hash = pw_hash
            sub.is_password_set = True
            print("Updated demo subscriber: 9876543210 / wings123")

        # 3. Beneficiary
        res = await session.execute(select(Beneficiary).where(Beneficiary.whatsapp_number.like("%9876543211%")))
        ben = res.scalars().first()
        if not ben:
            ben = Beneficiary(
                beneficiary_name="Ramesh Patel",
                whatsapp_number="9876543211",
                referrer_phone="9876543211",
                status="Active",
                occupation="Senior Business Associate",
                qualification="B.Tech (Information Technology)",
                year_of_passing="2022",
                address="45 Gandhi Road, Katpadi, Vellore - 632014",
                password_hash=pw_hash,
                is_password_set=True,
                total_business_given=48000.0,
                total_rewards_gained=2400,
                jobs_taken=5,
                is_deleted=False
            )
            session.add(ben)
            print("Seeded demo beneficiary: 9876543211 / wings123")
        else:
            ben.password_hash = pw_hash
            ben.is_password_set = True
            print("Updated demo beneficiary: 9876543211 / wings123")

        await session.commit()
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed())

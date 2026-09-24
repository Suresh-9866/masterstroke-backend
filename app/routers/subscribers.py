from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from ..database import get_async_session
from ..models.subscriber import Subscriber
from ..services.whatsapp import send_whatsapp_template


router = APIRouter(prefix="/subscribers", tags=["subscribers"])

class SubscriberCreate(BaseModel):
    business_name: str
    business_category: str
    owner_name: str
    total_business_taken: Optional[float] = 0.0
    total_business_given: Optional[float] = 0.0
    business_count: Optional[int] = 0
    leads: Optional[int] = 0
    s_member_induction: Optional[str] = "Pending"
    b_member_induction: Optional[str] = "Pending"
    total_rewards_gained: Optional[int] = 0
    benefit_claim_status: Optional[str] = "Not Claimed"
    phone: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    joined_date: Optional[str] = None
    business_sub_category: Optional[str] = None
    established_year: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    whatsapp_number: Optional[str] = None
    gst_number: Optional[str] = None
    about_business: Optional[str] = None
    target_customers: Optional[str] = None
    enrollment_duration: Optional[str] = None
    renewal_date: Optional[str] = None
    referrer_type: Optional[str] = None
    referrer_name: Optional[str] = None
    referrer_phone: Optional[str] = None
    ad_image: Optional[str] = None
    ad_description: Optional[str] = None
    ad_start_date: Optional[str] = None
    ad_end_date: Optional[str] = None

class SubscriberUpdate(BaseModel):
    business_name: Optional[str] = None
    business_category: Optional[str] = None
    owner_name: Optional[str] = None
    total_business_taken: Optional[float] = None
    total_business_given: Optional[float] = None
    business_count: Optional[int] = None
    leads: Optional[int] = None
    s_member_induction: Optional[str] = None
    b_member_induction: Optional[str] = None
    total_rewards_gained: Optional[int] = None
    benefit_claim_status: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    joined_date: Optional[str] = None
    business_sub_category: Optional[str] = None
    established_year: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    whatsapp_number: Optional[str] = None
    gst_number: Optional[str] = None
    about_business: Optional[str] = None
    target_customers: Optional[str] = None
    enrollment_duration: Optional[str] = None
    renewal_date: Optional[str] = None
    referrer_type: Optional[str] = None
    referrer_name: Optional[str] = None
    referrer_phone: Optional[str] = None
    ad_image: Optional[str] = None
    ad_description: Optional[str] = None
    ad_start_date: Optional[str] = None
    ad_end_date: Optional[str] = None

@router.get("/")
async def get_subscribers(db: AsyncSession = Depends(get_async_session)):
    stmt = select(Subscriber).order_by(Subscriber.id.desc())
    res = await db.execute(stmt)
    subscribers = res.scalars().all()
    return subscribers

@router.get("/{subscriber_id}")
async def get_subscriber(subscriber_id: int, db: AsyncSession = Depends(get_async_session)):
    stmt = select(Subscriber).where(Subscriber.id == subscriber_id)
    res = await db.execute(stmt)
    subscriber = res.scalars().first()
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return subscriber

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_subscriber(data: SubscriberCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_session)):
    subscriber = Subscriber(
        business_name=data.business_name,
        business_category=data.business_category,
        owner_name=data.owner_name,
        total_business_taken=data.total_business_taken or 0.0,
        total_business_given=data.total_business_given or 0.0,
        business_count=data.business_count or 0,
        leads=data.leads or 0,
        s_member_induction=data.s_member_induction or "Pending",
        b_member_induction=data.b_member_induction or "Pending",
        total_rewards_gained=data.total_rewards_gained or 0,
        benefit_claim_status=data.benefit_claim_status or "Not Claimed",
        phone=data.phone,
        email=data.email,
        location=data.location,
        joined_date=data.joined_date,
        business_sub_category=data.business_sub_category,
        established_year=data.established_year,
        gender=data.gender,
        address=data.address,
        whatsapp_number=data.whatsapp_number,
        gst_number=data.gst_number,
        about_business=data.about_business,
        target_customers=data.target_customers,
        enrollment_duration=data.enrollment_duration,
        renewal_date=data.renewal_date,
        referrer_type=data.referrer_type,
        referrer_name=data.referrer_name,
        referrer_phone=data.referrer_phone,
        ad_image=data.ad_image,
        ad_description=data.ad_description,
        ad_start_date=data.ad_start_date,
        ad_end_date=data.ad_end_date,
    )
    db.add(subscriber)
    await db.commit()
    await db.refresh(subscriber)

    if subscriber.phone:
        background_tasks.add_task(send_whatsapp_template, subscriber.phone, "hello_world")

    return subscriber


@router.put("/{subscriber_id}")
async def update_subscriber(subscriber_id: int, data: SubscriberUpdate, db: AsyncSession = Depends(get_async_session)):
    stmt = select(Subscriber).where(Subscriber.id == subscriber_id)
    res = await db.execute(stmt)
    subscriber = res.scalars().first()
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(subscriber, field, val)

    await db.commit()
    await db.refresh(subscriber)
    return subscriber

@router.delete("/{subscriber_id}")
async def delete_subscriber(subscriber_id: int, db: AsyncSession = Depends(get_async_session)):
    stmt = select(Subscriber).where(Subscriber.id == subscriber_id)
    res = await db.execute(stmt)
    subscriber = res.scalars().first()
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    subscriber.is_deleted = True
    await db.commit()
    await db.refresh(subscriber)
    return {"status": "soft_deleted", "id": subscriber_id, "subscriber": subscriber}

@router.post("/{subscriber_id}/restore")
async def restore_subscriber(subscriber_id: int, db: AsyncSession = Depends(get_async_session)):
    stmt = select(Subscriber).where(Subscriber.id == subscriber_id)
    res = await db.execute(stmt)
    subscriber = res.scalars().first()
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    subscriber.is_deleted = False
    await db.commit()
    await db.refresh(subscriber)
    return {"status": "restored", "id": subscriber_id, "subscriber": subscriber}


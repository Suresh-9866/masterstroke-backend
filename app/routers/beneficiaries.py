from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from ..database import get_async_session
from ..models.beneficiary import Beneficiary
from ..services.whatsapp import send_whatsapp_template

router = APIRouter(prefix="/beneficiaries", tags=["beneficiaries"])

class BeneficiaryCreate(BaseModel):
    beneficiary_name: str
    status: Optional[str] = "Active"
    whatsapp_number: Optional[str] = None
    location: Optional[str] = None
    total_business_given: Optional[float] = 0.0
    s_member_induction: Optional[str] = "Pending"
    b_member_induction: Optional[str] = "Pending"
    total_rewards_gained: Optional[int] = 0
    benefit_claim_status: Optional[str] = "Not Claimed"
    email: Optional[str] = None
    subscriber_name: Optional[str] = None
    subscriber_id: Optional[str] = None
    occupation: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    jobs_taken: Optional[int] = 0

class BeneficiarySignup(BaseModel):
    beneficiary_name: str
    email: str
    whatsapp_number: str
    location: Optional[str] = "Not Specified"
    occupation: Optional[str] = "Not Specified"
    age: Optional[int] = None
    gender: Optional[str] = None
    password: Optional[str] = None

class BeneficiaryUpdate(BaseModel):
    beneficiary_name: Optional[str] = None
    status: Optional[str] = None
    whatsapp_number: Optional[str] = None
    location: Optional[str] = None
    total_business_given: Optional[float] = None
    s_member_induction: Optional[str] = None
    b_member_induction: Optional[str] = None
    total_rewards_gained: Optional[int] = None
    benefit_claim_status: Optional[str] = None
    email: Optional[str] = None
    subscriber_name: Optional[str] = None
    subscriber_id: Optional[str] = None
    occupation: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    jobs_taken: Optional[int] = None

@router.get("/")
async def get_beneficiaries(db: AsyncSession = Depends(get_async_session)):
    stmt = select(Beneficiary).order_by(Beneficiary.id.desc())
    res = await db.execute(stmt)
    beneficiaries = res.scalars().all()
    return beneficiaries

@router.get("/{beneficiary_id}")
async def get_beneficiary(beneficiary_id: int, db: AsyncSession = Depends(get_async_session)):
    stmt = select(Beneficiary).where(Beneficiary.id == beneficiary_id)
    res = await db.execute(stmt)
    beneficiary = res.scalars().first()
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")
    return beneficiary

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_beneficiary(data: BeneficiaryCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_session)):
    beneficiary = Beneficiary(
        beneficiary_name=data.beneficiary_name,
        status=data.status or "Active",
        whatsapp_number=data.whatsapp_number or "",
        location=data.location or "Not Specified",
        total_business_given=data.total_business_given or 0.0,
        s_member_induction=data.s_member_induction or "Pending",
        b_member_induction=data.b_member_induction or "Pending",
        total_rewards_gained=data.total_rewards_gained or 0,
        benefit_claim_status=data.benefit_claim_status or "Not Claimed",
        email=data.email or "",
        subscriber_name=data.subscriber_name or "N/A",
        subscriber_id=data.subscriber_id or "N/A",
        occupation=data.occupation or "Not Specified",
        age=data.age or 0,
        gender=data.gender or "Not Specified",
        jobs_taken=data.jobs_taken or 0,
    )
    db.add(beneficiary)
    await db.commit()
    await db.refresh(beneficiary)

    if beneficiary.whatsapp_number:
        background_tasks.add_task(send_whatsapp_template, beneficiary.whatsapp_number, "hello_world")

    return beneficiary

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup_beneficiary(data: BeneficiarySignup, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_session)):
    beneficiary = Beneficiary(
        beneficiary_name=data.beneficiary_name,
        status="Active",
        whatsapp_number=data.whatsapp_number,
        location=data.location or "Not Specified",
        total_business_given=0.0,
        s_member_induction="Pending",
        b_member_induction="Pending",
        total_rewards_gained=0,
        benefit_claim_status="Not Claimed",
        email=data.email,
        subscriber_name="Self Signed",
        subscriber_id="WNG-BEN-SELF",
        occupation=data.occupation or "Not Specified",
        age=data.age or 0,
        gender=data.gender or "Not Specified",
        jobs_taken=0,
    )
    db.add(beneficiary)
    await db.commit()
    await db.refresh(beneficiary)

    if beneficiary.whatsapp_number:
        background_tasks.add_task(send_whatsapp_template, beneficiary.whatsapp_number, "hello_world")

    return {"status": "success", "message": "Beneficiary registered successfully", "beneficiary": beneficiary}


@router.put("/{beneficiary_id}")
async def update_beneficiary(beneficiary_id: int, data: BeneficiaryUpdate, db: AsyncSession = Depends(get_async_session)):
    stmt = select(Beneficiary).where(Beneficiary.id == beneficiary_id)
    res = await db.execute(stmt)
    beneficiary = res.scalars().first()
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(beneficiary, field, val)

    await db.commit()
    await db.refresh(beneficiary)
    return beneficiary

@router.delete("/{beneficiary_id}")
async def delete_beneficiary(beneficiary_id: int, db: AsyncSession = Depends(get_async_session)):
    stmt = select(Beneficiary).where(Beneficiary.id == beneficiary_id)
    res = await db.execute(stmt)
    beneficiary = res.scalars().first()
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")

    beneficiary.is_deleted = True
    beneficiary.status = "Deleted"
    await db.commit()
    await db.refresh(beneficiary)
    return {"status": "soft_deleted", "id": beneficiary_id, "beneficiary": beneficiary}

@router.post("/{beneficiary_id}/restore")
async def restore_beneficiary(beneficiary_id: int, db: AsyncSession = Depends(get_async_session)):
    stmt = select(Beneficiary).where(Beneficiary.id == beneficiary_id)
    res = await db.execute(stmt)
    beneficiary = res.scalars().first()
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")

    beneficiary.is_deleted = False
    beneficiary.status = "Active"
    await db.commit()
    await db.refresh(beneficiary)
    return {"status": "restored", "id": beneficiary_id, "beneficiary": beneficiary}


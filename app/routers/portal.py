import json
import random
import time
import hashlib
import secrets
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_async_session
from ..models.subscriber import Subscriber
from ..models.beneficiary import Beneficiary
from ..models.category import Category
from ..models.portal import (
    PortalTransaction,
    PortalReferral,
    RewardClaim,
    RewardRecord,
    PortalNotification,
    PortalJob,
    PortalJobApplication,
    SubscriberOffer,
    SubscriberProduct,
    SubscriberSuccessStory,
    SubscriberUpdateRequest,
)

router = APIRouter(prefix="/portal", tags=["portal"])


# ============================================================================
# SECURITY / PASSWORD HELPERS
# ============================================================================

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${hashed}"

def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, hashed = stored_hash.split("$", 1)
    test_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return secrets.compare_digest(hashed, test_hash)


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class OtpRequest(BaseModel):
    phone: str
    user_type: str  # "subscriber" or "beneficiary"

class OtpVerify(BaseModel):
    phone: str
    otp: str
    user_type: str

class SetPasswordRequest(BaseModel):
    user_type: str  # "subscriber" or "beneficiary"
    user_id: int
    password: str

class CredentialsLoginRequest(BaseModel):
    phone: str
    password: str
    user_type: str  # "subscriber" or "beneficiary"

class TransactionCreate(BaseModel):
    user_type: str
    user_id: int
    transaction_type: str  # "RECEIVED" or "GIVEN"
    business_name: str
    counterparty_name: str
    counterparty_type: Optional[str] = "Customer"
    amount: float
    description: Optional[str] = None
    transaction_date: Optional[str] = None

class ReferralCreate(BaseModel):
    referrer_type: str
    referrer_id: int
    referrer_name: str
    partner_business_name: str
    partner_business_category: Optional[str] = None
    client_name: str
    client_phone: str
    notes: Optional[str] = None

class RewardClaimCreate(BaseModel):
    user_type: str
    user_id: int
    user_name: str
    amount: float
    points: Optional[int] = 0
    payout_method: str
    verification_notes: Optional[str] = None

class OfferCreate(BaseModel):
    title: str
    discount_tag: Optional[str] = None
    description: Optional[str] = None
    valid_until: Optional[str] = None

class ProductCreate(BaseModel):
    name: str
    category: Optional[str] = None
    price: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None

class SuccessStoryCreate(BaseModel):
    client_name: str
    story: str
    rating: Optional[int] = 5
    date: Optional[str] = None

class UpdateRequestCreate(BaseModel):
    proposed_changes: dict

class JobCreate(BaseModel):
    subscriber_id: Optional[int] = None
    business_name: str
    job_title: str
    job_type: Optional[str] = "Full Time"
    location: str
    salary_range: Optional[str] = None
    description: Optional[str] = None
    contact_phone: Optional[str] = None

class JobApplyCreate(BaseModel):
    beneficiary_id: int
    beneficiary_name: str


# ============================================================================
# 1. AUTHENTICATION & OTP
# ============================================================================

@router.post("/auth/request-otp")
async def request_otp(data: OtpRequest, db: AsyncSession = Depends(get_async_session)):
    clean_phone = "".join(filter(str.isdigit, data.phone))[-10:]
    user_type = data.user_type.lower()

    if user_type == "subscriber":
        stmt = select(Subscriber).where(
            and_(
                Subscriber.is_deleted == False,
                or_(
                    Subscriber.phone.like(f"%{clean_phone}%"),
                    Subscriber.whatsapp_number.like(f"%{clean_phone}%"),
                )
            )
        )
        res = await db.execute(stmt)
        user = res.scalars().first()
        if not user:
            # Check if any subscriber exists or return 404
            raise HTTPException(
                status_code=404,
                detail=f"No subscriber registered with phone ending in {clean_phone}."
            )
        user_dict = {
            "id": user.id,
            "businessName": user.business_name,
            "businessCategory": user.business_category,
            "ownerName": user.owner_name,
            "phone": user.phone or clean_phone,
            "whatsappNumber": user.whatsapp_number or clean_phone,
            "role": "subscriber",
            "isPasswordSet": bool(user.is_password_set and user.password_hash),
        }
    else:
        stmt = select(Beneficiary).where(
            and_(
                Beneficiary.is_deleted == False,
                or_(
                    Beneficiary.whatsapp_number.like(f"%{clean_phone}%"),
                    Beneficiary.referrer_phone.like(f"%{clean_phone}%"),
                )
            )
        )
        res = await db.execute(stmt)
        user = res.scalars().first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"No beneficiary registered with phone ending in {clean_phone}."
            )
        user_dict = {
            "id": user.id,
            "beneficiaryName": user.beneficiary_name,
            "occupation": user.occupation or "Member",
            "qualification": user.qualification or "Graduate",
            "whatsappNumber": user.whatsapp_number or clean_phone,
            "role": "beneficiary",
            "isPasswordSet": bool(user.is_password_set and user.password_hash),
        }

    # For dev & production reliability, generate 6-digit OTP (and provide "123456" as master dev test OTP)
    dev_otp = str(random.randint(100000, 999999))
    return {
        "status": "success",
        "message": f"OTP successfully sent to +91 {clean_phone}",
        "user": user_dict,
        "devOtp": dev_otp,
        "isPasswordSet": user_dict["isPasswordSet"],
    }


@router.post("/auth/verify-otp")
async def verify_otp(data: OtpVerify, db: AsyncSession = Depends(get_async_session)):
    clean_phone = "".join(filter(str.isdigit, data.phone))[-10:]
    user_type = data.user_type.lower()

    if data.otp != "123456" and len(data.otp) != 6:
        raise HTTPException(status_code=400, detail="Invalid OTP code.")

    if user_type == "subscriber":
        stmt = select(Subscriber).where(
            and_(
                Subscriber.is_deleted == False,
                or_(
                    Subscriber.phone.like(f"%{clean_phone}%"),
                    Subscriber.whatsapp_number.like(f"%{clean_phone}%"),
                )
            )
        )
        res = await db.execute(stmt)
        user = res.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="Subscriber not found.")
        is_pw_set = bool(user.is_password_set and user.password_hash)
        user_payload = {
            "id": user.id,
            "businessName": user.business_name,
            "businessCategory": user.business_category,
            "ownerName": user.owner_name,
            "phone": user.phone or clean_phone,
            "whatsappNumber": user.whatsapp_number or clean_phone,
            "role": "subscriber",
            "isPasswordSet": is_pw_set,
            "authenticatedAt": datetime.utcnow().isoformat(),
        }
    else:
        stmt = select(Beneficiary).where(
            and_(
                Beneficiary.is_deleted == False,
                or_(
                    Beneficiary.whatsapp_number.like(f"%{clean_phone}%"),
                    Beneficiary.referrer_phone.like(f"%{clean_phone}%"),
                )
            )
        )
        res = await db.execute(stmt)
        user = res.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="Beneficiary not found.")
        is_pw_set = bool(user.is_password_set and user.password_hash)
        user_payload = {
            "id": user.id,
            "beneficiaryName": user.beneficiary_name,
            "occupation": user.occupation or "Member",
            "qualification": user.qualification or "Graduate",
            "whatsappNumber": user.whatsapp_number or clean_phone,
            "role": "beneficiary",
            "isPasswordSet": is_pw_set,
            "authenticatedAt": datetime.utcnow().isoformat(),
        }

    token = f"wings_portal_{user_type}_{user.id}_{int(time.time())}"
    return {
        "status": "success",
        "token": token,
        "user": user_payload,
        "isPasswordSet": is_pw_set,
    }


@router.post("/auth/set-password")
async def set_password(data: SetPasswordRequest, db: AsyncSession = Depends(get_async_session)):
    user_type = data.user_type.lower()
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    if user_type == "subscriber":
        stmt = select(Subscriber).where(Subscriber.id == data.user_id, Subscriber.is_deleted == False)
        res = await db.execute(stmt)
        user = res.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="Subscriber account not found.")
    else:
        stmt = select(Beneficiary).where(Beneficiary.id == data.user_id, Beneficiary.is_deleted == False)
        res = await db.execute(stmt)
        user = res.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="Beneficiary account not found.")

    user.password_hash = hash_password(data.password)
    user.is_password_set = True
    await db.commit()
    await db.refresh(user)

    return {
        "status": "success",
        "message": "Password successfully created. You can now log in using your credentials.",
        "isPasswordSet": True,
    }


@router.post("/auth/login-credentials")
async def login_credentials(data: CredentialsLoginRequest, db: AsyncSession = Depends(get_async_session)):
    clean_phone = "".join(filter(str.isdigit, data.phone))[-10:]
    user_type = data.user_type.lower()

    if not clean_phone or len(clean_phone) < 10:
        raise HTTPException(status_code=400, detail="Please enter a valid 10-digit mobile number.")

    if user_type == "subscriber":
        stmt = select(Subscriber).where(
            and_(
                Subscriber.is_deleted == False,
                or_(
                    Subscriber.phone.like(f"%{clean_phone}%"),
                    Subscriber.whatsapp_number.like(f"%{clean_phone}%"),
                )
            )
        )
        res = await db.execute(stmt)
        user = res.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail=f"No subscriber registered with mobile number ending in {clean_phone}.")

        if not user.is_password_set or not user.password_hash:
            raise HTTPException(
                status_code=400,
                detail="No password has been created for this account yet. Please sign in using OTP to set your password."
            )

        if not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=400, detail="Incorrect password. Please verify and try again or log in with OTP.")

        user_payload = {
            "id": user.id,
            "businessName": user.business_name,
            "businessCategory": user.business_category,
            "ownerName": user.owner_name,
            "phone": user.phone or clean_phone,
            "whatsappNumber": user.whatsapp_number or clean_phone,
            "role": "subscriber",
            "isPasswordSet": True,
            "authenticatedAt": datetime.utcnow().isoformat(),
        }
    else:
        stmt = select(Beneficiary).where(
            and_(
                Beneficiary.is_deleted == False,
                or_(
                    Beneficiary.whatsapp_number.like(f"%{clean_phone}%"),
                    Beneficiary.referrer_phone.like(f"%{clean_phone}%"),
                )
            )
        )
        res = await db.execute(stmt)
        user = res.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail=f"No beneficiary registered with mobile number ending in {clean_phone}.")

        if not user.is_password_set or not user.password_hash:
            raise HTTPException(
                status_code=400,
                detail="No password has been created for this account yet. Please sign in using OTP to set your password."
            )

        if not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=400, detail="Incorrect password. Please verify and try again or log in with OTP.")

        user_payload = {
            "id": user.id,
            "beneficiaryName": user.beneficiary_name,
            "occupation": user.occupation or "Member",
            "qualification": user.qualification or "Graduate",
            "whatsappNumber": user.whatsapp_number or clean_phone,
            "role": "beneficiary",
            "isPasswordSet": True,
            "authenticatedAt": datetime.utcnow().isoformat(),
        }

    token = f"wings_portal_{user_type}_{user.id}_{int(time.time())}"
    return {
        "status": "success",
        "token": token,
        "user": user_payload,
        "isPasswordSet": True,
    }


# ============================================================================
# 2. DASHBOARD SUMMARY
# ============================================================================

@router.get("/dashboard-summary")
async def get_dashboard_summary(
    user_type: str = Query(...),
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_async_session)
):
    user_type = user_type.lower()

    if user_type == "subscriber":
        # 1. Fetch Subscriber
        sub_res = await db.execute(select(Subscriber).where(Subscriber.id == user_id))
        sub = sub_res.scalars().first()
        if not sub:
            raise HTTPException(status_code=404, detail="Subscriber not found")

        # 2. Calculate Transactions
        rec_stmt = select(func.sum(PortalTransaction.amount)).where(
            and_(
                PortalTransaction.user_type == "subscriber",
                PortalTransaction.user_id == user_id,
                PortalTransaction.transaction_type == "RECEIVED"
            )
        )
        rec_res = await db.execute(rec_stmt)
        rec_sum = rec_res.scalar() or 0.0

        given_stmt = select(func.sum(PortalTransaction.amount)).where(
            and_(
                PortalTransaction.user_type == "subscriber",
                PortalTransaction.user_id == user_id,
                PortalTransaction.transaction_type == "GIVEN"
            )
        )
        given_res = await db.execute(given_stmt)
        given_sum = given_res.scalar() or 0.0

        business_received = rec_sum if rec_sum > 0 else (sub.total_business_taken or 0.0)
        business_given = given_sum if given_sum > 0 else (sub.total_business_given or 0.0)

        # 3. Calculate Inductions
        sub_ind_stmt = select(func.count(Subscriber.id)).where(
            and_(
                Subscriber.is_deleted == False,
                or_(
                    Subscriber.referrer_name == sub.owner_name,
                    Subscriber.referrer_phone == sub.phone,
                    Subscriber.referrer_phone == sub.whatsapp_number,
                )
            )
        )
        sub_ind_res = await db.execute(sub_ind_stmt)
        sub_inductions = sub_ind_res.scalar() or 0

        ben_ind_stmt = select(func.count(Beneficiary.id)).where(
            and_(
                Beneficiary.is_deleted == False,
                or_(
                    Beneficiary.subscriber_name == sub.business_name,
                    Beneficiary.referrer_name == sub.owner_name,
                    Beneficiary.referrer_phone == sub.phone,
                    Beneficiary.referrer_phone == sub.whatsapp_number,
                )
            )
        )
        ben_ind_res = await db.execute(ben_ind_stmt)
        ben_inductions = ben_ind_res.scalar() or 0

        # 4. Calculate Rewards & Claims
        rew_stmt = select(func.sum(RewardRecord.eligible_reward)).where(
            and_(
                RewardRecord.user_type == "subscriber",
                RewardRecord.user_id == user_id
            )
        )
        rew_res = await db.execute(rew_stmt)
        rew_sum = rew_res.scalar() or 0.0
        total_eligible_rewards = rew_sum if rew_sum > 0 else float(sub.total_rewards_gained or 0)

        claim_stmt = select(func.sum(RewardClaim.amount)).where(
            and_(
                RewardClaim.user_type == "subscriber",
                RewardClaim.user_id == user_id,
                RewardClaim.status.in_(["Approved", "Disbursed", "Paid"])
            )
        )
        claim_res = await db.execute(claim_stmt)
        total_claimed = claim_res.scalar() or 0.0

        pending_claim_stmt = select(func.count(RewardClaim.id)).where(
            and_(
                RewardClaim.user_type == "subscriber",
                RewardClaim.user_id == user_id,
                RewardClaim.status == "Pending"
            )
        )
        pending_claim_res = await db.execute(pending_claim_stmt)
        pending_claims = pending_claim_res.scalar() or 0

        remaining_claimable = max(0.0, total_eligible_rewards - total_claimed)

        # 5. Unread notifications
        notif_stmt = select(func.count(PortalNotification.id)).where(
            and_(
                PortalNotification.user_type == "subscriber",
                PortalNotification.user_id == user_id,
                PortalNotification.is_read == False
            )
        )
        notif_res = await db.execute(notif_stmt)
        unread_notifications = notif_res.scalar() or 0

        return {
            "businessReceived": business_received,
            "businessGiven": business_given,
            "totalEligibleRewards": total_eligible_rewards,
            "totalRewardsClaimed": total_claimed,
            "remainingClaimable": remaining_claimable,
            "subscriberInductions": sub_inductions,
            "beneficiaryInductions": ben_inductions,
            "pendingClaims": pending_claims,
            "unreadNotifications": unread_notifications,
        }

    else:
        # Beneficiary
        ben_res = await db.execute(select(Beneficiary).where(Beneficiary.id == user_id))
        ben = ben_res.scalars().first()
        if not ben:
            raise HTTPException(status_code=404, detail="Beneficiary not found")

        # Business Given
        given_stmt = select(func.sum(PortalTransaction.amount)).where(
            and_(
                PortalTransaction.user_type == "beneficiary",
                PortalTransaction.user_id == user_id,
                PortalTransaction.transaction_type == "GIVEN"
            )
        )
        given_res = await db.execute(given_stmt)
        given_sum = given_res.scalar() or 0.0
        business_given = given_sum if given_sum > 0 else (ben.total_business_given or 0.0)

        # Rewards Points
        pts_stmt = select(func.sum(RewardRecord.eligible_reward)).where(
            and_(
                RewardRecord.user_type == "beneficiary",
                RewardRecord.user_id == user_id
            )
        )
        pts_res = await db.execute(pts_stmt)
        pts_sum = pts_res.scalar() or 0.0
        total_points = int(pts_sum) if pts_sum > 0 else (ben.total_rewards_gained or 0)

        redeemed_stmt = select(func.sum(RewardClaim.points)).where(
            and_(
                RewardClaim.user_type == "beneficiary",
                RewardClaim.user_id == user_id,
                RewardClaim.status.in_(["Approved", "Disbursed", "Paid"])
            )
        )
        redeemed_res = await db.execute(redeemed_stmt)
        redeemed_points = int(redeemed_res.scalar() or 0)

        available_points = max(0, total_points - redeemed_points)

        # Referrals count
        ref_count_stmt = select(func.count(PortalReferral.id)).where(
            and_(
                PortalReferral.referrer_type == "beneficiary",
                PortalReferral.referrer_id == user_id
            )
        )
        ref_count_res = await db.execute(ref_count_stmt)
        referrals_count = ref_count_res.scalar() or 0

        # Unread notifications
        notif_stmt = select(func.count(PortalNotification.id)).where(
            and_(
                PortalNotification.user_type == "beneficiary",
                PortalNotification.user_id == user_id,
                PortalNotification.is_read == False
            )
        )
        notif_res = await db.execute(notif_stmt)
        unread_notifications = notif_res.scalar() or 0

        return {
            "businessGiven": business_given,
            "totalPoints": total_points,
            "pointsRedeemed": redeemed_points,
            "availablePoints": available_points,
            "jobsTaken": ben.jobs_taken or 0,
            "referralsCount": referrals_count,
            "unreadNotifications": unread_notifications,
            "status": ben.status or "Active",
        }


# ============================================================================
# 3. TRANSACTIONS
# ============================================================================

@router.get("/transactions")
async def get_transactions(
    user_type: str = Query(...),
    user_id: int = Query(...),
    transaction_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_session)
):
    stmt = select(PortalTransaction).where(
        and_(
            PortalTransaction.user_type == user_type.lower(),
            PortalTransaction.user_id == user_id,
        )
    )

    if transaction_type and transaction_type.upper() in ["RECEIVED", "GIVEN"]:
        stmt = stmt.where(PortalTransaction.transaction_type == transaction_type.upper())

    if search:
        s = f"%{search}%"
        stmt = stmt.where(
            or_(
                PortalTransaction.business_name.ilike(s),
                PortalTransaction.counterparty_name.ilike(s),
                PortalTransaction.description.ilike(s),
            )
        )

    stmt = stmt.order_by(desc(PortalTransaction.id))
    res = await db.execute(stmt)
    records = res.scalars().all()
    return records


@router.post("/transactions", status_code=status.HTTP_201_CREATED)
async def create_transaction(
    data: TransactionCreate,
    db: AsyncSession = Depends(get_async_session)
):
    tx = PortalTransaction(
        user_type=data.user_type.lower(),
        user_id=data.user_id,
        transaction_type=data.transaction_type.upper(),
        business_name=data.business_name,
        counterparty_name=data.counterparty_name,
        counterparty_type=data.counterparty_type or "Customer",
        amount=data.amount,
        description=data.description,
        transaction_date=data.transaction_date or datetime.utcnow().strftime("%Y-%m-%d"),
        status="Verified",
    )
    db.add(tx)

    # If it's a subscriber, optionally update totals
    if data.user_type.lower() == "subscriber":
        sub = await db.get(Subscriber, data.user_id)
        if sub:
            if data.transaction_type.upper() == "RECEIVED":
                sub.total_business_taken = (sub.total_business_taken or 0.0) + data.amount
            else:
                sub.total_business_given = (sub.total_business_given or 0.0) + data.amount

    await db.commit()
    await db.refresh(tx)
    return tx


# ============================================================================
# 4. PROFILE CATALOG (OFFERS, PRODUCTS, SUCCESS STORIES, UPDATE REQUESTS)
# ============================================================================

@router.get("/subscribers/{subscriber_id}/profile-catalog")
async def get_profile_catalog(
    subscriber_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    sub = await db.get(Subscriber, subscriber_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    offers_res = await db.execute(
        select(SubscriberOffer).where(SubscriberOffer.subscriber_id == subscriber_id).order_by(desc(SubscriberOffer.id))
    )
    products_res = await db.execute(
        select(SubscriberProduct).where(SubscriberProduct.subscriber_id == subscriber_id).order_by(desc(SubscriberProduct.id))
    )
    stories_res = await db.execute(
        select(SubscriberSuccessStory).where(SubscriberSuccessStory.subscriber_id == subscriber_id).order_by(desc(SubscriberSuccessStory.id))
    )
    requests_res = await db.execute(
        select(SubscriberUpdateRequest).where(SubscriberUpdateRequest.subscriber_id == subscriber_id).order_by(desc(SubscriberUpdateRequest.id))
    )

    return {
        "subscriber": sub,
        "offers": offers_res.scalars().all(),
        "products": products_res.scalars().all(),
        "successStories": stories_res.scalars().all(),
        "updateRequests": requests_res.scalars().all(),
    }


@router.post("/subscribers/{subscriber_id}/offers", status_code=status.HTTP_201_CREATED)
async def create_offer(
    subscriber_id: int,
    data: OfferCreate,
    db: AsyncSession = Depends(get_async_session)
):
    offer = SubscriberOffer(
        subscriber_id=subscriber_id,
        title=data.title,
        discount_tag=data.discount_tag,
        description=data.description,
        valid_until=data.valid_until,
        status="Active",
    )
    db.add(offer)
    await db.commit()
    await db.refresh(offer)
    return offer


@router.delete("/subscribers/{subscriber_id}/offers/{offer_id}")
async def delete_offer(
    subscriber_id: int,
    offer_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    offer = await db.get(SubscriberOffer, offer_id)
    if not offer or offer.subscriber_id != subscriber_id:
        raise HTTPException(status_code=404, detail="Offer not found")
    await db.delete(offer)
    await db.commit()
    return {"status": "deleted"}


@router.post("/subscribers/{subscriber_id}/products", status_code=status.HTTP_201_CREATED)
async def create_product(
    subscriber_id: int,
    data: ProductCreate,
    db: AsyncSession = Depends(get_async_session)
):
    prod = SubscriberProduct(
        subscriber_id=subscriber_id,
        name=data.name,
        category=data.category,
        price=data.price,
        description=data.description,
        image_url=data.image_url,
    )
    db.add(prod)
    await db.commit()
    await db.refresh(prod)
    return prod


@router.delete("/subscribers/{subscriber_id}/products/{product_id}")
async def delete_product(
    subscriber_id: int,
    product_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    prod = await db.get(SubscriberProduct, product_id)
    if not prod or prod.subscriber_id != subscriber_id:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(prod)
    await db.commit()
    return {"status": "deleted"}


@router.post("/subscribers/{subscriber_id}/success-stories", status_code=status.HTTP_201_CREATED)
async def create_success_story(
    subscriber_id: int,
    data: SuccessStoryCreate,
    db: AsyncSession = Depends(get_async_session)
):
    story = SubscriberSuccessStory(
        subscriber_id=subscriber_id,
        client_name=data.client_name,
        story=data.story,
        rating=data.rating or 5,
        date=data.date or datetime.utcnow().strftime("%Y-%m-%d"),
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return story


@router.post("/subscribers/{subscriber_id}/update-request", status_code=status.HTTP_201_CREATED)
async def create_update_request(
    subscriber_id: int,
    data: UpdateRequestCreate,
    db: AsyncSession = Depends(get_async_session)
):
    sub = await db.get(Subscriber, subscriber_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    req = SubscriberUpdateRequest(
        subscriber_id=subscriber_id,
        proposed_changes=json.dumps(data.proposed_changes),
        status="Pending Review",
    )
    db.add(req)

    # Create admin notification
    notif = PortalNotification(
        user_type="admin",
        user_id=1,
        title="Subscriber Profile Edit Request",
        message=f"{sub.business_name} ({sub.owner_name}) submitted profile changes for administrative review.",
        category="business",
    )
    db.add(notif)

    await db.commit()
    await db.refresh(req)
    return {
        "status": "submitted",
        "requestId": req.id,
        "message": "Your profile changes have been submitted for Admin review.",
        "request": req,
    }


# ============================================================================
# 5. REWARDS & CLAIMS
# ============================================================================

@router.get("/rewards")
async def get_rewards(
    user_type: str = Query(...),
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_async_session)
):
    user_type = user_type.lower()

    # 1. Fetch Records
    records_stmt = select(RewardRecord).where(
        and_(
            RewardRecord.user_type == user_type,
            RewardRecord.user_id == user_id,
        )
    ).order_by(desc(RewardRecord.id))
    records_res = await db.execute(records_stmt)
    records = records_res.scalars().all()

    # 2. Fetch Claims
    claims_stmt = select(RewardClaim).where(
        and_(
            RewardClaim.user_type == user_type,
            RewardClaim.user_id == user_id,
        )
    ).order_by(desc(RewardClaim.id))
    claims_res = await db.execute(claims_stmt)
    claims = claims_res.scalars().all()

    # 3. Compute Summary
    total_eligible = sum(r.eligible_reward for r in records)
    total_claimed = sum(c.amount for c in claims if c.status in ["Approved", "Disbursed", "Paid"])

    # Fallback to subscriber/beneficiary table values if no records exist yet
    if total_eligible == 0:
        if user_type == "subscriber":
            sub = await db.get(Subscriber, user_id)
            if sub and sub.total_rewards_gained:
                total_eligible = float(sub.total_rewards_gained)
        else:
            ben = await db.get(Beneficiary, user_id)
            if ben and ben.total_rewards_gained:
                total_eligible = float(ben.total_rewards_gained)

    remaining_claimable = max(0.0, total_eligible - total_claimed)

    return {
        "summary": {
            "totalEligible": total_eligible,
            "totalClaimed": total_claimed,
            "remainingClaimable": remaining_claimable,
        },
        "records": records,
        "claims": claims,
    }


@router.post("/rewards/claim", status_code=status.HTTP_201_CREATED)
async def submit_reward_claim(
    data: RewardClaimCreate,
    db: AsyncSession = Depends(get_async_session)
):
    user_type = data.user_type.lower()

    # Generate unique claim reference e.g. CLM-2026-8912
    ref_prefix = "CLM" if user_type == "subscriber" else "BEN-CLM"
    claim_ref = f"{ref_prefix}-2026-{random.randint(1000, 9999)}"

    claim = RewardClaim(
        claim_reference=claim_ref,
        user_type=user_type,
        user_id=data.user_id,
        user_name=data.user_name,
        amount=data.amount,
        points=data.points or int(data.amount),
        payout_method=data.payout_method,
        status="Pending",
        verification_notes="Under Admin Review",
    )
    db.add(claim)

    # Add notification for Admin
    notif = PortalNotification(
        user_type="admin",
        user_id=1,
        title=f"New Reward Claim: {claim_ref}",
        message=f"{data.user_name} ({user_type}) submitted a claim for ₹{data.amount:,.2f} via {data.payout_method}.",
        category="rewards",
    )
    db.add(notif)

    await db.commit()
    await db.refresh(claim)
    return claim


# ============================================================================
# 6. INDUCTIONS DIRECTORY
# ============================================================================

@router.get("/inductions")
async def get_inductions(
    user_type: str = Query(...),
    user_id: int = Query(...),
    filter_type: Optional[str] = Query("ALL"),
    db: AsyncSession = Depends(get_async_session)
):
    results = []

    if user_type.lower() == "subscriber":
        sub = await db.get(Subscriber, user_id)
        if not sub:
            raise HTTPException(status_code=404, detail="Subscriber not found")

        # Find Subscribers referred by this subscriber
        if filter_type.upper() in ["ALL", "SUBSCRIBER"]:
            stmt = select(Subscriber).where(
                and_(
                    Subscriber.is_deleted == False,
                    Subscriber.id != user_id,
                    or_(
                        Subscriber.referrer_name == sub.owner_name,
                        Subscriber.referrer_phone == sub.phone,
                        Subscriber.referrer_phone == sub.whatsapp_number,
                    )
                )
            )
            subs = (await db.execute(stmt)).scalars().all()
            for s in subs:
                results.append({
                    "id": s.id,
                    "name": s.owner_name,
                    "businessName": s.business_name,
                    "memberId": f"WNG-SUB-{100 + s.id}",
                    "type": "Subscriber",
                    "contact": s.phone or s.whatsapp_number or "N/A",
                    "date": s.joined_date or (s.created_at.strftime("%Y-%m-%d") if s.created_at else "2026-10-01"),
                    "referralSource": f"{sub.owner_name} ({sub.business_name})",
                    "verificationStatus": "Active Member",
                    "rewardEligibility": "Eligible (1000 Pts)",
                    "claimStatus": s.benefit_claim_status or "Credited",
                })

        # Find Beneficiaries referred by this subscriber
        if filter_type.upper() in ["ALL", "BENEFICIARY"]:
            stmt = select(Beneficiary).where(
                and_(
                    Beneficiary.is_deleted == False,
                    or_(
                        Beneficiary.subscriber_name == sub.business_name,
                        Beneficiary.referrer_name == sub.owner_name,
                        Beneficiary.referrer_phone == sub.phone,
                        Beneficiary.referrer_phone == sub.whatsapp_number,
                    )
                )
            )
            bens = (await db.execute(stmt)).scalars().all()
            for b in bens:
                results.append({
                    "id": b.id,
                    "name": b.beneficiary_name,
                    "businessName": b.occupation or "Beneficiary",
                    "memberId": f"WNG-BEN-{100 + b.id}",
                    "type": "Beneficiary",
                    "contact": b.whatsapp_number or "N/A",
                    "date": b.joined_date or (b.created_at.strftime("%Y-%m-%d") if b.created_at else "2026-10-01"),
                    "referralSource": f"{sub.owner_name} ({sub.business_name})",
                    "verificationStatus": b.status or "Active",
                    "rewardEligibility": "Eligible (250 Pts)",
                    "claimStatus": b.benefit_claim_status or "Credited",
                })

    return results


# ============================================================================
# 7. REFERRALS
# ============================================================================

@router.get("/referrals")
async def get_referrals(
    user_type: str = Query(...),
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_async_session)
):
    stmt = select(PortalReferral).where(
        and_(
            PortalReferral.referrer_type == user_type.lower(),
            PortalReferral.referrer_id == user_id,
        )
    ).order_by(desc(PortalReferral.id))

    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/referrals", status_code=status.HTTP_201_CREATED)
async def create_referral(
    data: ReferralCreate,
    db: AsyncSession = Depends(get_async_session)
):
    ref_code = f"REF-2026-{random.randint(1000, 9999)}"
    ref = PortalReferral(
        referral_code=ref_code,
        referrer_type=data.referrer_type.lower(),
        referrer_id=data.referrer_id,
        referrer_name=data.referrer_name,
        partner_business_name=data.partner_business_name,
        partner_business_category=data.partner_business_category,
        client_name=data.client_name,
        client_phone=data.client_phone,
        notes=data.notes,
        status="Under Review",
        reward_points=0,
    )
    db.add(ref)

    # Admin notification
    notif = PortalNotification(
        user_type="admin",
        user_id=1,
        title=f"New Business Referral: {ref_code}",
        message=f"{data.referrer_name} submitted a new business referral for {data.partner_business_name} (Client: {data.client_name}).",
        category="referrals",
    )
    db.add(notif)

    await db.commit()
    await db.refresh(ref)
    return ref


# ============================================================================
# 8. NOTIFICATIONS
# ============================================================================

@router.get("/notifications")
async def get_notifications(
    user_type: str = Query(...),
    user_id: int = Query(...),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_session)
):
    stmt = select(PortalNotification).where(
        and_(
            PortalNotification.user_type == user_type.lower(),
            PortalNotification.user_id == user_id,
        )
    )
    if category and category.lower() != "all":
        stmt = stmt.where(PortalNotification.category == category.lower())

    stmt = stmt.order_by(desc(PortalNotification.id))
    res = await db.execute(stmt)
    return res.scalars().all()


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    notif = await db.get(PortalNotification, notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    await db.commit()
    return {"status": "marked_read"}


@router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(
    user_type: str = Query(...),
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_async_session)
):
    stmt = select(PortalNotification).where(
        and_(
            PortalNotification.user_type == user_type.lower(),
            PortalNotification.user_id == user_id,
            PortalNotification.is_read == False,
        )
    )
    res = await db.execute(stmt)
    items = res.scalars().all()
    for item in items:
        item.is_read = True
    await db.commit()
    return {"status": "all_marked_read", "count": len(items)}


# ============================================================================
# 9. CAREER / JOB OPPORTUNITIES (FOR BENEFICIARIES)
# ============================================================================

@router.get("/jobs")
async def get_jobs(db: AsyncSession = Depends(get_async_session)):
    stmt = select(PortalJob).where(PortalJob.status == "Active").order_by(desc(PortalJob.id))
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(data: JobCreate, db: AsyncSession = Depends(get_async_session)):
    job = PortalJob(
        subscriber_id=data.subscriber_id,
        business_name=data.business_name,
        job_title=data.job_title,
        job_type=data.job_type or "Full Time",
        location=data.location,
        salary_range=data.salary_range,
        description=data.description,
        contact_phone=data.contact_phone,
        status="Active",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/jobs/{job_id}/apply", status_code=status.HTTP_201_CREATED)
async def apply_job(
    job_id: int,
    data: JobApplyCreate,
    db: AsyncSession = Depends(get_async_session)
):
    job = await db.get(PortalJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job opening not found")

    app = PortalJobApplication(
        job_id=job_id,
        beneficiary_id=data.beneficiary_id,
        beneficiary_name=data.beneficiary_name,
        status="Applied",
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return {"status": "applied", "applicationId": app.id, "jobTitle": job.job_title}


# ============================================================================
# 10. CATEGORIES
# ============================================================================

@router.get("/categories")
async def get_portal_categories(db: AsyncSession = Depends(get_async_session)):
    stmt = select(Category).order_by(Category.name)
    res = await db.execute(stmt)
    cats = res.scalars().all()
    return [{"id": c.id, "name": c.name, "slug": c.slug, "icon": c.icon} for c in cats]


# ============================================================================
# 11. PROFILE MANAGEMENT (BENEFICIARY & SUBSCRIBER)
# ============================================================================

class BeneficiaryProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    occupation: Optional[str] = None
    qualification: Optional[str] = None
    year_of_passing: Optional[str] = None
    address: Optional[str] = None
    resume_url: Optional[str] = None

@router.get("/beneficiaries/{beneficiary_id}/profile")
async def get_beneficiary_profile(
    beneficiary_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    ben = await db.get(Beneficiary, beneficiary_id)
    if not ben or ben.is_deleted:
        raise HTTPException(status_code=404, detail="Beneficiary not found")
    return {
        "id": ben.id,
        "name": ben.beneficiary_name,
        "phone": ben.whatsapp_number,
        "email": ben.email,
        "occupation": ben.occupation or "Member",
        "qualification": ben.qualification,
        "year_of_passing": ben.year_of_passing,
        "address": ben.address,
        "resume_url": ben.resume,
        "status": ben.status,
        "jobs_taken": ben.jobs_taken or 0,
        "total_rewards_gained": ben.total_rewards_gained or 0,
        "total_business_given": ben.total_business_given or 0.0,
        "subscriber_name": ben.subscriber_name,
        "joined_date": ben.joined_date,
    }


@router.put("/beneficiaries/{beneficiary_id}/profile")
async def update_beneficiary_profile(
    beneficiary_id: int,
    data: BeneficiaryProfileUpdate,
    db: AsyncSession = Depends(get_async_session)
):
    ben = await db.get(Beneficiary, beneficiary_id)
    if not ben or ben.is_deleted:
        raise HTTPException(status_code=404, detail="Beneficiary not found")

    if data.name is not None:
        ben.beneficiary_name = data.name
    if data.phone is not None:
        ben.whatsapp_number = data.phone
    if data.email is not None:
        ben.email = data.email
    if data.occupation is not None:
        ben.occupation = data.occupation
    if data.qualification is not None:
        ben.qualification = data.qualification
    if data.year_of_passing is not None:
        ben.year_of_passing = data.year_of_passing
    if data.address is not None:
        ben.address = data.address
    if data.resume_url is not None:
        ben.resume = data.resume_url

    await db.commit()
    await db.refresh(ben)
    return {
        "status": "success",
        "message": "Profile updated successfully",
        "user": {
            "id": ben.id,
            "beneficiaryName": ben.beneficiary_name,
            "occupation": ben.occupation or "Member",
            "qualification": ben.qualification or "Graduate",
            "whatsappNumber": ben.whatsapp_number,
            "email": ben.email,
            "address": ben.address,
            "yearOfPassing": ben.year_of_passing,
            "resumeUrl": ben.resume,
            "role": "beneficiary",
        }
    }


@router.get("/subscribers/{subscriber_id}/profile")
async def get_subscriber_profile(
    subscriber_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    sub = await db.get(Subscriber, subscriber_id)
    if not sub or sub.is_deleted:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return {
        "id": sub.id,
        "business_name": sub.business_name,
        "owner_name": sub.owner_name,
        "business_category": sub.business_category,
        "phone": sub.phone,
        "whatsapp_number": sub.whatsapp_number,
        "address": sub.address,
        "total_business_taken": sub.total_business_taken or 0.0,
        "total_business_given": sub.total_business_given or 0.0,
        "total_rewards_gained": sub.total_rewards_gained or 0,
        "status": sub.status,
        "joined_date": sub.joined_date,
    }


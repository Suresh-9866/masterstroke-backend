from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_async_session
from ..deps.auth import require_role
from ..models.user_profile import UserProfile
from ..models.audit_log import AuditLog
from ..services import keycloak_admin
from ..services.audit import log_audit

router = APIRouter(prefix="/admin", tags=["admin"])

class UserOut(BaseModel):
    id: str
    keycloak_sub: str
    role: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None
    deleted_reason: Optional[str] = None

    class Config:
        from_attributes = True

class DeleteUserIn(BaseModel):
    reason: str

class AuditLogOut(BaseModel):
    id: str
    actor_sub: str
    actor_role: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    extra_data: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("/users", response_model=list[UserOut])
async def list_users(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    role: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    payload: dict = Depends(require_role("admin")),
):
    if page_size > 100:
        page_size = 100
    stmt = select(UserProfile).where(UserProfile.status != "deleted")
    if role:
        stmt = stmt.where(UserProfile.role == role)
    if search:
        stmt = stmt.where(
            or_(
                UserProfile.phone_number.ilike(f"%{search}%"),
                UserProfile.email.ilike(f"%{search}%"),
                UserProfile.full_name.ilike(f"%{search}%"),
            )
        )
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.patch("/users/{id}/suspend")
async def suspend_user(id: str, payload: dict = Depends(require_role("admin")), db: AsyncSession = Depends(get_async_session)):
    stmt = select(UserProfile).where(UserProfile.id == id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.status = "suspended"
    await db.commit()
    await keycloak_admin.set_user_enabled(user.keycloak_sub, False)
    await log_audit(
        db,
        payload.get("sub"),
        ",".join(payload.get("realm_access", {}).get("roles", [])),
        "SUSPEND_USER",
        "user_profile",
        str(user.id),
        None,
    )
    return {"status": "suspended"}

@router.delete("/users/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(id: str, body: DeleteUserIn, payload: dict = Depends(require_role("admin")), db: AsyncSession = Depends(get_async_session)):
    stmt = select(UserProfile).where(UserProfile.id == id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.status = "deleted"
    user.deleted_at = datetime.utcnow()
    user.deleted_by = payload.get("sub")
    user.deleted_reason = body.reason
    await db.commit()
    await keycloak_admin.set_user_enabled(user.keycloak_sub, False)
    await log_audit(
        db,
        payload.get("sub"),
        ",".join(payload.get("realm_access", {}).get("roles", [])),
        "DELETE_USER",
        "user_profile",
        str(user.id),
        {"reason": body.reason},
    )
    return

@router.get("/users/deleted", response_model=list[UserOut])
async def deleted_users(page: int = 1, page_size: int = 20, payload: dict = Depends(require_role("admin")), db: AsyncSession = Depends(get_async_session)):
    if page_size > 100:
        page_size = 100
    stmt = select(UserProfile).where(UserProfile.status == "deleted").offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/users/{id}/restore")
async def restore_user(id: str, payload: dict = Depends(require_role("admin")), db: AsyncSession = Depends(get_async_session)):
    stmt = select(UserProfile).where(UserProfile.id == id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.status = "active"
    user.deleted_at = None
    user.deleted_by = None
    user.deleted_reason = None
    await db.commit()
    await keycloak_admin.set_user_enabled(user.keycloak_sub, True)
    await log_audit(
        db,
        payload.get("sub"),
        ",".join(payload.get("realm_access", {}).get("roles", [])),
        "RESTORE_USER",
        "user_profile",
        str(user.id),
        None,
    )
    return {"status": "restored"}

@router.get("/audit-logs", response_model=list[AuditLogOut])
async def audit_logs(
    page: int = 1,
    page_size: int = 20,
    actor_sub: Optional[str] = None,
    action: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    payload: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    if page_size > 100:
        page_size = 100
    stmt = select(AuditLog)
    if actor_sub:
        stmt = stmt.where(AuditLog.actor_sub == actor_sub)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= date_to)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    return result.scalars().all()


# System settings storage for admin configurations
system_settings = {
    "hero_banner_url": "/images/ad1.jpg"
}

class HeroBannerUpdate(BaseModel):
    hero_banner_url: str

@router.get("/hero-banner")
async def get_hero_banner():
    return {"hero_banner_url": system_settings.get("hero_banner_url", "/images/ad1.jpg")}

@router.post("/hero-banner")
async def update_hero_banner(body: HeroBannerUpdate):
    system_settings["hero_banner_url"] = body.hero_banner_url
    return {"hero_banner_url": system_settings["hero_banner_url"], "message": "Hero banner updated successfully"}

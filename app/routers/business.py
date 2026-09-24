from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..database import get_async_session
from ..deps.auth import require_role, decode_token, get_optional_payload
from ..models.business import Business
from ..models.category import Category
from ..models.media import BusinessMedia
from ..services.audit import log_audit
from ..services.storage import get_file_url, save_file
from ..utils.geo import build_maps_url, validate_lat_lng

settings = Settings()
router = APIRouter(prefix="/businesses", tags=["businesses"])

class BusinessCreate(BaseModel):
    category_id: int
    business_name: str
    short_description: Optional[str] = None
    detailed_description: Optional[str] = None
    mobile_number: str
    email: Optional[str] = None
    landline_number: Optional[str] = None
    website: Optional[str] = None
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    pincode: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    business_timings: Optional[str] = None

class BusinessUpdate(BaseModel):
    category_id: Optional[int] = None
    business_name: Optional[str] = None
    short_description: Optional[str] = None
    detailed_description: Optional[str] = None
    mobile_number: Optional[str] = None
    email: Optional[str] = None
    landline_number: Optional[str] = None
    website: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    business_timings: Optional[str] = None

class BusinessOut(BaseModel):
    id: str
    owner_sub: str
    category_id: int
    business_name: str
    short_description: Optional[str] = None
    detailed_description: Optional[str] = None
    mobile_number: str
    email: Optional[str] = None
    city: str
    state: str
    pincode: str
    status: str
    is_featured: bool
    created_at: datetime

    class Config:
        from_attributes = True

class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str

    class Config:
        from_attributes = True

class MediaOut(BaseModel):
    id: str
    media_type: str
    file_path: str

    class Config:
        from_attributes = True

class BusinessDetailOut(BaseModel):
    id: str
    owner_sub: str
    category: CategoryOut
    business_name: str
    short_description: Optional[str] = None
    detailed_description: Optional[str] = None
    mobile_number: str
    email: Optional[str] = None
    landline_number: Optional[str] = None
    website: Optional[str] = None
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    pincode: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    google_maps_url: Optional[str] = None
    business_timings: Optional[str] = None
    status: str
    rejection_reason: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    is_featured: bool
    media: list[MediaOut]

    class Config:
        from_attributes = True

class RejectIn(BaseModel):
    reason: str

class MediaUploadIn(BaseModel):
    media_type: str


from ..deps.auth import require_role, decode_token

@router.post("", status_code=status.HTTP_201_CREATED, response_model=BusinessOut)
async def create_business(data: BusinessCreate, payload: dict = Depends(require_role("business")), db: AsyncSession = Depends(get_async_session)):
    if data.latitude is not None and data.longitude is not None and not validate_lat_lng(data.latitude, data.longitude):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid latitude or longitude")
    category = await db.get(Category, data.category_id)
    if not category or not category.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    business = Business(
        owner_sub=payload.get("sub"),
        category_id=data.category_id,
        business_name=data.business_name.strip(),
        short_description=data.short_description,
        detailed_description=data.detailed_description,
        mobile_number=data.mobile_number,
        email=data.email,
        landline_number=data.landline_number,
        website=data.website,
        address_line1=data.address_line1,
        address_line2=data.address_line2,
        city=data.city,
        state=data.state,
        pincode=data.pincode,
        latitude=data.latitude,
        longitude=data.longitude,
        business_timings=data.business_timings,
        status="pending",
    )
    db.add(business)
    await db.commit()
    await db.refresh(business)
    await log_audit(
        db,
        payload.get("sub"),
        ",".join(payload.get("realm_access", {}).get("roles", [])),
        "SUBMIT_BUSINESS",
        "business",
        str(business.id),
        None,
    )
    return business

@router.patch("/{id}", response_model=BusinessOut)
async def update_business(id: str, data: BusinessUpdate, payload: dict = Depends(require_role("business")), db: AsyncSession = Depends(get_async_session)):
    stmt = select(Business).where(Business.id == id)
    result = await db.execute(stmt)
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    if business.owner_sub != payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit this listing")
    if business.status == "approved":
        business.status = "pending"
    if data.category_id is not None:
        category = await db.get(Category, data.category_id)
        if not category or not category.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        business.category_id = data.category_id
    for field in [
        "business_name",
        "short_description",
        "detailed_description",
        "mobile_number",
        "email",
        "landline_number",
        "website",
        "address_line1",
        "address_line2",
        "city",
        "state",
        "pincode",
        "latitude",
        "longitude",
        "business_timings",
    ]:
        value = getattr(data, field)
        if value is not None:
            setattr(business, field, value)
    if business.latitude is not None and business.longitude is not None and not validate_lat_lng(business.latitude, business.longitude):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid latitude or longitude")
    await db.commit()
    await db.refresh(business)
    return business

@router.get("", response_model=list[BusinessOut])
async def list_businesses(
    page: int = 1,
    page_size: int = 20,
    category_id: Optional[int] = None,
    city: Optional[str] = None,
    search: Optional[str] = None,
    is_featured: Optional[bool] = None,
    sort: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
):
    if page_size > 100:
        page_size = 100
    stmt = select(Business).where(Business.status == "approved")
    if category_id is not None:
        stmt = stmt.where(Business.category_id == category_id)
    if city:
        stmt = stmt.where(Business.city.ilike(f"%{city}%"))
    if search:
        stmt = stmt.where(or_(Business.business_name.ilike(f"%{search}%"), Business.short_description.ilike(f"%{search}%"), Business.detailed_description.ilike(f"%{search}%")))
    if is_featured is not None:
        stmt = stmt.where(Business.is_featured == is_featured)
    if sort == "newest":
        stmt = stmt.order_by(Business.created_at.desc())
    else:
        stmt = stmt.order_by(Business.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{id}")
async def get_business(id: str, payload: Optional[dict] = Depends(get_optional_payload), db: AsyncSession = Depends(get_async_session)):
    stmt = select(Business).where(Business.id == id)
    result = await db.execute(stmt)
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    allowed = business.status == "approved"
    if not allowed and payload is not None:
        roles = payload.get("realm_access", {}).get("roles", [])
        if payload.get("sub") == business.owner_sub or "admin" in roles:
            allowed = True
    if not allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    category = await db.get(Category, business.category_id)
    media_stmt = select(BusinessMedia).where(BusinessMedia.business_id == business.id)
    media_result = await db.execute(media_stmt)
    media = media_result.scalars().all()
    media_list = [MediaOut.from_orm(item) for item in media]
    google_maps_url = None
    if business.latitude is not None and business.longitude is not None:
        google_maps_url = build_maps_url(business.latitude, business.longitude)
    return {
        "id": str(business.id),
        "owner_sub": business.owner_sub,
        "category": CategoryOut.from_orm(category) if category else None,
        "business_name": business.business_name,
        "short_description": business.short_description,
        "detailed_description": business.detailed_description,
        "mobile_number": business.mobile_number,
        "email": business.email,
        "landline_number": business.landline_number,
        "website": business.website,
        "address_line1": business.address_line1,
        "address_line2": business.address_line2,
        "city": business.city,
        "state": business.state,
        "pincode": business.pincode,
        "latitude": business.latitude,
        "longitude": business.longitude,
        "google_maps_url": google_maps_url,
        "business_timings": business.business_timings,
        "status": business.status,
        "rejection_reason": business.rejection_reason,
        "approved_by": business.approved_by,
        "approved_at": business.approved_at,
        "is_featured": business.is_featured,
        "media": media_list,
    }

@router.patch("/{id}/approve")
async def approve_business(id: str, payload: dict = Depends(require_role("admin")), db: AsyncSession = Depends(get_async_session)):
    stmt = select(Business).where(Business.id == id)
    result = await db.execute(stmt)
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    business.status = "approved"
    business.approved_by = payload.get("sub")
    business.approved_at = datetime.utcnow()
    await db.commit()
    await log_audit(
        db,
        payload.get("sub"),
        ",".join(payload.get("realm_access", {}).get("roles", [])),
        "APPROVE_BUSINESS",
        "business",
        str(business.id),
        None,
    )
    return {"status": "approved"}

@router.patch("/{id}/reject")
async def reject_business(id: str, reject: RejectIn, payload: dict = Depends(require_role("admin")), db: AsyncSession = Depends(get_async_session)):
    stmt = select(Business).where(Business.id == id)
    result = await db.execute(stmt)
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    business.status = "rejected"
    business.rejection_reason = reject.reason
    await db.commit()
    await log_audit(
        db,
        payload.get("sub"),
        ",".join(payload.get("realm_access", {}).get("roles", [])),
        "REJECT_BUSINESS",
        "business",
        str(business.id),
        {"reason": reject.reason},
    )
    return {"status": "rejected"}

@router.post("/{id}/media", status_code=status.HTTP_201_CREATED)
async def upload_business_media(
    id: str,
    media_type: str = Form(...),
    file: UploadFile = File(...),
    payload: dict = Depends(decode_token),
    db: AsyncSession = Depends(get_async_session),
):
    stmt = select(Business).where(Business.id == id)
    result = await db.execute(stmt)
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    roles = payload.get("realm_access", {}).get("roles", [])
    if payload.get("sub") != business.owner_sub and "admin" not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    allowed_types = {"logo": 1, "cover_photo": 1, "gallery_image": 10, "video": 1}
    if media_type not in allowed_types:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported media type")
    current_count = await db.execute(select(BusinessMedia).where(BusinessMedia.business_id == business.id, BusinessMedia.media_type == media_type))
    count = len(current_count.scalars().all())
    if count >= allowed_types[media_type]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Maximum {allowed_types[media_type]} {media_type} file(s) allowed")
    content_type = file.content_type or ""
    image_types = {"image/jpeg", "image/png"}
    video_types = {"video/mp4"}
    if media_type in ["logo", "cover_photo", "gallery_image"] and content_type not in image_types:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid image type")
    if media_type == "video" and content_type not in video_types:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid video type")
    data = await file.read()
    max_mb = settings.MAX_IMAGE_SIZE_MB if media_type != "video" else settings.MAX_VIDEO_SIZE_MB
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"File exceeds maximum size of {max_mb} MB")
    saved_path = save_file(data, file.filename, subdir=str(business.id))
    url = get_file_url(saved_path)
    media = BusinessMedia(business_id=business.id, media_type=media_type, file_path=url, uploaded_by=payload.get("sub"))
    db.add(media)
    await db.commit()
    await db.refresh(media)
    return {"id": str(media.id), "media_type": media.media_type, "file_path": media.file_path}

@router.delete("/{id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_business_media(id: str, media_id: str, payload: dict = Depends(decode_token), db: AsyncSession = Depends(get_async_session)):
    stmt = select(Business).where(Business.id == id)
    result = await db.execute(stmt)
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    roles = payload.get("realm_access", {}).get("roles", [])
    if payload.get("sub") != business.owner_sub and "admin" not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    media_stmt = select(BusinessMedia).where(BusinessMedia.id == media_id, BusinessMedia.business_id == business.id)
    media_result = await db.execute(media_stmt)
    media = media_result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    from pathlib import Path
    from ..config import Settings as ConfigSettings

    settings = ConfigSettings()
    if media.file_path.startswith("/media/"):
        local_path = Path(settings.MEDIA_ROOT) / media.file_path[len("/media/"):]
        if local_path.exists():
            local_path.unlink()
    await db.delete(media)
    await db.commit()
    return

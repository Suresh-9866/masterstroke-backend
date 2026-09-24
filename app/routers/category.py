from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..database import get_async_session
from ..deps.auth import require_role, decode_token
from ..models.category import Category
from ..services.audit import log_audit

router = APIRouter(prefix="/categories", tags=["categories"])

class CategoryCreate(BaseModel):
    name: str
    slug: str
    icon_url: str | None = None
    parent_id: int | None = None

class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    icon_url: str | None
    parent_id: int | None

    class Config:
        from_attributes = True

@router.get("", response_model=list[CategoryOut])
async def list_categories(page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_async_session)):
    if page_size > 100:
        page_size = 100
    stmt = select(Category).where(Category.is_active == True).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    categories = result.scalars().all()
    return categories

@router.post("", status_code=status.HTTP_201_CREATED, response_model=CategoryOut)
async def create_category(data: CategoryCreate, payload: dict = Depends(require_role("admin")), db: AsyncSession = Depends(get_async_session)):
    category = Category(
        name=data.name.strip(),
        slug=data.slug.strip(),
        icon_url=data.icon_url,
        parent_id=data.parent_id,
        created_by=payload.get("sub"),
    )
    db.add(category)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category name or slug already exists")
    await db.refresh(category)
    await log_audit(
        db,
        payload.get("sub"),
        ",".join(payload.get("realm_access", {}).get("roles", [])),
        "CREATE_CATEGORY",
        "category",
        str(category.id),
        {"name": category.name},
    )
    return category

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(id: int, payload: dict = Depends(require_role("admin")), db: AsyncSession = Depends(get_async_session)):
    stmt = select(Category).where(Category.id == id, Category.is_active == True)
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    category.is_active = False
    await db.commit()
    await log_audit(
        db,
        payload.get("sub"),
        ",".join(payload.get("realm_access", {}).get("roles", [])),
        "DELETE_CATEGORY",
        "category",
        str(category.id),
        None,
    )
    return

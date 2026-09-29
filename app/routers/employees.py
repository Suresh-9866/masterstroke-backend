from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, String
from typing import List, Optional
from datetime import datetime

from ..database import get_async_session
from ..models.user_profile import UserProfile

router = APIRouter(prefix="/employees", tags=["employees"])


class EmployeeCreate(BaseModel):
    full_name: str
    username: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    password: str
    role: Optional[str] = "employee"
    status: Optional[str] = "active"


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


class EmployeeOut(BaseModel):
    id: str
    full_name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    role: str
    status: str
    created_at: Optional[datetime] = None


@router.get("/", response_model=List[EmployeeOut])
async def list_employees(db: AsyncSession = Depends(get_async_session)):
    """List all employee and admin profiles from database."""
    role_col = cast(UserProfile.role, String)
    status_col = cast(UserProfile.status, String)
    stmt = select(UserProfile).where(
        (role_col.in_(["employee", "admin"])) & 
        ((status_col != "deleted") | (UserProfile.status.is_(None)))
    ).order_by(UserProfile.created_at.desc())
    res = await db.execute(stmt)
    users = res.scalars().all()
    out = []
    for u in users:
        u_role = u.role.value if hasattr(u.role, "value") else str(u.role or "employee")
        u_status = u.status.value if hasattr(u.status, "value") else str(u.status or "active")
        out.append(
            EmployeeOut(
                id=str(u.id),
                full_name=u.full_name or u.username or "Employee",
                username=u.username,
                email=u.email,
                phone_number=u.phone_number,
                role=u_role,
                status=u_status,
                created_at=u.created_at,
            )
        )
    return out


@router.post("/", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(data: EmployeeCreate, db: AsyncSession = Depends(get_async_session)):
    """Creates a new employee profile with credentials for system login."""
    if data.username:
        stmt = select(UserProfile).where(UserProfile.username == data.username)
        res = await db.execute(stmt)
        if res.scalars().first():
            raise HTTPException(status_code=400, detail=f"Username '{data.username}' is already taken.")

    if data.email:
        stmt = select(UserProfile).where(UserProfile.email == data.email)
        res = await db.execute(stmt)
        if res.scalars().first():
            raise HTTPException(status_code=400, detail=f"Email address '{data.email}' is already registered.")

    if data.phone_number:
        stmt = select(UserProfile).where(UserProfile.phone_number == data.phone_number)
        res = await db.execute(stmt)
        if res.scalars().first():
            raise HTTPException(status_code=400, detail=f"Phone number '{data.phone_number}' is already registered.")

    user = UserProfile(
        full_name=data.full_name,
        username=data.username,
        email=data.email,
        phone_number=data.phone_number,
        password_hash=data.password,
        role=data.role or "employee",
        status=data.status or "active",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return EmployeeOut(
        id=str(user.id),
        full_name=user.full_name,
        username=user.username,
        email=user.email,
        phone_number=user.phone_number,
        role=user.role.value if hasattr(user.role, "value") else str(user.role or "employee"),
        status=user.status.value if hasattr(user.status, "value") else str(user.status or "active"),
        created_at=user.created_at,
    )


@router.put("/{employee_id}", response_model=EmployeeOut)
async def update_employee(employee_id: str, data: EmployeeUpdate, db: AsyncSession = Depends(get_async_session)):
    """Updates an existing employee profile."""
    stmt = select(UserProfile).where(cast(UserProfile.id, String) == str(employee_id))
    res = await db.execute(stmt)
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    if data.full_name is not None:
        user.full_name = data.full_name
    if data.username is not None:
        user.username = data.username
    if data.email is not None:
        user.email = data.email
    if data.phone_number is not None:
        user.phone_number = data.phone_number
    if data.password:
        user.password_hash = data.password
    if data.role is not None:
        user.role = data.role
    if data.status is not None:
        user.status = data.status

    await db.commit()
    await db.refresh(user)

    return EmployeeOut(
        id=str(user.id),
        full_name=user.full_name,
        username=user.username,
        email=user.email,
        phone_number=user.phone_number,
        role=user.role.value if hasattr(user.role, "value") else str(user.role or "employee"),
        status=user.status.value if hasattr(user.status, "value") else str(user.status or "active"),
        created_at=user.created_at,
    )


@router.delete("/{employee_id}")
async def delete_employee(employee_id: str, db: AsyncSession = Depends(get_async_session)):
    """Soft deletes an employee account."""
    stmt = select(UserProfile).where(cast(UserProfile.id, String) == str(employee_id))
    res = await db.execute(stmt)
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    user.status = "deleted"
    user.deleted_at = datetime.utcnow()
    await db.commit()
    return {"message": "Employee account soft deleted successfully"}


@router.post("/{employee_id}/restore")
async def restore_employee(employee_id: str, db: AsyncSession = Depends(get_async_session)):
    """Restores a soft-deleted employee account."""
    stmt = select(UserProfile).where(cast(UserProfile.id, String) == str(employee_id))
    res = await db.execute(stmt)
    user = res.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    user.status = "active"
    user.deleted_at = None
    await db.commit()
    return {"message": "Employee account restored successfully"}

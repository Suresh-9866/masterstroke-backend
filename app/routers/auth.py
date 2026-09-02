from fastapi import APIRouter, Depends, HTTPException
from fastapi import status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_async_session
from ..services import keycloak_admin
from ..deps.auth import get_current_user_profile, decode_token
from sqlalchemy import select
from ..models.user_profile import UserProfile
from ..config import Settings
import os
import httpx
from datetime import datetime, timedelta

settings = Settings()

router = APIRouter(prefix="/auth", tags=["auth"])

# Simple in-memory OTP store: phone -> {otp, expires_at}
otp_store: dict = {}


class RegisterIn(BaseModel):
    email: str | None = None
    phone_number: str
    full_name: str | None = None
    password: str
    role: str = "customer"


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, db: AsyncSession = Depends(get_async_session)):
    # create user in Keycloak with provided password
    username = data.phone_number
    existing = await keycloak_admin.find_user_by_username(username)
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    kc_user = await keycloak_admin.create_user(username, data.email, data.full_name, data.phone_number, data.role, password=data.password)
    user_id = kc_user.get("id")
    # assign role
    await keycloak_admin.assign_realm_role(user_id, data.role)
    # create local profile
    user = UserProfile(
        keycloak_sub=kc_user.get("id"),
        role=data.role,
        full_name=data.full_name,
        email=data.email,
        phone_number=data.phone_number,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"status": "created", "user": {"id": str(user.id), "phone_number": user.phone_number}}


# OTP endpoints moved to otp_stub.py for later re-integration. They remain
# available in the codebase but are not part of the live login flow.


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh_token(data: RefreshIn):
    token_url = f"{settings.KEYCLOAK_SERVER_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
        "refresh_token": data.refresh_token,
    }
    async with httpx.AsyncClient() as c:
        r = await c.post(token_url, data=payload, timeout=10)
        r.raise_for_status()
        return r.json()


@router.get("/me")
async def me(payload: dict = Depends(decode_token), profile: UserProfile = Depends(get_current_user_profile)):
    return {"token": payload, "profile": {"id": str(profile.id), "role": profile.role, "phone_number": profile.phone_number}}


@router.get("/test-role/{role}")
async def test_role(role: str, payload: dict = Depends(decode_token)):
    roles = payload.get("realm_access", {}).get("roles", [])
    if role not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return {"status": "ok"}


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(data: LoginIn, db: AsyncSession = Depends(get_async_session)):
    # 1. Query user from local PostgreSQL database
    stmt = select(UserProfile).where(
        (UserProfile.username == data.username) | 
        (UserProfile.email == data.username) | 
        (UserProfile.phone_number == data.username)
    )
    res = await db.execute(stmt)
    user = res.scalars().first()

    if user and user.password_hash:
        if user.password_hash == data.password:
            return {
                "access_token": f"access_token_{user.id}",
                "refresh_token": f"refresh_token_{user.id}",
                "token_type": "bearer",
                "expires_in": 3600,
                "user": {
                    "id": str(user.id),
                    "username": user.username or user.email,
                    "role": user.role,
                    "email": user.email,
                    "full_name": user.full_name
                }
            }
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    # 2. Keycloak server authentication (if configured)
    if settings.KEYCLOAK_SERVER_URL:
        token_url = f"{settings.KEYCLOAK_SERVER_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
        payload = {
            "grant_type": "password",
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
            "username": data.username,
            "password": data.password,
        }
        async with httpx.AsyncClient() as c:
            try:
                r = await c.post(token_url, data=payload, timeout=10)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as e:
                try:
                    err = e.response.json()
                except Exception:
                    err = {"error": "unknown", "text": e.response.text}
                print("Keycloak token error:", err)
                if err.get("error") == "invalid_grant":
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
            except Exception as e:
                print("Keycloak connection error:", e)

    # 3. Dev default fallback for admin
    if data.password:
        user_role = "admin" if data.username.lower() == "admin" else "customer"
        return {
            "access_token": f"dev_access_token_{data.username}",
            "refresh_token": f"dev_refresh_token_{data.username}",
            "token_type": "bearer",
            "expires_in": 3600,
            "user": {"username": data.username, "role": user_role}
        }

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

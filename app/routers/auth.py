from fastapi import APIRouter, Depends, HTTPException
from fastapi import status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_async_session
from ..services import keycloak_admin
from ..deps.auth import get_current_user_profile, decode_token
from sqlalchemy import select
from ..models.user_profile import UserProfile
from ..models.user_session import UserSession
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

    username_str = data.username
    full_name_str = data.username
    role_str = "customer"

    if user and user.password_hash:
        if user.password_hash == data.password:
            username_str = user.username or user.email or data.username
            full_name_str = user.full_name or username_str
            role_str = user.role or "customer"

            # Create UserSession record
            session_rec = UserSession(
                username=username_str,
                full_name=full_name_str,
                role=role_str,
                status="Active",
                login_time=datetime.utcnow()
            )
            db.add(session_rec)
            await db.commit()
            await db.refresh(session_rec)

            return {
                "access_token": f"access_token_{user.id}",
                "refresh_token": f"refresh_token_{user.id}",
                "token_type": "bearer",
                "expires_in": 3600,
                "session_id": session_rec.id,
                "user": {
                    "id": str(user.id),
                    "username": username_str,
                    "role": role_str,
                    "email": user.email,
                    "full_name": full_name_str
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
        full_name_val = "System Administrator" if user_role == "admin" else data.username

        session_rec = UserSession(
            username=data.username,
            full_name=full_name_val,
            role=user_role,
            status="Active",
            login_time=datetime.utcnow()
        )
        db.add(session_rec)
        await db.commit()
        await db.refresh(session_rec)

        return {
            "access_token": f"dev_access_token_{data.username}",
            "refresh_token": f"dev_refresh_token_{data.username}",
            "token_type": "bearer",
            "expires_in": 3600,
            "session_id": session_rec.id,
            "user": {"username": data.username, "full_name": full_name_val, "role": user_role}
        }

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")


class LogoutIn(BaseModel):
    session_id: int | None = None
    username: str | None = None


@router.post("/logout")
async def logout(data: LogoutIn, db: AsyncSession = Depends(get_async_session)):
    now = datetime.utcnow()

    if data.session_id:
        stmt = select(UserSession).where(UserSession.id == data.session_id)
        res = await db.execute(stmt)
        sess = res.scalars().first()
        if sess:
            sess.logout_time = now
            sess.status = "Logged Out"
            await db.commit()
            return {"status": "ok", "message": "Logged out successfully"}

    if data.username:
        stmt = select(UserSession).where(
            (UserSession.username == data.username) & (UserSession.status == "Active")
        ).order_by(UserSession.id.desc())
        res = await db.execute(stmt)
        sess = res.scalars().first()
        if sess:
            sess.logout_time = now
            sess.status = "Logged Out"
            await db.commit()
            return {"status": "ok", "message": "Logged out successfully"}

    return {"status": "ok", "message": "Logged out"}


@router.get("/login-history")
async def get_login_history(
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_async_session)
):
    stmt = select(UserSession).order_by(UserSession.login_time.desc())
    res = await db.execute(stmt)
    sessions = res.scalars().all()

    results = []
    for s in sessions:
        # Search filter
        if search:
            q = search.lower()
            u = (s.username or "").lower()
            fn = (s.full_name or "").lower()
            r = (s.role or "").lower()
            if q not in u and q not in fn and q not in r:
                continue

        # Date filter
        login_date_str = s.login_time.strftime("%Y-%m-%d") if s.login_time else ""
        if start_date and login_date_str < start_date:
            continue
        if end_date and login_date_str > end_date:
            continue

        login_iso = None
        if s.login_time:
            login_iso = s.login_time.isoformat()
            if not login_iso.endswith("Z") and "+" not in login_iso:
                login_iso += "Z"

        logout_iso = None
        if s.logout_time:
            logout_iso = s.logout_time.isoformat()
            if not logout_iso.endswith("Z") and "+" not in logout_iso:
                logout_iso += "Z"

        results.append({
            "id": s.id,
            "username": s.username,
            "full_name": s.full_name or s.username,
            "role": s.role or "user",
            "login_time": login_iso,
            "logout_time": logout_iso,
            "status": s.status or "Active",
        })

    return results


# In-memory store for forgot password OTPs: email -> {otp, expires_at}
forgot_password_otps: dict = {}


def send_email_otp(to_email: str, otp: str) -> tuple[bool, str]:
    to_email = to_email.strip()
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
        <h2 style="color: #0F4C81; margin-bottom: 5px;">WINGS Platform</h2>
        <p style="font-size: 14px; color: #555;">Account Password Reset Request</p>
        <div style="background-color: #F5FAFC; border: 1px solid #008080; padding: 15px; border-radius: 8px; font-size: 24px; font-weight: bold; color: #008080; letter-spacing: 5px; text-align: center; margin: 20px 0;">
            {otp}
        </div>
        <p style="font-size: 13px;">This verification code is valid for <strong>10 minutes</strong>.</p>
        <p style="color: #888; font-size: 12px; margin-top: 20px;">If you did not request this reset, please ignore this message.</p>
    </div>
    """

    # 1. Try Brevo HTTP API (Port 443 - Bypasses Render raw socket firewall)
    brevo_api_key = (os.getenv("BREVO_API_KEY") or os.getenv("SENDINBLUE_API_KEY") or "").strip()
    if brevo_api_key:
        try:
            print("Sending email via Brevo HTTP API (Port 443)...")
            sender_email = (os.getenv("SMTP_USER") or "wings.velloredigital@gmail.com").strip()
            payload = {
                "sender": {"name": "WINGS Platform", "email": sender_email},
                "to": [{"email": to_email}],
                "subject": "WINGS App - Password Reset Verification Code",
                "htmlContent": html_content
            }
            headers = {"api-key": brevo_api_key, "Content-Type": "application/json"}
            with httpx.Client(timeout=10.0) as client:
                r = client.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers)
                if r.status_code in (200, 201, 202):
                    print(f"Successfully sent OTP email to {to_email} via Brevo HTTP API")
                    return True, "OK"
                else:
                    print(f"Brevo HTTP API returned status {r.status_code}: {r.text}")
        except Exception as e:
            print(f"Brevo HTTP API attempt failed: {e}")

    # 2. Try Resend HTTP API (Port 443 - Bypasses Render raw socket firewall)
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
    if resend_api_key:
        try:
            print("Sending email via Resend HTTP API (Port 443)...")
            payload = {
                "from": os.getenv("EMAIL_FROM", "WINGS App <onboarding@resend.dev>").strip(),
                "to": [to_email],
                "subject": "WINGS App - Password Reset Verification Code",
                "html": html_content
            }
            headers = {"Authorization": f"Bearer {resend_api_key}", "Content-Type": "application/json"}
            with httpx.Client(timeout=10.0) as client:
                r = client.post("https://api.resend.com/emails", json=payload, headers=headers)
                if r.status_code in (200, 201, 202):
                    print(f"Successfully sent OTP email to {to_email} via Resend HTTP API")
                    return True, "OK"
                else:
                    print(f"Resend HTTP API returned status {r.status_code}: {r.text}")
        except Exception as e:
            print(f"Resend HTTP API attempt failed: {e}")

    # 3. Standard SMTP via smtplib (Fallback for Local Dev or Unblocked Hosts)
    smtp_server = (os.getenv("SMTP_SERVER") or settings.SMTP_SERVER or "smtp.gmail.com").strip()
    smtp_port_val = os.getenv("SMTP_PORT") or settings.SMTP_PORT or 465
    smtp_port = int(str(smtp_port_val).strip())
    smtp_user = (os.getenv("SMTP_USER") or settings.SMTP_USER or "").strip()
    smtp_password = (os.getenv("SMTP_PASSWORD") or settings.SMTP_PASSWORD or "").strip()
    
    if not smtp_server or not smtp_user or not smtp_password:
        msg = f"Missing SMTP config (server='{smtp_server}', user='{smtp_user}', password_set={bool(smtp_password)})"
        print(msg)
        return False, msg

    last_err = "Unknown error"
    try:
        import smtplib
        import ssl
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "WINGS App - Password Reset Verification Code"
        msg["From"] = f"WINGS App <{smtp_user}>"
        msg["To"] = to_email
        
        text = f"Your WINGS account password reset verification code is: {otp}\nThis code is valid for 10 minutes."
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html_content, "html"))
        
        # Try SSL Port 465 with default SSL context
        try:
            print(f"Connecting via SMTP_SSL (default ctx) to {smtp_server}:465...")
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_server, 465, context=context, timeout=12) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, to_email, msg.as_string())
            print(f"Successfully sent OTP email to {to_email} via Port 465 SSL")
            return True, "OK"
        except Exception as e:
            last_err = f"Port 465 SSL default ctx failed: {e}"
            print(last_err)

        # Fallback: Try SSL Port 465 with unverified context
        try:
            print(f"Connecting via SMTP_SSL (unverified ctx) to {smtp_server}:465...")
            unverified_ctx = ssl._create_unverified_context()
            with smtplib.SMTP_SSL(smtp_server, 465, context=unverified_ctx, timeout=12) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, to_email, msg.as_string())
            print(f"Successfully sent OTP email to {to_email} via Port 465 SSL (unverified context)")
            return True, "OK"
        except Exception as e:
            last_err = f"Port 465 SSL unverified ctx failed: {e}"
            print(last_err)

        # Try STARTTLS on configured port (e.g. Port 587)
        if smtp_port != 465:
            try:
                print(f"Connecting via STARTTLS to {smtp_server}:{smtp_port}...")
                context = ssl.create_default_context()
                with smtplib.SMTP(smtp_server, smtp_port, timeout=8) as server:
                    server.starttls(context=context)
                    server.login(smtp_user, smtp_password)
                    server.sendmail(smtp_user, to_email, msg.as_string())
                print(f"Successfully sent OTP email to {to_email} via Port {smtp_port}")
                return True, "OK"
            except Exception as e:
                last_err = f"Port {smtp_port} STARTTLS failed: {e}"
                print(last_err)

        return False, last_err
    except Exception as e:
        last_err = f"General SMTP error: {e}"
        print(last_err)
        return False, last_err


class ForgotPasswordRequestIn(BaseModel):
    email: str


@router.post("/forgot-password/request")
async def forgot_password_request(data: ForgotPasswordRequestIn, db: AsyncSession = Depends(get_async_session)):
    email = data.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    # Verify user exists in PostgreSQL user_profile table
    stmt = select(UserProfile).where(
        (UserProfile.email.ilike(email)) |
        (UserProfile.username.ilike(email))
    )
    res = await db.execute(stmt)
    user = res.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail=f"No account found registered with '{email}'")

    # Generate 6-digit OTP
    otp = "%06d" % (int(datetime.utcnow().timestamp()) % 1000000)
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    forgot_password_otps[email] = {"otp": otp, "expires_at": expires_at}
    
    print(f"Forgot password OTP for {email}: {otp}")
    
    # Try sending real email via SMTP
    email_sent, err_detail = send_email_otp(email, otp)
    
    if not email_sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email via SMTP ({err_detail}). Please verify server SMTP configuration."
        )
        
    return {
        "status": "ok",
        "message": f"Verification code sent to {email}"
    }


class ForgotPasswordVerifyIn(BaseModel):
    email: str
    otp: str


@router.post("/forgot-password/verify-otp")
async def forgot_password_verify_otp(data: ForgotPasswordVerifyIn):
    email = data.email.strip().lower()
    entry = forgot_password_otps.get(email)
    if not entry:
        raise HTTPException(status_code=400, detail="No OTP requested for this email")
    
    if entry.get("otp") != data.otp.strip():
        raise HTTPException(status_code=400, detail="Invalid OTP code")
        
    if entry.get("expires_at") < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
        
    return {"status": "ok", "message": "OTP verified successfully"}


class ForgotPasswordResetIn(BaseModel):
    email: str
    otp: str
    new_password: str


@router.post("/forgot-password/reset")
async def forgot_password_reset(data: ForgotPasswordResetIn, db: AsyncSession = Depends(get_async_session)):
    email = data.email.strip().lower()
    entry = forgot_password_otps.get(email)
    
    if not entry or entry.get("otp") != data.otp.strip() or entry.get("expires_at") < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP session")
        
    # Update password in local PostgreSQL UserProfile database
    stmt = select(UserProfile).where(
        (UserProfile.email == email) |
        (UserProfile.username == email)
    )
    res = await db.execute(stmt)
    user = res.scalars().first()
    
    if user:
        user.password_hash = data.new_password
        user.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(user)
    
    # Also update Keycloak user password if Keycloak is configured
    if settings.KEYCLOAK_SERVER_URL:
        try:
            kc_user = await keycloak_admin.find_user_by_username(email)
            if kc_user and kc_user.get("id"):
                await keycloak_admin.set_user_password(kc_user.get("id"), data.new_password)
        except Exception as exc:
            print("Failed to update Keycloak password:", exc)
            
    # Clear used OTP
    forgot_password_otps.pop(email, None)
    return {"status": "ok", "message": "Password updated successfully"}


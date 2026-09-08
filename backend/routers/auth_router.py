from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import secrets
import json

from database import get_db
from models import User, RefreshSession, AuditLog, RoleEnum, AccountStatusEnum
from security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    hash_token,
    decode_jwt_token,
    generate_totp_secret,
    get_totp_uri,
    verify_totp_code,
    generate_recovery_codes,
    verify_and_consume_recovery_code,
    get_client_ip,
)
from rate_limiter import limiter

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        ...,
        min_length=12,
        description="Password must be at least 12 characters"
    )
    full_name: str
    badge_number: Optional[str] = None
    unit: Optional[str] = None
    requested_role: Optional[str] = RoleEnum.CONSTABLE


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: Optional[str] = None


class TwoFASetupResponse(BaseModel):
    secret: str
    otpauth_url: str
    recovery_codes: list[str]


class TwoFAVerifyRequest(BaseModel):
    code: str


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def is_https_request(request: Request) -> bool:
    """
    Determine whether the original client request used HTTPS.

    Render terminates HTTPS at its proxy, so check X-Forwarded-Proto
    first and fall back to request.url.scheme.
    """
    forwarded_proto = request.headers.get("x-forwarded-proto")

    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() == "https"

    return request.url.scheme.lower() == "https"


def get_cookie_settings(request: Request) -> dict:
    """
    Configure cookies for both local development and deployed
    Vercel -> Render cross-site authentication.

    Production / HTTPS:
        SameSite=None
        Secure=True

    Local HTTP:
        SameSite=Lax
        Secure=False
    """
    secure = is_https_request(request)

    return {
        "httponly": True,
        "samesite": "none" if secure else "lax",
        "secure": secure,
        "path": "/",
    }


# ------------------------------------------------------------------
# Current user dependency
# ------------------------------------------------------------------

def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user from access_token cookie or Authorization header.
    """

    token = request.cookies.get("access_token")

    if not token:
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    payload = decode_jwt_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token"
        )

    user_id = payload.get("sub")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if user.account_status != AccountStatusEnum.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.account_status.lower()}"
        )

    return user


# ------------------------------------------------------------------
# Signup
# ------------------------------------------------------------------

@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED
)
def signup(
    req_data: SignupRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    limiter.check_rate_limit(
        request,
        "signup",
        max_requests=10,
        window_seconds=60
    )

    if len(req_data.password) < 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 12 characters long"
        )

    existing = (
        db.query(User)
        .filter(User.email == req_data.email)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    assigned_role = (
        req_data.requested_role
        if req_data.requested_role in RoleEnum.hierarchy()
        else RoleEnum.CONSTABLE
    )

    new_user = User(
        email=req_data.email,
        full_name=req_data.full_name,
        badge_number=req_data.badge_number,
        unit=req_data.unit,
        password_hash=hash_password(req_data.password),
        role=assigned_role,
        account_status=AccountStatusEnum.PENDING
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    audit = AuditLog(
        user_id=new_user.id,
        role=new_user.role,
        action="ACCOUNT_CREATED",
        resource_type="USER",
        resource_id=str(new_user.id),
        result="SUCCESS",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent")
    )

    db.add(audit)
    db.commit()

    return {
        "message": (
            "Account created successfully. "
            "Your account is pending approval by a senior officer."
        ),
        "user_id": new_user.id,
        "account_status": new_user.account_status
    }


# ------------------------------------------------------------------
# Login
# ------------------------------------------------------------------

@router.post("/login")
def login(
    req_data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    limiter.check_rate_limit(
        request,
        "login",
        max_requests=10,
        window_seconds=60
    )

    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials or account access restricted."
    )

    user = (
        db.query(User)
        .filter(User.email == req_data.email)
        .first()
    )

    if not user:
        audit = AuditLog(
            action="LOGIN_FAILED",
            result="FAILURE",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            metadata_json=json.dumps({
                "reason": "Invalid credentials"
            })
        )

        db.add(audit)
        db.commit()

        raise generic_error

    now = datetime.now(timezone.utc)

    # --------------------------------------------------------------
    # Brute-force lockout
    # --------------------------------------------------------------

    if user.locked_until and user.locked_until > now:
        audit = AuditLog(
            user_id=user.id,
            role=user.role,
            action="LOGIN_FAILED",
            result="FAILURE",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            metadata_json=json.dumps({
                "reason": "Account locked"
            })
        )

        db.add(audit)
        db.commit()

        raise generic_error

    # --------------------------------------------------------------
    # Password verification
    # --------------------------------------------------------------

    if not verify_password(
        req_data.password,
        user.password_hash
    ):
        user.failed_login_attempts += 1

        if user.failed_login_attempts >= 5:
            user.locked_until = (
                now + timedelta(minutes=15)
            )

            lock_audit = AuditLog(
                user_id=user.id,
                role=user.role,
                action="ACCOUNT_LOCKED",
                result="FAILURE",
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("User-Agent"),
                metadata_json=json.dumps({
                    "reason": (
                        "5 consecutive failed login attempts"
                    )
                })
            )

            db.add(lock_audit)

        fail_audit = AuditLog(
            user_id=user.id,
            role=user.role,
            action="LOGIN_FAILED",
            result="FAILURE",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )

        db.add(fail_audit)
        db.commit()

        raise generic_error

    # --------------------------------------------------------------
    # Account status
    # --------------------------------------------------------------

    if user.account_status != AccountStatusEnum.ACTIVE:
        status_audit = AuditLog(
            user_id=user.id,
            role=user.role,
            action="LOGIN_FAILED",
            result="DENIED",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            metadata_json=json.dumps({
                "reason": f"Account status {user.account_status}"
            })
        )

        db.add(status_audit)
        db.commit()

        raise generic_error

    # --------------------------------------------------------------
    # MFA
    # --------------------------------------------------------------

    if user.mfa_enabled:
        totp_code = req_data.totp_code

        if not totp_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="MFA_REQUIRED"
            )

        mfa_valid = verify_totp_code(
            user.mfa_secret,
            totp_code
        )

        if not mfa_valid:
            recovery_valid, new_recovery_json = (
                verify_and_consume_recovery_code(
                    totp_code,
                    user.recovery_codes_hash
                )
            )

            if recovery_valid:
                user.recovery_codes_hash = new_recovery_json
                mfa_valid = True

        if not mfa_valid:
            mfa_audit = AuditLog(
                user_id=user.id,
                role=user.role,
                action="MFA_FAILED",
                result="FAILURE",
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("User-Agent")
            )

            db.add(mfa_audit)
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA code"
            )

    # --------------------------------------------------------------
    # Reset login failure state
    # --------------------------------------------------------------

    user.failed_login_attempts = 0
    user.locked_until = None

    # --------------------------------------------------------------
    # Issue tokens
    # --------------------------------------------------------------

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role
    })

    raw_refresh_token, refresh_hash = create_refresh_token()

    session_obj = RefreshSession(
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        expires_at=now + timedelta(days=7),
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent")
    )

    db.add(session_obj)

    # --------------------------------------------------------------
    # Audit login success
    # --------------------------------------------------------------

    success_audit = AuditLog(
        user_id=user.id,
        role=user.role,
        action="LOGIN_SUCCESS",
        result="SUCCESS",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent")
    )

    db.add(success_audit)
    db.commit()

    csrf_token = generate_csrf_token()

    # --------------------------------------------------------------
    # Production-safe cross-origin cookies
    #
    # Vercel frontend:
    #     https://darknight-tau.vercel.app
    #
    # Render backend:
    #     https://darknight-hrv8.onrender.com
    #
    # Cross-site cookies require:
    #     SameSite=None
    #     Secure=True
    #
    # Local HTTP development falls back to:
    #     SameSite=Lax
    #     Secure=False
    # --------------------------------------------------------------

    cookie_settings = get_cookie_settings(request)

    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=15 * 60,
        **cookie_settings
    )

    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        max_age=7 * 24 * 3600,
        **cookie_settings
    )

    return {
        "message": "Login successful",
        "csrf_token": csrf_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "badge_number": user.badge_number,
            "unit": user.unit,
            "account_status": user.account_status,
            "mfa_enabled": user.mfa_enabled
        }
    }


# ------------------------------------------------------------------
# Logout
# ------------------------------------------------------------------

@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    raw_refresh_token = request.cookies.get(
        "refresh_token"
    )

    if raw_refresh_token:
        ref_hash = hash_token(raw_refresh_token)

        ref_session = (
            db.query(RefreshSession)
            .filter(
                RefreshSession.refresh_token_hash == ref_hash,
                RefreshSession.revoked == False
            )
            .first()
        )

        if ref_session:
            ref_session.revoked = True

            audit = AuditLog(
                user_id=ref_session.user_id,
                action="LOGOUT",
                result="SUCCESS",
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("User-Agent")
            )

            db.add(audit)
            db.commit()

    # Use the same path so the browser removes the cookies correctly.
    response.delete_cookie(
        "access_token",
        path="/"
    )

    response.delete_cookie(
        "refresh_token",
        path="/"
    )

    return {
        "message": "Logged out successfully"
    }


# ------------------------------------------------------------------
# Refresh
# ------------------------------------------------------------------

@router.post("/refresh")
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    limiter.check_rate_limit(
        request,
        "refresh",
        max_requests=30,
        window_seconds=60
    )

    raw_refresh = request.cookies.get(
        "refresh_token"
    )

    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing"
        )

    ref_hash = hash_token(raw_refresh)

    ref_session = (
        db.query(RefreshSession)
        .filter(
            RefreshSession.refresh_token_hash == ref_hash,
            RefreshSession.revoked == False
        )
        .first()
    )

    if not ref_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh session"
        )

    expires_at = ref_session.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    if expires_at < datetime.now(timezone.utc):
        ref_session.revoked = True
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired"
        )

    user = (
        db.query(User)
        .filter(User.id == ref_session.user_id)
        .first()
    )

    if not user or user.account_status != AccountStatusEnum.ACTIVE:
        ref_session.revoked = True
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account inactive"
        )

    ref_session.last_used_at = datetime.now(
        timezone.utc
    )

    new_access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role
    })

    db.commit()

    csrf_token = generate_csrf_token()

    cookie_settings = get_cookie_settings(request)

    response.set_cookie(
        key="access_token",
        value=new_access_token,
        max_age=15 * 60,
        **cookie_settings
    )

    return {
        "message": "Token refreshed",
        "csrf_token": csrf_token
    }


# ------------------------------------------------------------------
# Current user
# ------------------------------------------------------------------

@router.get("/me")
def get_me(
    user: User = Depends(get_current_user)
):
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "badge_number": user.badge_number,
            "unit": user.unit,
            "account_status": user.account_status,
            "mfa_enabled": user.mfa_enabled
        },
        "csrf_token": generate_csrf_token()
    }


# ------------------------------------------------------------------
# 2FA Setup
# ------------------------------------------------------------------

@router.post(
    "/2fa/setup",
    response_model=TwoFASetupResponse
)
def setup_2fa(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    secret = generate_totp_secret()
    otpauth_url = get_totp_uri(
        secret,
        user.email
    )

    raw_recovery_codes, hashed_codes_json = (
        generate_recovery_codes()
    )

    user.mfa_secret = secret
    user.recovery_codes_hash = hashed_codes_json

    db.commit()

    return {
        "secret": secret,
        "otpauth_url": otpauth_url,
        "recovery_codes": raw_recovery_codes
    }


# ------------------------------------------------------------------
# 2FA Verify
# ------------------------------------------------------------------

@router.post("/2fa/verify")
def verify_2fa(
    req_data: TwoFAVerifyRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    limiter.check_rate_limit(
        request,
        "2fa",
        max_requests=10,
        window_seconds=60
    )

    if not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA setup has not been initialized"
        )

    if not verify_totp_code(
        user.mfa_secret,
        req_data.code
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA code"
        )

    user.mfa_enabled = True

    audit = AuditLog(
        user_id=user.id,
        role=user.role,
        action="MFA_SUCCESS",
        result="SUCCESS",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent")
    )

    db.add(audit)
    db.commit()

    return {
        "message": (
            "Two-factor authentication enabled successfully"
        )
    }
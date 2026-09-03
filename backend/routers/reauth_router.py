from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json

from database import get_db
from models import User, AuditLog
from security import verify_password, create_reauth_token, decode_jwt_token, get_client_ip
from routers.auth_router import get_current_user
from rate_limiter import limiter

router = APIRouter(prefix="/api/auth", tags=["Re-Authentication"])

class ReAuthRequest(BaseModel):
    password: str

def require_recent_reauth(request: Request, current_user: User = Depends(get_current_user)) -> User:
    """
    FastAPI dependency enforcing that the user has completed password re-authentication
    within the last 10 minutes for sensitive/high-risk actions.
    """
    reauth_token = request.cookies.get("reauth_token") or request.headers.get("X-ReAuth-Token")
    
    if not reauth_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="REAUTH_REQUIRED"
        )

    payload = decode_jwt_token(reauth_token)
    if not payload or payload.get("type") != "reauth" or payload.get("sub") != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="REAUTH_REQUIRED"
        )

    return current_user

@router.post("/reauthenticate")
def reauthenticate(req_data: ReAuthRequest, request: Request, response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    limiter.check_rate_limit(request, "reauth", max_requests=5, window_seconds=60)

    if not verify_password(req_data.password, current_user.password_hash):
        audit_fail = AuditLog(
            user_id=current_user.id,
            role=current_user.role,
            action="REAUTH_FAILED",
            result="FAILURE",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )
        db.add(audit_fail)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password re-authentication failed"
        )

    reauth_token = create_reauth_token(current_user.id)

    audit_success = AuditLog(
        user_id=current_user.id,
        role=current_user.role,
        action="REAUTH_SUCCESS",
        result="SUCCESS",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent")
    )
    db.add(audit_success)
    db.commit()

    # Set short-lived 10-minute re-authentication cookie
    response.set_cookie(
        key="reauth_token",
        value=reauth_token,
        httponly=True,
        max_age=10 * 60,
        samesite="strict",
        secure=False
    )

    return {
        "message": "Re-authentication verified successfully",
        "reauth_token": reauth_token,
        "expires_in_seconds": 600
    }

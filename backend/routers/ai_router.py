"""
DarKnight AI — API Router

Provides the secured streaming endpoint `/api/ai/message` and quick prompt list.
Requires valid authentication via `get_current_user`.
Integrates with `audit_service` for immutable audit logging of AI queries.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import User
from routers.auth_router import get_current_user
from audit_service import create_audit_log
from services.ai_service import ai_service
from utils.ai_prompts import GLOBAL_QUICK_PROMPTS

router = APIRouter(prefix="/api/ai", tags=["DarKnight AI Copilot"])


class AIMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User question or query to DarKnight AI")
    history: Optional[List[Dict[str, str]]] = Field(default=None, description="In-memory chat history [{role, content}]")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional UI context hint (activeView, investigationId)")


@router.post("/message")
async def send_ai_message(
    req: AIMessageRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Secured streaming endpoint for DarKnight AI Copilot.

    Authentication:
        Requires valid officer session via `get_current_user`.
        Server-derived identity and role are authoritative.

    Auditing:
        Generates an immutable `AI_QUERY` AuditLog event on invocation without
        persisting confidential full query contents or credentials.
    """
    if not req.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty."
        )

    # Record audit log entry for this AI interaction
    try:
        create_audit_log(
            db=db,
            action="AI_QUERY",
            result="SUCCESS",
            user=current_user,
            resource_type="AI_COPILOT",
            resource_id=req.context.get("investigationId") if req.context else "global",
            request=request,
            metadata={
                "model": ai_service.model,
                "prompt_length": len(req.message),
                "active_view": req.context.get("activeView") if req.context else None,
                "investigation_id": req.context.get("investigationId") if req.context else None,
            }
        )
    except Exception as e:
        # Audit logging failure should be logged but not crash the user query
        import logging
        logging.getLogger(__name__).error(f"Failed to record AI audit log: {e}")

    # Return StreamingResponse carrying SSE event chunks
    return StreamingResponse(
        ai_service.stream_chat_response(
            message=req.message.strip(),
            history=req.history,
            user_name=current_user.full_name,
            user_role=current_user.role,
            context=req.context,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/prompts")
def get_quick_prompts(
    current_user: User = Depends(get_current_user)
):
    """Returns curated contextual quick prompts for the AI empty state."""
    return {"prompts": GLOBAL_QUICK_PROMPTS}


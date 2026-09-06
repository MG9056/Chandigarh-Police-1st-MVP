"""
test_ai_copilot.py — Automated test suite for DarKnight AI Copilot (Phase 1).

Covers:
1. Unauthenticated requests to /api/ai/message return 401.
2. Authenticated requests stream AI responses.
3. Audit log is created with action="AI_QUERY" without exposing secrets or API keys.
4. Quick prompts endpoint returns curated suggestions.
5. System prompt builder context assembly.
"""

import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from database import SessionLocal, init_db
from main import app
from models import User, RoleEnum, AccountStatusEnum, AuditLog
from security import create_access_token
from utils.ai_prompts import build_system_instruction, GLOBAL_QUICK_PROMPTS

client = TestClient(app)


@pytest.fixture
def db():
    init_db()
    session = SessionLocal()
    yield session
    session.close()


def _make_test_user(db, role: str = RoleEnum.INSPECTOR) -> User:
    sfx = uuid.uuid4().hex[:6]
    user = User(
        email=f"copilot_test_{role.lower().replace(' ', '_')}_{sfx}@police.gov",
        full_name=f"Officer Test {sfx}",
        password_hash="hashed_pass",
        role=role,
        account_status=AccountStatusEnum.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_ai_endpoint_unauthenticated_fails(db):
    """Unauthenticated requests to /api/ai/message must be rejected with 401."""
    res = client.post("/api/ai/message", json={"message": "How does DarKnight work?"})
    assert res.status_code == 401


def test_ai_endpoint_authenticated_success(db):
    """Authenticated users can request AI copilot responses."""
    user = _make_test_user(db, RoleEnum.INSPECTOR)
    token = create_access_token(data={"sub": str(user.id), "type": "access"})

    headers = {"Authorization": f"Bearer {token}"}
    cookies = {"access_token": token}

    res = client.post(
        "/api/ai/message",
        json={
            "message": "How does the intelligence pipeline work?",
            "context": {"activeView": "dashboard"}
        },
        headers=headers,
        cookies=cookies,
    )

    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")

    # Check that an AuditLog entry was recorded for AI_QUERY
    audit_entry = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == user.id, AuditLog.action == "AI_QUERY")
        .order_by(AuditLog.timestamp.desc())
        .first()
    )

    assert audit_entry is not None, "AI query must generate an AuditLog entry"
    assert audit_entry.result == "SUCCESS"
    assert audit_entry.role == RoleEnum.INSPECTOR
    assert "LLM_API_KEY" not in (audit_entry.metadata_json or "")
    assert "password" not in (audit_entry.metadata_json or "")


def test_ai_quick_prompts_endpoint(db):
    """GET /api/ai/prompts returns quick prompts list for authenticated users."""
    user = _make_test_user(db, RoleEnum.INVESTIGATOR)
    token = create_access_token(data={"sub": str(user.id), "type": "access"})

    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/ai/prompts", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "prompts" in data
    assert len(data["prompts"]) > 0
    assert data["prompts"][0]["id"] == "how_it_works"


def test_system_prompt_builder():
    """Confirms system prompt builder attaches officer identity & role without leaking secrets."""
    prompt = build_system_instruction(user_name="Inspector Vikram", user_role=RoleEnum.INSPECTOR)
    assert "DarKnight AI" in prompt
    assert "Officer Name: Inspector Vikram" in prompt
    assert "Role / Rank: INSPECTOR" in prompt
    assert "PHASE 1" in prompt


def test_empty_message_validation(db):
    """Blank or whitespace-only messages must be rejected with 400."""
    user = _make_test_user(db)
    token = create_access_token(data={"sub": str(user.id), "type": "access"})
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/ai/message", json={"message": "   "}, headers=headers)
    assert res.status_code == 400

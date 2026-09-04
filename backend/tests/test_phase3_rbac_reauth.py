import pytest
import os
import sys
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from database import engine, Base, SessionLocal, get_db
from models import User, InvestigationAccessGrant, AuditLog, RoleEnum, AccountStatusEnum
from security import hash_password
from rbac import has_permission, Permission, check_investigation_modification_access

# Override DB session for testing
def override_get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module")
def setup_users():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Create SP user
    sp = User(
        email="sp_test@chandigarhpolice.gov.in",
        full_name="SP Test",
        password_hash=hash_password("SPPassword123!"),
        role=RoleEnum.SP,
        account_status=AccountStatusEnum.ACTIVE
    )
    # Create Investigator user
    inv = User(
        email="inv_test@chandigarhpolice.gov.in",
        full_name="Investigator Test",
        password_hash=hash_password("InvPassword123!"),
        role=RoleEnum.INVESTIGATOR,
        account_status=AccountStatusEnum.ACTIVE
    )
    # Create Constable user
    constable = User(
        email="constable_test@chandigarhpolice.gov.in",
        full_name="Constable Test",
        password_hash=hash_password("ConstablePassword123!"),
        role=RoleEnum.CONSTABLE,
        account_status=AccountStatusEnum.ACTIVE
    )

    db.add_all([sp, inv, constable])
    db.commit()
    db.refresh(sp)
    db.refresh(inv)
    db.refresh(constable)

    yield {"sp": sp, "inv": inv, "constable": constable}

    db.close()
    Base.metadata.drop_all(bind=engine)

def test_rbac_permission_matrix():
    assert has_permission(RoleEnum.CONSTABLE, Permission.READ) is True
    assert has_permission(RoleEnum.CONSTABLE, Permission.CREATE) is False
    assert has_permission(RoleEnum.CONSTABLE, Permission.MANAGE_ACCESS) is False

    assert has_permission(RoleEnum.INVESTIGATOR, Permission.READ) is True
    assert has_permission(RoleEnum.INVESTIGATOR, Permission.CREATE) is True
    assert has_permission(RoleEnum.INVESTIGATOR, Permission.MANAGE_USERS) is False

    assert has_permission(RoleEnum.SP, Permission.MANAGE_ACCESS) is True
    assert has_permission(RoleEnum.SUPER_ADMIN, Permission.VIEW_AUDIT_LOGS) is True

def test_forced_reauthentication_flow(setup_users):
    with TestClient(app) as client:
        # Login as SP
        login_res = client.post("/api/auth/login", json={
            "email": "sp_test@chandigarhpolice.gov.in",
            "password": "SPPassword123!"
        })
        assert login_res.status_code == 200

        # Attempt sensitive action (Granting Access) WITHOUT re-authentication -> 403 REAUTH_REQUIRED
        grant_no_reauth = client.post(
            "/api/investigations/INV-1001/grant-access",
            json={"target_user_id": setup_users["inv"].id},
            cookies=login_res.cookies
        )
        assert grant_no_reauth.status_code == 403
        assert grant_no_reauth.json()["detail"] == "REAUTH_REQUIRED"

        # Perform Re-Authentication
        reauth_res = client.post(
            "/api/auth/reauthenticate",
            json={"password": "SPPassword123!"},
            cookies=login_res.cookies
        )
        assert reauth_res.status_code == 200
        assert "reauth_token" in reauth_res.cookies

        # Merge cookies
        cookies = {**login_res.cookies, **reauth_res.cookies}

        # Attempt sensitive action WITH re-authentication -> SUCCESS
        grant_with_reauth = client.post(
            "/api/investigations/INV-1001/grant-access",
            json={"target_user_id": setup_users["inv"].id, "expires_in_hours": 24},
            cookies=cookies
        )
        assert grant_with_reauth.status_code == 200
        assert grant_with_reauth.json()["user_id"] == setup_users["inv"].id

def test_delegated_investigation_access(setup_users):
    db = SessionLocal()
    inv_user = setup_users["inv"]
    constable_user = setup_users["constable"]
    investigation_id = "INV-2026-99"

    # Constable by default cannot modify investigation
    can_modify_before = check_investigation_modification_access(constable_user, investigation_id, db)
    assert can_modify_before is False

    # Create explicit delegated grant for Constable
    grant = InvestigationAccessGrant(
        investigation_id=investigation_id,
        user_id=constable_user.id,
        granted_by=setup_users["sp"].id,
        permission="MODIFY",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    db.add(grant)
    db.commit()

    # Constable can now modify investigation via explicit grant (utilizing composite index)
    can_modify_after = check_investigation_modification_access(constable_user, investigation_id, db)
    assert can_modify_after is True

    # Revoke grant
    grant.revoked = True
    db.commit()

    # Access check returns False after revocation
    can_modify_revoked = check_investigation_modification_access(constable_user, investigation_id, db)
    assert can_modify_revoked is False
    db.close()

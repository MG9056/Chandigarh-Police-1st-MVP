import pytest
import os
import sys
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from database import engine, Base, SessionLocal, get_db
from models import User, RefreshSession, AuditLog, RoleEnum, AccountStatusEnum
from security import hash_password, create_access_token, create_refresh_token, generate_totp_secret
import pyotp

# Override DB session for testing
def override_get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)

def test_signup_password_policy(client):
    # Test short password rejection (< 12 chars)
    res = client.post("/api/auth/signup", json={
        "email": "short_pass@chandigarhpolice.gov.in",
        "password": "short",
        "full_name": "Constable A. Singh"
    })
    assert res.status_code == 422 or res.status_code == 400

    # Test valid signup
    res_valid = client.post("/api/auth/signup", json={
        "email": "officer1@chandigarhpolice.gov.in",
        "password": "ValidSecurePassword123!",
        "full_name": "Constable A. Singh",
        "badge_number": "CP-1001",
        "unit": "Patrol Unit",
        "requested_role": "INVESTIGATOR"
    })
    assert res_valid.status_code == 201
    data = res_valid.json()
    assert data["account_status"] == "PENDING"

def test_pending_user_login_denied(client):
    # Attempt login for PENDING account -> 401 Forbidden generic error
    res = client.post("/api/auth/login", json={
        "email": "officer1@chandigarhpolice.gov.in",
        "password": "ValidSecurePassword123!"
    })
    assert res.status_code == 401
    assert "Invalid credentials" in res.json()["detail"]

def test_brute_force_lockout_and_admin_approval(client):
    db = SessionLocal()
    
    # 1. Create Senior Approver (SP) in DB as ACTIVE
    sp_user = User(
        email="sp_officer@chandigarhpolice.gov.in",
        full_name="SP V. Kumar",
        password_hash=hash_password("SuperSecretSPPassword123!"),
        role=RoleEnum.SP,
        account_status=AccountStatusEnum.ACTIVE
    )
    db.add(sp_user)
    db.commit()

    # Login as SP to get cookies/session
    login_sp = client.post("/api/auth/login", json={
        "email": "sp_officer@chandigarhpolice.gov.in",
        "password": "SuperSecretSPPassword123!"
    })
    assert login_sp.status_code == 200
    sp_cookies = login_sp.cookies

    # 2. Find pending officer
    pending_officer = db.query(User).filter(User.email == "officer1@chandigarhpolice.gov.in").first()
    assert pending_officer is not None

    # 3. Test ROLE HIERARCHY RULE (Constraint 4): SP cannot assign equal or higher role (SP, IGP, DGP)!
    res_equal_role = client.post(
        "/api/admin/approve-user",
        json={"target_user_id": pending_officer.id, "action": "APPROVE", "assigned_role": RoleEnum.SP},
        cookies=sp_cookies
    )
    assert res_equal_role.status_code == 403
    assert "Security Rule Violation" in res_equal_role.json()["detail"]

    # 4. SP approves pending officer as INVESTIGATOR (lower rank -> allowed)
    res_approve = client.post(
        "/api/admin/approve-user",
        json={"target_user_id": pending_officer.id, "action": "APPROVE", "assigned_role": RoleEnum.INVESTIGATOR},
        cookies=sp_cookies
    )
    assert res_approve.status_code == 200
    assert res_approve.json()["account_status"] == "ACTIVE"
    assert res_approve.json()["assigned_role"] == RoleEnum.INVESTIGATOR

    # 5. Test Brute-force 5 failed logins -> Lockout
    for i in range(4):
        client.post("/api/auth/login", json={
            "email": "officer1@chandigarhpolice.gov.in",
            "password": "WrongPassword123!"
        })

    # 5th failed attempt triggers 15 min lock
    res_lock = client.post("/api/auth/login", json={
        "email": "officer1@chandigarhpolice.gov.in",
        "password": "WrongPassword123!"
    })
    assert res_lock.status_code == 401

    # Verify user locked in DB
    db.refresh(pending_officer)
    assert pending_officer.locked_until is not None

    # Unlock for remaining tests
    pending_officer.failed_login_attempts = 0
    pending_officer.locked_until = None
    db.commit()

def test_login_success_and_logout(client):
    res_login = client.post("/api/auth/login", json={
        "email": "officer1@chandigarhpolice.gov.in",
        "password": "ValidSecurePassword123!"
    })
    assert res_login.status_code == 200
    data = res_login.json()
    assert data["user"]["email"] == "officer1@chandigarhpolice.gov.in"
    assert "access_token" in res_login.cookies
    assert "refresh_token" in res_login.cookies

    # Test /me endpoint
    res_me = client.get("/api/auth/me", cookies=res_login.cookies)
    assert res_me.status_code == 200
    assert res_me.json()["user"]["role"] == RoleEnum.INVESTIGATOR

    # Test Refresh Endpoint
    res_refresh = client.post("/api/auth/refresh", cookies=res_login.cookies)
    assert res_refresh.status_code == 200
    assert "access_token" in res_refresh.cookies

    # Test Logout
    res_logout = client.post("/api/auth/logout", cookies=res_login.cookies)
    assert res_logout.status_code == 200

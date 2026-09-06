import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from database import SessionLocal, init_db
from main import app

from models import (
    AccountStatusEnum,
    CaseKeyword,
    CrawlerRun,
    Investigation,
    InvestigationFinding,
    InvestigationFindingStatus,
    InvestigationSource,
    Keyword,
    RawRecord,
    RoleEnum,
    Source,
    User,
)

client = TestClient(app)

@pytest.fixture
def db():
    init_db()
    db = SessionLocal()
    yield db
    db.close()

@pytest.fixture
def dgp_user(db):
    email = f"dgp_test_{uuid.uuid4().hex[:6]}@police.gov"
    user = User(
        email=email,
        full_name="DGP Test Officer",
        password_hash="hashed_pass",
        role=RoleEnum.SUPER_ADMIN,
        account_status=AccountStatusEnum.ACTIVE
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def test_investigation(db, dgp_user):
    inv_id = f"TEST-STEP2-{uuid.uuid4().hex[:4].upper()}"
    inv = Investigation(
        investigation_id=inv_id,
        title="Step 2 Integration Test Case",
        status="OPEN",
        priority=2,
        created_by_id=dgp_user.id,
        lead_investigator_id=dgp_user.id,
        unit="Cyber Crime Cell"
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv

def test_investigation_source_unique_constraint(db, test_investigation):
    """Test that (investigation_id, source_id) works cleanly with soft deletes"""
    source_uuid = str(uuid.uuid4())
    s1 = InvestigationSource(
        investigation_id=test_investigation.id,
        source_id=source_uuid
    )
    db.add(s1)
    db.commit()
    assert s1.id is not None

    # Soft delete s1
    s1.removed_at = datetime.now(timezone.utc)
    db.commit()

    # Query active sources
    active = db.query(InvestigationSource).filter(
        InvestigationSource.investigation_id == test_investigation.id,
        InvestigationSource.removed_at == None
    ).all()
    assert len(active) == 0

def test_investigation_finding_upsert(db, test_investigation, dgp_user):
    """Test that creating and updating an InvestigationFinding works as expected"""
    rec_id = str(uuid.uuid4())
    finding = InvestigationFinding(
        investigation_id=test_investigation.id,
        raw_record_id=rec_id,
        review_status=InvestigationFindingStatus.PENDING_REVIEW,
        reviewed_by_id=dgp_user.id
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)

    assert finding.review_status == InvestigationFindingStatus.PENDING_REVIEW

    # Update review decision
    finding.review_status = InvestigationFindingStatus.RELEVANT
    finding.review_notes = "Confirmed darknet listing match"
    db.commit()

    updated = db.query(InvestigationFinding).filter_by(id=finding.id).first()
    assert updated.review_status == InvestigationFindingStatus.RELEVANT
    assert updated.review_notes == "Confirmed darknet listing match"

def test_investigation_finding_status_enum():
    """Verify InvestigationFindingStatus values"""
    statuses = InvestigationFindingStatus.all_values()
    assert "PENDING_REVIEW" in statuses
    assert "RELEVANT" in statuses
    assert "DISMISSED" in statuses


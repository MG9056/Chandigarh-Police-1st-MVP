from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os

# SQLite database setup for local development / hackathon feasibility
DB_PATH = os.path.join(os.path.dirname(__file__), "darknight.db")
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """
    FastAPI dependency to yield a database session per request.
    Automatically closes session on completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Creates all database tables defined in models.py and seeds initial DGP admin.
    """
    import models  # Ensures models are registered with Base
    Base.metadata.create_all(bind=engine)

    # Seed initial DGP Super Admin account if not present
    db = SessionLocal()
    try:
        from models import User, RoleEnum, AccountStatusEnum
        from security import hash_password
        existing = db.query(User).filter(User.email == "dgp@chandigarhpolice.gov.in").first()
        dgp_user = existing
        if not existing:
            dgp_user = User(
                email="dgp@chandigarhpolice.gov.in",
                full_name="DGP Admin",
                password_hash=hash_password("AdminPassword123!"),
                role=RoleEnum.SUPER_ADMIN,
                account_status=AccountStatusEnum.ACTIVE
            )
            db.add(dgp_user)
            db.commit()
            db.refresh(dgp_user)
    except Exception as e:
        db.rollback()
        print("Database auto-seed error:", e)
    finally:
        db.close()

    # Seed sample investigation for testing
    db = SessionLocal()
    try:
        from models import User, Investigation
        dgp_user = db.query(User).filter(User.email == "dgp@chandigarhpolice.gov.in").first()
        sample_inv = db.query(Investigation).filter(Investigation.investigation_id == "TEST-2026-001").first()
        if not sample_inv and dgp_user:
            sample_inv = Investigation(
                investigation_id="TEST-2026-001",
                title="Sample Investigation (For Testing)",
                description="This is a test investigation created during database initialization.",
                case_type="Testing",
                status="OPEN",
                priority=2,
                created_by_id=dgp_user.id,
                lead_investigator_id=dgp_user.id,
                unit="All"
            )
            db.add(sample_inv)
            db.commit()
    except Exception as e:
        db.rollback()
        print("Sample investigation seed error:", e)
    finally:
        db.close()

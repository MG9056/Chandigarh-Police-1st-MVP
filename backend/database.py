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

    Creates all database tables defined in the application and crawler models,
    then seeds the initial DGP admin, Inspector, and IGP accounts.
    """
    
    import models  # Ensures existing application models are registered with Base
    import crawler.models  # Ensures crawler models are registered with Base
    import data.canonical_schema

    Base.metadata.create_all(bind=engine)

    # Seed/upsert DGP Admin, Inspector, and IGP accounts
    db = SessionLocal()
    try:
        from models import User, RoleEnum, AccountStatusEnum
        from security import hash_password

        # Seed/verify DGP Admin
        dgp = db.query(User).filter(User.email == "dgp@chandigarhpolice.gov.in").first()
        if not dgp:
            dgp = User(
                email="dgp@chandigarhpolice.gov.in",
                full_name="DGP Admin",
                password_hash=hash_password("AdminPassword123!"),
                role=RoleEnum.SUPER_ADMIN,
                account_status=AccountStatusEnum.ACTIVE
            )
            db.add(dgp)
        else:
            dgp.password_hash = hash_password("AdminPassword123!")
            dgp.account_status = AccountStatusEnum.ACTIVE
            dgp.failed_login_attempts = 0
            dgp.locked_until = None

        # Seed/verify Inspector
        inspector = db.query(User).filter(User.email == "inspector.chandr@chandigarhpolice.gov.in").first()
        if not inspector:
            inspector = User(
                email="inspector.chandr@chandigarhpolice.gov.in",
                full_name="Rohit Chand",
                badge_number="CP-4491",
                unit="Cyber Crime Cell",
                password_hash=hash_password("InspectorPass123!"),
                role=RoleEnum.INSPECTOR,
                account_status=AccountStatusEnum.ACTIVE
            )
            db.add(inspector)
        else:
            inspector.password_hash = hash_password("InspectorPass123!")
            inspector.account_status = AccountStatusEnum.ACTIVE
            inspector.failed_login_attempts = 0
            inspector.locked_until = None

        # Seed/verify IGP Admin
        igp = db.query(User).filter(User.email == "igp@chandigarhpolice.gov.in").first()
        if not igp:
            igp = User(
                email="igp@chandigarhpolice.gov.in",
                full_name="IGP Intelligence",
                badge_number="CP-1001",
                unit="Crime & Intelligence Branch",
                password_hash=hash_password("IGPPassword123!"),
                role=RoleEnum.IGP,
                account_status=AccountStatusEnum.ACTIVE
            )
            db.add(igp)
        else:
            igp.password_hash = hash_password("IGPPassword123!")
            igp.account_status = AccountStatusEnum.ACTIVE
            igp.failed_login_attempts = 0
            igp.locked_until = None

        db.commit()

    except Exception as e:
        db.rollback()
        print("Database auto-seed error:", e)

    finally:
        db.close()

    # Seed sample investigation for testing (investigation management step 1)
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

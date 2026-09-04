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
    Creates all database tables defined in models.py and canonical_schema.py and seeds initial DGP admin.
    """
    import models  # Ensures legacy models are registered with Base
    import data.canonical_schema  # Ensures canonical models are registered with Base
    Base.metadata.create_all(bind=engine)

    # Seed initial DGP Super Admin account if not present
    db = SessionLocal()
    try:
        from models import User, RoleEnum, AccountStatusEnum
        from security import hash_password
        existing = db.query(User).filter(User.email == "dgp@chandigarhpolice.gov.in").first()
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
    except Exception as e:
        db.rollback()
        print("Database auto-seed error:", e)
    finally:
        db.close()

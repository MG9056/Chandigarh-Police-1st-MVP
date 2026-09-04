from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import User
from rbac import require_permission, Permission, check_investigation_modification_access
from crawler.models.keyword import Keyword
from crawler.models.case_keyword import CaseKeyword
from crawler.keywords.service import KeywordService

router = APIRouter(prefix="", tags=["Crawler Keywords"])


class KeywordCreate(BaseModel):
    term: str
    language: str = "en"
    category: Optional[str] = None


@router.get("/api/keywords")
def list_keywords(
    case_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.READ)),
):
    active_terms = KeywordService.get_active_keywords(db, case_id=case_id)
    global_kws = db.query(Keyword).filter(Keyword.is_global == True).all()

    return {
        "case_id": case_id,
        "active_terms": active_terms,
        "global_keywords": [
            {
                "id": str(kw.id),
                "term": kw.term,
                "language": kw.language,
                "category": kw.category,
            }
            for kw in global_kws
        ],
    }


@router.post("/api/keywords")
def create_global_keyword(
    payload: KeywordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_DATA_SOURCES)),
):
    kw = KeywordService.add_global(
        db,
        term=payload.term,
        language=payload.language,
        category=payload.category,
        created_by=current_user.id,
    )
    return {"id": str(kw.id), "term": kw.term, "language": kw.language, "category": kw.category}


@router.post("/api/cases/{case_id}/keywords")
def add_case_keyword(
    case_id: str,
    keyword_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.UPDATE)),
):
    # Permission check for investigation scoping
    if not check_investigation_modification_access(current_user, case_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User unauthorized to modify case keywords for case '{case_id}'",
        )

    ck = KeywordService.add_case_keyword(db, case_id=case_id, keyword_id=keyword_id, added_by=current_user.id)
    return {"message": "Case keyword override added", "case_id": case_id, "keyword_id": keyword_id, "is_active": ck.is_active}


@router.delete("/api/cases/{case_id}/keywords/{keyword_id}")
def remove_case_keyword(
    case_id: str,
    keyword_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.UPDATE)),
):
    if not check_investigation_modification_access(current_user, case_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User unauthorized to modify case keywords for case '{case_id}'",
        )

    KeywordService.remove_case_keyword(db, case_id=case_id, keyword_id=keyword_id)
    return {"message": "Case keyword override removed", "case_id": case_id, "keyword_id": keyword_id}

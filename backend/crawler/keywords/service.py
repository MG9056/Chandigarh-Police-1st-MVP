import uuid
from typing import List, Optional
from sqlalchemy.orm import Session


from crawler.models.keyword import Keyword
from crawler.models.case_keyword import CaseKeyword


INITIAL_GLOBAL_KEYWORDS = [
    # English Drug & Marketplace Terms
    {"term": "heroin", "language": "en", "category": "substance"},
    {"term": "cocaine", "language": "en", "category": "substance"},
    {"term": "fentanyl", "language": "en", "category": "substance"},
    {"term": "tramadol", "language": "en", "category": "substance"},
    {"term": "methamphetamine", "language": "en", "category": "substance"},
    {"term": "mdma", "language": "en", "category": "substance"},
    {"term": "escrow", "language": "en", "category": "marketplace_term"},
    {"term": "stealth shipping", "language": "en", "category": "marketplace_term"},
    # Hindi Slang & Regional Terms
    {"term": "अफीम", "language": "hi", "category": "slang"},  # Afeem
    {"term": "चरस", "language": "hi", "category": "slang"},   # Charas
    {"term": "गांजा", "language": "hi", "category": "slang"},  # Ganja
    {"term": "स्मैक", "language": "hi", "category": "slang"},  # Smack
    # Punjabi Slang & Regional Terms
    {"term": "ਚਿੱਟਾ", "language": "pa", "category": "slang"},   # Chitta
    {"term": "ਅਫ਼ੀਮ", "language": "pa", "category": "slang"},   # Afeem
    {"term": "ਭੰਗ", "language": "pa", "category": "slang"},    # Bhang
]


class KeywordService:

    @staticmethod
    def seed_initial_keywords(db: Session):
        for item in INITIAL_GLOBAL_KEYWORDS:
            existing = db.query(Keyword).filter(
                Keyword.term == item["term"],
                Keyword.language == item["language"]
            ).first()
            if not existing:
                kw = Keyword(
                    term=item["term"],
                    language=item["language"],
                    category=item["category"],
                    is_global=True,
                )
                db.add(kw)
        db.commit()

    @staticmethod
    def add_global(db: Session, term: str, language: str, category: Optional[str] = None, created_by: Optional[int] = None) -> Keyword:
        kw = Keyword(
            term=term.strip().lower(),
            language=language.lower(),
            category=category,
            is_global=True,
            created_by=created_by,
        )
        db.add(kw)
        db.commit()
        db.refresh(kw)
        return kw

    @staticmethod
    def add_case_keyword(db: Session, case_id: str, keyword_id: str | uuid.UUID, added_by: Optional[int] = None) -> CaseKeyword:
        kw_uuid = uuid.UUID(str(keyword_id)) if isinstance(keyword_id, str) else keyword_id
        existing = db.query(CaseKeyword).filter(
            CaseKeyword.case_id == case_id,
            CaseKeyword.keyword_id == kw_uuid
        ).first()

        if existing:
            existing.is_active = True
            db.commit()
            return existing

        ck = CaseKeyword(
            case_id=case_id,
            keyword_id=kw_uuid,
            is_active=True,
            added_by=added_by,
        )
        db.add(ck)
        db.commit()
        db.refresh(ck)
        return ck

    @staticmethod
    def remove_case_keyword(db: Session, case_id: str, keyword_id: str | uuid.UUID):
        kw_uuid = uuid.UUID(str(keyword_id)) if isinstance(keyword_id, str) else keyword_id
        ck = db.query(CaseKeyword).filter(
            CaseKeyword.case_id == case_id,
            CaseKeyword.keyword_id == kw_uuid
        ).first()
        if ck:
            ck.is_active = False
            db.commit()


    @staticmethod
    def get_active_keywords(db: Session, case_id: Optional[str] = None) -> List[str]:
        # 1. Ensure initial keywords are seeded
        KeywordService.seed_initial_keywords(db)

        # 2. Get global active keywords
        global_kws = db.query(Keyword).filter(Keyword.is_global == True).all()
        active_terms = {kw.term for kw in global_kws}

        # 3. Merge case-specific overrides if case_id provided
        if case_id:
            case_overrides = db.query(CaseKeyword).filter(CaseKeyword.case_id == case_id).all()
            for co in case_overrides:
                kw = db.query(Keyword).filter(Keyword.id == co.keyword_id).first()
                if kw:
                    if co.is_active:
                        active_terms.add(kw.term)
                    else:
                        active_terms.discard(kw.term)

        return list(active_terms)

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import json
from datetime import datetime, timezone

from database import get_db
from models import User, Suspect, CryptoWallet, DarknetListing, TelegramMessage, TelegramChannel, CrawlerCandidate
from routers.auth_router import get_current_user
from entity_resolution import username_similarity
from semantic_search import SemanticIndex

router = APIRouter(prefix="/api", tags=["Search & Intelligence Domain"])


def _platform_mentions(suspect: Suspect) -> list:
    if not suspect.platform_mentions:
        return []
    try:
        parsed = json.loads(suspect.platform_mentions)
        return parsed if isinstance(parsed, list) else [str(parsed)]
    except json.JSONDecodeError:
        return [suspect.platform_mentions]


def _data_origin(suspect: Suspect) -> str:
    return suspect.data_origin or "base_dataset"


def _candidate_aliases(candidate: CrawlerCandidate) -> list:
    if candidate.aliases_json:
        try:
            parsed = json.loads(candidate.aliases_json)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item]
            return [str(parsed)]
        except json.JSONDecodeError:
            pass
    if candidate.primary_alias:
        return [candidate.primary_alias]
    return [f"Unidentified target — crawler {candidate.id}"]


def _candidate_data_origin(candidate: CrawlerCandidate) -> str:
    return candidate.data_origin or "crawler_candidate"


def _profile_sort_key(item: dict) -> tuple:
    origin = item.get("data_origin") or ""
    priority = 0 if item.get("crawler_candidate") else (1 if "crawler" in origin else 2)
    return priority, -(item.get("risk_score") or 0), item.get("primary_alias") or item.get("label") or ""


def _candidate_result(candidate: CrawlerCandidate) -> dict:
    aliases = _candidate_aliases(candidate)
    label = candidate.primary_alias or aliases[0]
    risk_level = "Critical" if candidate.risk_score >= 80 else ("High" if candidate.risk_score >= 70 else "Medium")
    platform_mentions = []
    if candidate.platform_mentions:
        try:
            parsed_mentions = json.loads(candidate.platform_mentions)
            if isinstance(parsed_mentions, list):
                platform_mentions = parsed_mentions
            else:
                platform_mentions = [str(parsed_mentions)]
        except json.JSONDecodeError:
            platform_mentions = [candidate.platform_mentions]
    return {
        "id": candidate.id,
        "label": label,
        "primary_alias": candidate.primary_alias or label,
        "aliases": aliases,
        "telegram_handle": candidate.telegram_handle,
        "pgp_fingerprint": None,
        "phone_number": candidate.phone_number,
        "last_known_location": candidate.last_known_location,
        "platform_mentions": platform_mentions,
        "enrichment_summary": candidate.notes or "Partial crawler observation; identity information may be incomplete.",
        "enrichment_source_count": 1 if candidate.confidence_score else 0,
        "last_enriched_at": candidate.updated_at.isoformat() if candidate.updated_at else None,
        "data_origin": _candidate_data_origin(candidate),
        "risk_score": candidate.risk_score,
        "risk_level": risk_level,
        "notes": candidate.notes or "Partial crawler-fetched entity; identity fields may be incomplete.",
        "match_reason": "Crawler candidate match",
        "wallets_count": 0,
        "listings_count": 0,
        "telegram_messages_count": 0,
        "crawler_candidate": True,
        "profile_type": "crawler_candidate",
        "source_url": candidate.source_url,
        "synthetic_generated": bool(candidate.synthetic_generated),
        "synthetic_reason": candidate.synthetic_reason,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
    }


def _candidate_matches_query(candidate: CrawlerCandidate, q_lower: str) -> bool:
    search_fields = [
        candidate.primary_alias or "",
        candidate.telegram_handle or "",
        candidate.phone_number or "",
        candidate.last_known_location or "",
        candidate.source_url or "",
        candidate.raw_text or "",
        candidate.cleaned_text or "",
        candidate.notes or "",
    ]
    if candidate.platform_mentions:
        search_fields.append(candidate.platform_mentions)
    return any(q_lower in str(value).lower() for value in search_fields)


def _semantic_matches(query_str: str, category: str, db: Session) -> list[dict]:
    category_types = {
        "suspects": {"suspect"},
        "wallets": {"wallet"},
        "listings": {"listing"},
        "telegram": {"telegram"},
        "all": {"suspect", "wallet", "listing", "telegram"},
    }
    try:
        return SemanticIndex().search(
            query_str,
            source_types=category_types.get(category.lower(), category_types["all"]),
            top_k=50,
        )
    except Exception:
        # Search must remain available when an optional AI provider is down.
        return []


def _append_semantic_matches(query_str: str, category: str, db: Session,
                             suspects_results: list, wallets_results: list,
                             listings_results: list, telegram_results: list) -> None:
    existing = {
        ("suspect", str(item["id"])) for item in suspects_results
    } | {
        ("wallet", str(item["id"])) for item in wallets_results
    } | {
        ("listing", str(item["id"])) for item in listings_results
    } | {
        ("telegram", str(item["id"])) for item in telegram_results
    }
    minimum_score = float(__import__("os").environ.get("SEMANTIC_SEARCH_MIN_SCORE", "0.65"))

    for match in _semantic_matches(query_str, category, db):
        if match["score"] < minimum_score or (match["source_type"], match["source_id"]) in existing:
            continue
        source_type = match["source_type"]
        source_id = int(match["source_id"])
        reason = f"Semantic similarity ({int(match['score'] * 100)}%)"
        if source_type == "suspect":
            record = db.query(Suspect).filter(Suspect.id == source_id).first()
            if record:
                aliases = json.loads(record.aliases_json) if record.aliases_json else [record.primary_alias]
                suspects_results.append({"id": record.id, "primary_alias": record.primary_alias,
                    "aliases": aliases, "telegram_handle": record.telegram_handle,
                    "pgp_fingerprint": record.pgp_fingerprint, "phone_number": record.phone_number,
                    "last_known_location": record.last_known_location, "platform_mentions": _platform_mentions(record),
                    "enrichment_summary": record.enrichment_summary, "enrichment_source_count": record.enrichment_source_count or 0,
                    "last_enriched_at": record.last_enriched_at.isoformat() if record.last_enriched_at else None,
                    "data_origin": _data_origin(record), "risk_score": record.risk_score,
                    "risk_level": "Critical" if record.risk_score >= 80 else ("High" if record.risk_score >= 70 else "Medium"),
                    "notes": record.notes, "match_reason": reason,
                    "wallets_count": len(record.wallets) if record.wallets else 0,
                    "listings_count": len(record.listings) if record.listings else 0})
        elif source_type == "wallet":
            record = db.query(CryptoWallet).filter(CryptoWallet.id == source_id).first()
            if record:
                wallets_results.append({"id": record.id, "address": record.address, "currency": record.currency,
                    "balance": record.balance, "risk_level": record.risk_level,
                    "associated_suspect_id": record.associated_suspect_id,
                    "associated_suspect_alias": record.suspect.primary_alias if record.suspect else None,
                    "outgoing_txs_count": len(record.outgoing_txs) if record.outgoing_txs else 0,
                    "incoming_txs_count": len(record.incoming_txs) if record.incoming_txs else 0,
                    "match_reason": reason})
        elif source_type == "listing":
            record = db.query(DarknetListing).filter(DarknetListing.id == source_id).first()
            if record:
                listings_results.append({"id": record.id, "title": record.title, "vendor_alias": record.vendor_alias,
                    "platform": record.platform, "drug_category": record.drug_category, "price": record.price,
                    "currency": record.currency, "location": record.location,
                    "associated_suspect_id": record.associated_suspect_id,
                    "scraped_at": record.scraped_at.isoformat() if record.scraped_at else None,
                    "match_reason": reason})
        elif source_type == "telegram":
            record = db.query(TelegramMessage).filter(TelegramMessage.id == source_id).first()
            if record:
                wallets = json.loads(record.detected_wallets_json) if record.detected_wallets_json else []
                keywords = json.loads(record.detected_keywords_json) if record.detected_keywords_json else []
                telegram_results.append({"id": record.id, "channel_id": record.channel_id,
                    "channel_name": record.channel.channel_name if record.channel else f"Channel #{record.channel_id}",
                    "sender_handle": record.sender_handle, "message_text": record.message_text,
                    "detected_wallets": wallets, "detected_keywords": keywords,
                    "timestamp": record.timestamp.isoformat() if record.timestamp else None,
                    "match_reason": reason})

@router.get("/search/universal")
def universal_search(
    q: str = Query("", description="Search query string"),
    category: Optional[str] = Query("all", description="Category filter: all, suspects, wallets, listings, telegram"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query_str = (q or "").strip()
    if not query_str:
        return {
            "query": "",
            "total_results": 0,
            "suspects": [],
            "wallets": [],
            "listings": [],
            "telegram_messages": []
        }

    q_lower = query_str.lower()
    
    candidate_matches = []
    for candidate in db.query(CrawlerCandidate).all():
        if _candidate_matches_query(candidate, q_lower):
            candidate_matches.append(_candidate_result(candidate))

    # 1. Search Suspects (SQL Substring + Fuzzy Matching)
    suspects_results = []
    seen_suspect_ids = set()
    all_suspects = db.query(Suspect).all()
    
    for s in all_suspects:
        match_reason = None
        aliases_list = json.loads(s.aliases_json) if s.aliases_json else [s.primary_alias]
        
        # Substring checks
        if q_lower in s.primary_alias.lower():
            match_reason = "Primary Alias Exact Substring"
        elif any(q_lower in a.lower() for a in aliases_list):
            match_reason = "Known Alias Match"
        elif s.telegram_handle and q_lower in s.telegram_handle.lower():
            match_reason = "Telegram Handle Match"
        elif s.pgp_fingerprint and q_lower in s.pgp_fingerprint.lower():
            match_reason = "PGP Fingerprint Match"
        elif s.phone_number and q_lower in s.phone_number.lower():
            match_reason = "Phone Number Match"
        elif s.last_known_location and q_lower in s.last_known_location.lower():
            match_reason = "Location Match"
        elif s.platform_mentions and q_lower in s.platform_mentions.lower():
            match_reason = "Platform Mention Match"
        else:
            # Fuzzy match check
            sim = username_similarity(query_str, s.primary_alias)
            if sim["username_similarity"] >= 0.65:
                match_reason = f"Fuzzy Alias Similarity ({int(sim['username_similarity'] * 100)}%)"

        if match_reason:
            seen_suspect_ids.add(s.id)
            risk_lvl = "Critical" if s.risk_score >= 80 else ("High" if s.risk_score >= 70 else "Medium")
            suspects_results.append({
                "id": s.id,
                "primary_alias": s.primary_alias,
                "aliases": aliases_list,
                "telegram_handle": s.telegram_handle,
                "pgp_fingerprint": s.pgp_fingerprint,
                "phone_number": s.phone_number,
                "last_known_location": s.last_known_location,
                "platform_mentions": _platform_mentions(s),
                "enrichment_summary": s.enrichment_summary,
                "enrichment_source_count": s.enrichment_source_count or 0,
                "last_enriched_at": s.last_enriched_at.isoformat() if s.last_enriched_at else None,
                "data_origin": _data_origin(s),
                "risk_score": s.risk_score,
                "risk_level": risk_lvl,
                "notes": s.notes,
                "match_reason": match_reason,
                "wallets_count": len(s.wallets) if s.wallets else 0,
                "listings_count": len(s.listings) if s.listings else 0
            })

    # 2. Search Crypto Wallets
    wallets_results = []
    wallets_query = db.query(CryptoWallet).filter(
        (CryptoWallet.address.ilike(f"%{query_str}%")) |
        (CryptoWallet.currency.ilike(f"%{query_str}%")) |
        (CryptoWallet.risk_level.ilike(f"%{query_str}%"))
    ).limit(50).all()

    for w in wallets_query:
        suspect_alias = w.suspect.primary_alias if w.suspect else None
        wallets_results.append({
            "id": w.id,
            "address": w.address,
            "currency": w.currency,
            "balance": w.balance,
            "risk_level": w.risk_level,
            "associated_suspect_id": w.associated_suspect_id,
            "associated_suspect_alias": suspect_alias,
            "outgoing_txs_count": len(w.outgoing_txs) if w.outgoing_txs else 0,
            "incoming_txs_count": len(w.incoming_txs) if w.incoming_txs else 0
        })

    # 3. Search Darknet Listings
    listings_results = []
    all_listings = db.query(DarknetListing).all()

    for l in all_listings:
        match_reason = None
        if (q_lower in l.title.lower() or 
            q_lower in l.vendor_alias.lower() or 
            q_lower in l.drug_category.lower() or 
            (l.location and q_lower in l.location.lower()) or 
            (l.description and q_lower in l.description.lower())):
            match_reason = "Direct Text Substring Match"
        else:
            sim = username_similarity(query_str, l.vendor_alias)
            if sim["username_similarity"] >= 0.70:
                match_reason = f"Fuzzy Vendor Alias ({int(sim['username_similarity'] * 100)}%)"

        if match_reason:
            listings_results.append({
                "id": l.id,
                "title": l.title,
                "vendor_alias": l.vendor_alias,
                "platform": l.platform,
                "drug_category": l.drug_category,
                "price": l.price,
                "currency": l.currency,
                "location": l.location,
                "associated_suspect_id": l.associated_suspect_id,
                "scraped_at": l.scraped_at.isoformat() if l.scraped_at else None,
                "match_reason": match_reason
            })

    # 4. Search Telegram Messages
    telegram_results = []
    all_messages = db.query(TelegramMessage).all()

    for m in all_messages:
        match_reason = None
        wallets_detected = json.loads(m.detected_wallets_json) if m.detected_wallets_json else []
        keywords_detected = json.loads(m.detected_keywords_json) if m.detected_keywords_json else []

        if q_lower in m.message_text.lower():
            match_reason = "Message Content Text Match"
        elif q_lower in m.sender_handle.lower():
            match_reason = "Sender Handle Match"
        elif any(q_lower in w.lower() for w in wallets_detected):
            match_reason = "Detected BTC Wallet Match"
        elif any(q_lower in k.lower() for k in keywords_detected):
            match_reason = "Detected Drug Keyword Match"
        else:
            sim = username_similarity(query_str, m.sender_handle)
            if sim["username_similarity"] >= 0.70:
                match_reason = f"Fuzzy Handle Match ({int(sim['username_similarity'] * 100)}%)"

        if match_reason:
            ch_name = m.channel.channel_name if m.channel else f"Channel #{m.channel_id}"
            telegram_results.append({
                "id": m.id,
                "channel_id": m.channel_id,
                "channel_name": ch_name,
                "sender_handle": m.sender_handle,
                "message_text": m.message_text,
                "detected_wallets": wallets_detected,
                "detected_keywords": keywords_detected,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "match_reason": match_reason
            })

    suspects_results.extend(candidate_matches)

    suspects_results = sorted(suspects_results, key=_profile_sort_key)

    _append_semantic_matches(
        query_str, category or "all", db,
        suspects_results, wallets_results, listings_results, telegram_results,
    )

    cat_lower = (category or "all").lower()
    if cat_lower == "suspects":
        wallets_results = []
        listings_results = []
        telegram_results = []
    elif cat_lower == "wallets":
        suspects_results = []
        listings_results = []
        telegram_results = []
    elif cat_lower == "listings":
        suspects_results = []
        wallets_results = []
        telegram_results = []
    elif cat_lower == "telegram":
        suspects_results = []
        wallets_results = []
        listings_results = []

    total_results = len(suspects_results) + len(wallets_results) + len(listings_results) + len(telegram_results)

    return {
        "query": query_str,
        "category": category,
        "total_results": total_results,
        "suspects": suspects_results[:30],
        "wallets": wallets_results[:30],
        "listings": listings_results[:30],
        "telegram_messages": telegram_results[:30]
    }

@router.get("/suspects")
def list_suspects(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    q: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Suspect)
    if q:
        q_clean = q.strip()
        query = query.filter(
            (Suspect.primary_alias.ilike(f"%{q_clean}%")) |
            (Suspect.aliases_json.ilike(f"%{q_clean}%")) |
            (Suspect.telegram_handle.ilike(f"%{q_clean}%")) |
            (Suspect.phone_number.ilike(f"%{q_clean}%")) |
            (Suspect.last_known_location.ilike(f"%{q_clean}%")) |
            (Suspect.platform_mentions.ilike(f"%{q_clean}%")) |
            (Suspect.enrichment_summary.ilike(f"%{q_clean}%"))
        )

    total = query.count()
    suspects = query.order_by(Suspect.risk_score.desc(), Suspect.id.asc()).offset((page - 1) * limit).limit(limit).all()

    result = []
    for s in suspects:
        aliases_list = json.loads(s.aliases_json) if s.aliases_json else [s.primary_alias]
        risk_lvl = "Critical" if s.risk_score >= 80 else ("High" if s.risk_score >= 70 else "Medium")
        
        tg_count = 0
        if s.telegram_handle:
            tg_count = db.query(TelegramMessage).filter(TelegramMessage.sender_handle == s.telegram_handle).count()

        result.append({
            "id": s.id,
            "label": s.primary_alias,
            "primary_alias": s.primary_alias,
            "aliases": aliases_list,
            "telegram_handle": s.telegram_handle,
            "pgp_fingerprint": s.pgp_fingerprint,
            "phone_number": s.phone_number,
            "last_known_location": s.last_known_location,
            "platform_mentions": _platform_mentions(s),
            "enrichment_summary": s.enrichment_summary,
            "enrichment_source_count": s.enrichment_source_count or 0,
            "last_enriched_at": s.last_enriched_at.isoformat() if s.last_enriched_at else None,
            "data_origin": _data_origin(s),
            "risk_score": s.risk_score,
            "risk_level": risk_lvl,
            "notes": s.notes or "Monitored threat actor entity.",
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "last_active": s.updated_at.strftime("%Y-%m-%d") if s.updated_at else "2026-08-30",
            "wallets_count": len(s.wallets) if s.wallets else 0,
            "listings_count": len(s.listings) if s.listings else 0,
            "telegram_messages_count": tg_count
        })

    candidate_rows = []
    candidate_query = db.query(CrawlerCandidate)
    if q:
        q_clean = q.strip().lower()
        candidate_rows = [
            candidate for candidate in candidate_query.all()
            if _candidate_matches_query(candidate, q_clean)
        ]
    else:
        candidate_rows = candidate_query.order_by(CrawlerCandidate.updated_at.desc()).limit(limit).all()

    result.extend(_candidate_result(candidate) for candidate in candidate_rows)
    result = sorted(result, key=_profile_sort_key)

    return {
        "page": page,
        "limit": limit,
        "total": total + len(candidate_rows),
        "suspects": result[:limit]
    }

@router.get("/crawler-candidates/{candidate_id}")
def get_crawler_candidate_detail(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    candidate = db.query(CrawlerCandidate).filter(CrawlerCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crawler target profile not found"
        )

    raw_record = None
    if candidate.source_record_id:
        from crawler.models.raw_record import RawRecord
        raw_record = db.query(RawRecord).filter(RawRecord.id == candidate.source_record_id).first()

    result = _candidate_result(candidate)
    result.update({
        "raw_record_id": str(candidate.source_record_id) if candidate.source_record_id else None,
        "raw_text": candidate.raw_text,
        "cleaned_text": candidate.cleaned_text,
        "relevance_reasoning": raw_record.relevance_reasoning if raw_record else None,
        "extracted_candidates": raw_record.extracted_candidates if raw_record else [],
        "structured_intelligence": raw_record.structured_intelligence if raw_record else None,
        "wallets": [],
        "listings": [],
        "telegram_messages": [],
    })
    return result

@router.get("/suspects/{suspect_id}")
def get_suspect_detail(
    suspect_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    suspect = db.query(Suspect).filter(Suspect.id == suspect_id).first()
    if not suspect:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suspect profile not found"
        )

    aliases_list = json.loads(suspect.aliases_json) if suspect.aliases_json else [suspect.primary_alias]
    risk_lvl = "Critical" if suspect.risk_score >= 80 else ("High" if suspect.risk_score >= 70 else "Medium")

    wallets_detail = [
        {
            "id": w.id,
            "address": w.address,
            "currency": w.currency,
            "balance": w.balance,
            "risk_level": w.risk_level
        }
        for w in suspect.wallets
    ]

    listings_detail = [
        {
            "id": l.id,
            "title": l.title,
            "platform": l.platform,
            "drug_category": l.drug_category,
            "price": l.price,
            "location": l.location,
            "scraped_at": l.scraped_at.isoformat() if l.scraped_at else None
        }
        for l in suspect.listings
    ]

    telegram_detail = []
    if suspect.telegram_handle:
        msgs = db.query(TelegramMessage).filter(TelegramMessage.sender_handle == suspect.telegram_handle).order_by(TelegramMessage.timestamp.desc()).all()
        for m in msgs:
            ch_name = m.channel.channel_name if m.channel else f"Channel #{m.channel_id}"
            telegram_detail.append({
                "id": m.id,
                "channel_name": ch_name,
                "message_text": m.message_text,
                "detected_wallets": json.loads(m.detected_wallets_json) if m.detected_wallets_json else [],
                "detected_keywords": json.loads(m.detected_keywords_json) if m.detected_keywords_json else [],
                "timestamp": m.timestamp.isoformat() if m.timestamp else None
            })

    return {
        "id": suspect.id,
        "primary_alias": suspect.primary_alias,
        "aliases": aliases_list,
        "telegram_handle": suspect.telegram_handle,
        "pgp_fingerprint": suspect.pgp_fingerprint,
        "phone_number": suspect.phone_number,
        "last_known_location": suspect.last_known_location,
        "platform_mentions": _platform_mentions(suspect),
        "enrichment_summary": suspect.enrichment_summary,
        "enrichment_source_count": suspect.enrichment_source_count or 0,
        "last_enriched_at": suspect.last_enriched_at.isoformat() if suspect.last_enriched_at else None,
        "data_origin": _data_origin(suspect),
        "risk_score": suspect.risk_score,
        "risk_level": risk_lvl,
        "notes": suspect.notes or "Monitored threat actor entity.",
        "created_at": suspect.created_at.isoformat() if suspect.created_at else None,
        "wallets": wallets_detail,
        "listings": listings_detail,
        "telegram_messages": telegram_detail
    }

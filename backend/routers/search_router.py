from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import json
from datetime import datetime, timezone

from database import get_db
from models import User, Suspect, CryptoWallet, DarknetListing, TelegramMessage, TelegramChannel
from routers.auth_router import get_current_user
from entity_resolution import username_similarity

router = APIRouter(prefix="/api", tags=["Search & Intelligence Domain"])

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
            (Suspect.telegram_handle.ilike(f"%{q_clean}%"))
        )

    total = query.count()
    suspects = query.order_by(Suspect.risk_score.desc(), Suspect.id.asc()).offset((page - 1) * limit).limit(limit).all()

    result = []
    for s in suspects:
        aliases_list = json.loads(s.aliases_json) if s.aliases_json else [s.primary_alias]
        risk_lvl = "Critical" if s.risk_score >= 80 else ("High" if s.risk_score >= 70 else "Medium")
        
        # Count linked telegram messages by handle
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
            "risk_score": s.risk_score,
            "risk_level": risk_lvl,
            "notes": s.notes or "Monitored threat actor entity.",
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "last_active": s.updated_at.strftime("%Y-%m-%d") if s.updated_at else "2026-08-30",
            "wallets_count": len(s.wallets) if s.wallets else 0,
            "listings_count": len(s.listings) if s.listings else 0,
            "telegram_messages_count": tg_count
        })

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "suspects": result
    }

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
        "risk_score": suspect.risk_score,
        "risk_level": risk_lvl,
        "notes": suspect.notes or "Monitored threat actor entity.",
        "created_at": suspect.created_at.isoformat() if suspect.created_at else None,
        "wallets": wallets_detail,
        "listings": listings_detail,
        "telegram_messages": telegram_detail
    }

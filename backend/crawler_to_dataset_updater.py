"""
crawler_to_dataset_updater.py
─────────────────────────────
Track 2: Background task that reads new/unprocessed RawRecord rows from the
`raw_records` table (written by crawler/orchestration/flows.py) and appends
matched rows into the fixed dataset files on disk.

Matching logic (heuristic — no LLM required, LLM path is optional):
  AGORA   – record whose cleaned_text mentions a drug/substance keyword AND
             a vendor/price/market keyword, OR whose matched_keywords contain
             any known drug category term.
  ELLIPTIC– record whose extracted_candidates contain a BITCOIN_ADDRESS or
             ETHEREUM_ADDRESS type, OR cleaned_text contains a BTC address
             regex match.
  OFAC    – record classified as ELLIPTIC above AND cleaned_text also contains
             an OFAC/sanction/SDN indicator term.
  NO-MATCH– everything else: logged and left as status="no_dataset_match".

Field mapping:
  AGORA CSV  (Vendor, Category, Item, Price, Origin)
    Vendor  ← url domain / source handle extracted from url
    Category← first matched drug keyword, title-cased; else "Drugs/Uncategorized"
    Item    ← first 120 chars of cleaned_text (stripped to single line)
    Price   ← regex-extracted BTC/USD price from text; else ""
    Origin  ← NER GPE entity from extracted_candidates if present; else "Unknown"

  ELLIPTIC wallets_classes.csv  (address, class)
    address ← each BTC/ETH address in extracted_candidates
    class   ← always 3 (unknown) — crawler cannot label illicit/licit

  ELLIPTIC AddrAddr_edgelist.csv  (input_address, output_address)
    Produced only when 2+ wallet addresses appear in the same record.
    input_address  ← addresses[0]
    output_address ← addresses[1], addresses[2], ... (one row each)

  OFAC sanctioned_addresses_with_entities.json  (address, entity_name)
    address     ← each wallet address found
    entity_name ← url domain or "OFAC Match via Crawler"

After writing, sets RawRecord.status to one of:
  "mapped_agora"    – appended to agora_sample.csv
  "mapped_elliptic" – appended to wallets_classes.csv / AddrAddr_edgelist.csv
  "mapped_ofac"     – appended to sanctioned_addresses_with_entities.json
  "no_dataset_match"– no match, logged

Run mode: called from main.py lifespan as an asyncio background task.
Runs a polling loop with a configurable interval (default 60 s) so new crawler
output is picked up continuously without requiring a server restart.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("crawler_to_dataset_updater")

# ---------------------------------------------------------------------------
# Paths (resolved relative to this file, so they work regardless of cwd)
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_REAL_DATA = os.path.join(_HERE, "real_data_files")

AGORA_CSV    = os.path.join(_REAL_DATA, "listings",  "agora_sample.csv")
WALLETS_CSV  = os.path.join(_REAL_DATA, "elliptic",  "wallets_classes.csv")
EDGELIST_CSV = os.path.join(_REAL_DATA, "elliptic",  "AddrAddr_edgelist.csv")
OFAC_JSON    = os.path.join(_REAL_DATA, "ofac",      "sanctioned_addresses_with_entities.json")

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
_BTC_RE = re.compile(
    r"\b(?:bc1[a-z0-9]{11,71}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b"
)
_ETH_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
_PRICE_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(BTC|USD|XMR|ETH|USDT)\b", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Keyword sets for heuristic classification
# ---------------------------------------------------------------------------
_DRUG_KEYWORDS = {
    "cannabis", "weed", "marijuana", "hash", "kush", "indica", "sativa",
    "cocaine", "coke", "blow", "crack",
    "heroin", "dope", "fentanyl", "opioid", "opioids",
    "mdma", "ecstasy", "molly",
    "lsd", "acid", "blotter",
    "methamphetamine", "meth", "crystal",
    "ketamine", "xanax", "adderall", "tramadol", "oxycodone",
    "mushrooms", "psilocybin", "dmt",
    "speed", "amphetamine",
    "drug", "drugs", "pill", "pills", "powder", "gram", "ounce",
}

_MARKET_KEYWORDS = {
    "vendor", "seller", "shop", "market", "price", "btc", "bitcoin",
    "shipping", "escrow", "listing", "buy", "order", "stealth",
    "pgp", "wickr", "telegram", "walletaddress", "delivery",
}

_OFAC_KEYWORDS = {
    "sanction", "sanctions", "ofac", "sdn", "specially designated",
    "ransomware", "lazarus", "hydra", "tornado cash", "garantex",
    "illicit exchange", "mixer", "tumbler",
}

_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_HANDLE_RE = re.compile(r"(?<![\w])@[A-Za-z0-9_.-]{3,64}")
_LOCATION_RE = re.compile(r"\b(?:in|from|near|located in|based in)\s+([A-Z][A-Za-z .'-]{2,40})")


def _heuristic_enrichment(rec) -> dict[str, Any]:
    """Extract only values present in the record; never invent defaults."""
    text = rec.cleaned_text or ""
    candidates = rec.extracted_candidates or []
    phones = [
        str(candidate.get("value", "")).strip()
        for candidate in candidates
        if candidate.get("type") == "PHONE_NUMBER" and candidate.get("value")
    ]
    phones.extend(match.strip() for match in _PHONE_RE.findall(text))
    locations = [
        str(candidate.get("value", "")).strip()
        for candidate in candidates
        if candidate.get("type") in ("GPE", "LOC") and candidate.get("value")
    ]
    locations.extend(match.strip(" .,") for match in _LOCATION_RE.findall(text))
    handles = list(dict.fromkeys(_HANDLE_RE.findall(text)))
    return {
        "phone_number": next((value for value in phones if len(re.sub(r"\D", "", value)) >= 10), None),
        "last_known_location": next((value for value in locations if value), None),
        "platform_mentions": handles or None,
    }


def _suspect_match(db: Session, rec, enrichment: dict[str, Any]):
    """Find an existing suspect using exact signals first, then local fuzzy matching."""
    from entity_resolution import username_similarity
    from models import Suspect

    text = (rec.cleaned_text or "").lower()
    handles = [h.lower().lstrip("@") for h in (enrichment.get("platform_mentions") or [])]
    suspects = db.query(Suspect).all()
    fuzzy_candidates = []
    for suspect in suspects:
        aliases = [suspect.primary_alias]
        if suspect.aliases_json:
            try:
                aliases.extend(json.loads(suspect.aliases_json))
            except json.JSONDecodeError:
                pass
        aliases = [str(alias).strip() for alias in aliases if alias]
        wallets = {wallet.address.lower() for wallet in suspect.wallets}
        if any(alias.lower() in text for alias in aliases if len(alias) >= 4):
            return suspect
        if suspect.telegram_handle and suspect.telegram_handle.lower().lstrip("@") in handles:
            return suspect
        if wallets and any(address in text for address in wallets):
            return suspect
        for handle in handles:
            for alias in aliases:
                score = username_similarity(handle, alias).get("username_similarity", 0)
                if score >= 0.85:
                    fuzzy_candidates.append((score, suspect))
    return max(fuzzy_candidates, key=lambda item: item[0])[1] if fuzzy_candidates else None


def _append_summary(existing: str | None, additions: list[str]) -> str:
    current = [line for line in (existing or "").splitlines() if line.strip()]
    for addition in additions:
        if addition and addition not in current:
            current.append(addition)
    return "\n".join(current)


def _apply_enrichment(db: Session, rec, enrichment: dict[str, Any], tier: str, matched_suspect_id: int | None = None) -> bool:
    values = {key: value for key, value in enrichment.items() if value}
    if not values:
        return False

    suspect = None
    if matched_suspect_id is not None:
        from models import Suspect
        suspect = db.query(Suspect).filter(Suspect.id == matched_suspect_id).first()
    if suspect is None:
        suspect = _suspect_match(db, rec, values)
    if suspect is None:
        logger.info("[crawler_updater] tier=%s enrichment skipped: no confident existing suspect match", tier)
        return False

    if values.get("phone_number") and not suspect.phone_number:
        suspect.phone_number = values["phone_number"]
    if values.get("last_known_location") and not suspect.last_known_location:
        suspect.last_known_location = values["last_known_location"]

    existing_platforms = []
    if suspect.platform_mentions:
        try:
            existing_platforms = json.loads(suspect.platform_mentions)
        except json.JSONDecodeError:
            existing_platforms = [suspect.platform_mentions]
    merged_platforms = list(dict.fromkeys(existing_platforms + (values.get("platform_mentions") or [])))
    if merged_platforms:
        suspect.platform_mentions = json.dumps(merged_platforms)

    details = []
    if values.get("phone_number"):
        details.append(f"Phone observed: {values['phone_number']}")
    if values.get("last_known_location"):
        details.append(f"Location observed: {values['last_known_location']}")
    if values.get("platform_mentions"):
        details.append(f"Platform handles observed: {', '.join(values['platform_mentions'])}")
    details.append(f"Source: {rec.url}")
    suspect.enrichment_summary = _append_summary(suspect.enrichment_summary, details)
    suspect.enrichment_source_count = (suspect.enrichment_source_count or 0) + 1
    suspect.last_enriched_at = datetime.now(timezone.utc)
    suspect.data_origin = "base_dataset+crawler_enriched" if suspect.data_origin != "crawler_enriched" else suspect.data_origin
    logger.info("[crawler_updater] tier=%s enriched suspect=%s fields=%s", tier, suspect.id, sorted(values))
    return True


def _crawler_profile_identity(rec) -> tuple[str, list[str]]:
    """Extract a display identity without inventing one from crawler text."""
    aliases = []
    for candidate in (rec.extracted_candidates or []):
        candidate_type = str(candidate.get("type", "")).upper()
        value = str(candidate.get("value", "")).strip()
        if value and candidate_type in {"PERSON", "USERNAME", "HANDLE", "ACCOUNT"}:
            if value not in aliases:
                aliases.append(value)

    if aliases:
        return aliases[0], aliases

    digest = (rec.content_hash or str(rec.id))[:12]
    return f"Crawler observation {digest}", []


def _project_crawler_candidate(db: Session, rec, label: str, enrichment: dict[str, Any], matched_suspect_id: int | None) -> None:
    """Persist profile visibility for records without a confident suspect match."""
    from models import CrawlerCandidate

    if matched_suspect_id is not None or _suspect_match(db, rec, enrichment) is not None:
        return

    candidate = db.query(CrawlerCandidate).filter(
        CrawlerCandidate.source_record_id == rec.id
    ).first()
    primary_alias, aliases = _crawler_profile_identity(rec)
    confidence = rec.relevance_confidence or 0.0
    risk_by_label = {"ofac": 90, "elliptic": 75, "agora": 65, "no_match": 35}

    values = {
        "source_record_id": rec.id,
        "case_id": rec.case_id,
        "primary_alias": primary_alias,
        "aliases_json": json.dumps(aliases),
        "telegram_handle": (enrichment.get("platform_mentions") or [None])[0],
        "phone_number": enrichment.get("phone_number"),
        "last_known_location": enrichment.get("last_known_location"),
        "platform_mentions": json.dumps(enrichment.get("platform_mentions") or []),
        "notes": rec.relevance_reasoning or f"Crawler record classified as {label}.",
        "raw_text": rec.raw_text,
        "cleaned_text": rec.cleaned_text,
        "source_url": rec.url,
        "confidence_score": confidence,
        "risk_score": risk_by_label.get(label, 35),
        "data_origin": "crawler_candidate",
        "synthetic_generated": False,
        "synthetic_reason": None,
        "status": "crawler_candidate",
    }
    if candidate is None:
        db.add(CrawlerCandidate(**values))
        logger.info("[crawler_updater] projected crawler profile for record=%s label=%s", rec.id, label)
    else:
        for key, value in values.items():
            setattr(candidate, key, value)
        logger.info("[crawler_updater] refreshed crawler profile for record=%s label=%s", rec.id, label)


def _ai_decision(db: Session, rec) -> tuple[str | None, dict[str, Any], str, int | None] | None:
    """Use Gemini, then Anthropic, for optional structured classification."""
    import httpx

    from models import Suspect
    suspects = db.query(Suspect).all()
    entity_context = [
        {"id": s.id, "aliases": [s.primary_alias] + (json.loads(s.aliases_json) if s.aliases_json else []),
         "telegram_handle": s.telegram_handle,
         "wallets": [w.address for w in s.wallets]}
        for s in suspects
    ]
    prompt = f"""Classify this crawler record for a law-enforcement intelligence database.
Return only JSON with keys dataset_shape, matched_suspect_id, phone_number,
last_known_location, platform_mentions, confidence. dataset_shape must be one
of agora, elliptic, ofac, no_match. matched_suspect_id must be an existing id
from the supplied list or null. Never infer a value absent from the text.
Existing suspects: {json.dumps(entity_context)}
Record URL: {rec.url}
Record text: {rec.cleaned_text or ''}
Extracted candidates: {json.dumps(rec.extracted_candidates or [])}"""

    gemini_key = os.environ.get("GEMINI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    try:
        if gemini_key:
            response = httpx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                params={"key": gemini_key},
                json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            tier = "gemini"
        elif anthropic_key:
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": anthropic_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1000, "messages": [{"role": "user", "content": prompt}]},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()["content"][0]["text"]
            tier = "anthropic"
        else:
            return None
        result = json.loads(payload)
        shape = result.get("dataset_shape")
        enrichment = {key: result.get(key) for key in ("phone_number", "last_known_location", "platform_mentions") if result.get(key)}
        text_lower = (rec.cleaned_text or "").lower()
        if enrichment.get("phone_number") and re.sub(r"\D", "", str(enrichment["phone_number"])) not in re.sub(r"\D", "", rec.cleaned_text or ""):
            enrichment.pop("phone_number")
        if enrichment.get("last_known_location") and str(enrichment["last_known_location"]).lower() not in text_lower:
            enrichment.pop("last_known_location")
        if enrichment.get("platform_mentions"):
            mentions = enrichment["platform_mentions"] if isinstance(enrichment["platform_mentions"], list) else [enrichment["platform_mentions"]]
            enrichment["platform_mentions"] = [mention for mention in mentions if str(mention).lower() in text_lower]
            if not enrichment["platform_mentions"]:
                enrichment.pop("platform_mentions")
        return shape, enrichment, tier, result.get("matched_suspect_id")
    except Exception as exc:
        logger.warning("[crawler_updater] AI classification failed; using tier=heuristic fallback: %s", exc)
        return None

_AGORA_CATEGORIES = {
    "cannabis": "Drugs/Cannabis/Weed",
    "weed": "Drugs/Cannabis/Weed",
    "marijuana": "Drugs/Cannabis/Weed",
    "hash": "Drugs/Cannabis/Hash",
    "kush": "Drugs/Cannabis/Weed",
    "cocaine": "Drugs/Stimulants/Cocaine",
    "coke": "Drugs/Stimulants/Cocaine",
    "blow": "Drugs/Stimulants/Cocaine",
    "meth": "Drugs/Stimulants/Meth",
    "methamphetamine": "Drugs/Stimulants/Meth",
    "speed": "Drugs/Stimulants/Speed",
    "amphetamine": "Drugs/Stimulants/Speed",
    "heroin": "Drugs/Opioids/Heroin",
    "fentanyl": "Drugs/Opioids/Fentanyl",
    "oxycodone": "Drugs/Opioids/Oxycodone",
    "mdma": "Drugs/Ecstasy/MDMA",
    "ecstasy": "Drugs/Ecstasy/MDMA",
    "molly": "Drugs/Ecstasy/MDMA",
    "lsd": "Drugs/Psychedelics/LSD",
    "acid": "Drugs/Psychedelics/LSD",
    "mushrooms": "Drugs/Psychedelics/Mushrooms",
    "psilocybin": "Drugs/Psychedelics/Mushrooms",
    "dmt": "Drugs/Psychedelics/DMT",
    "ketamine": "Drugs/Dissociatives/Ketamine",
    "xanax": "Drugs/Prescription/Xanax",
    "adderall": "Drugs/Prescription/Adderall",
    "tramadol": "Drugs/Prescription/Tramadol",
}


# ---------------------------------------------------------------------------
# Heuristic classifier
# ---------------------------------------------------------------------------

def _text_tokens(text: str) -> set[str]:
    return {w.lower() for w in re.split(r"\W+", text or "") if len(w) > 2}


def _extract_wallets_from_record(rec) -> list[str]:
    """Collect all wallet addresses from extracted_candidates + text scan."""
    addrs = []
    seen = set()
    # 1. From entity extractor output stored in extracted_candidates
    for cand in (rec.extracted_candidates or []):
        if cand.get("type") in ("BITCOIN_ADDRESS", "ETHEREUM_ADDRESS"):
            a = cand.get("value", "").strip()
            if a and a not in seen:
                seen.add(a)
                addrs.append(a)
    # 2. Regex scan on cleaned_text (catches addresses extractor might have missed)
    text = rec.cleaned_text or ""
    for a in _BTC_RE.findall(text) + _ETH_RE.findall(text):
        if a not in seen:
            seen.add(a)
            addrs.append(a)
    return addrs


def _classify(rec) -> str:
    """
    Returns one of: "agora", "elliptic", "ofac", "no_match".
    "ofac" implies "elliptic" too (wallet addresses also appended there).
    """
    text = (rec.cleaned_text or "").lower()
    tokens = _text_tokens(text)
    keywords = set(rec.matched_keywords or [])
    all_tokens = tokens | {k.lower() for k in keywords}

    # OFAC: wallet address present AND sanctions keyword present
    has_wallet = bool(_extract_wallets_from_record(rec))
    has_ofac   = bool(all_tokens & _OFAC_KEYWORDS)
    if has_wallet and has_ofac:
        return "ofac"

    # ELLIPTIC: wallet address present (but no OFAC signal)
    if has_wallet:
        return "elliptic"

    # AGORA: drug keyword + market/transaction keyword
    has_drug   = bool(all_tokens & _DRUG_KEYWORDS)
    has_market = bool(all_tokens & _MARKET_KEYWORDS)
    if has_drug and has_market:
        return "agora"
    # relax: relevance_label=relevant + at least one drug keyword
    if rec.relevance_label == "relevant" and has_drug:
        return "agora"

    return "no_match"


# ---------------------------------------------------------------------------
# Field mappers
# ---------------------------------------------------------------------------

def _map_to_agora(rec) -> dict[str, str]:
    text = rec.cleaned_text or ""
    url  = rec.url or ""

    # Vendor ← domain of the URL, stripped of www.
    try:
        domain = urlparse(url).netloc.lstrip("www.").split(".")[0]
        vendor = domain.title() if domain else "CrawlerVendor"
    except Exception:
        vendor = "CrawlerVendor"

    # Category ← first matching drug keyword mapped to Agora category
    tokens = _text_tokens(text)
    category = "Drugs/Uncategorized"
    for tok in tokens:
        if tok in _AGORA_CATEGORIES:
            category = _AGORA_CATEGORIES[tok]
            break

    # Item ← first non-empty line of cleaned text, capped at 120 chars
    item_lines = [l.strip() for l in text.split("\n") if l.strip()]
    item = (item_lines[0] if item_lines else text[:120]).strip()[:120]

    # Price ← first BTC/USD price regex match
    price_match = _PRICE_RE.search(text)
    price = f"{price_match.group(1)} {price_match.group(2).upper()}" if price_match else ""

    # Origin ← first GPE/LOC entity from extracted_candidates
    origin = "Unknown"
    for cand in (rec.extracted_candidates or []):
        if cand.get("type") in ("GPE", "LOC") and cand.get("value"):
            origin = cand["value"].strip()[:50]
            break

    return {"Vendor": vendor, "Category": category, "Item": item,
            "Price": price, "Origin": origin}


def _map_to_elliptic(rec) -> list[dict[str, str]]:
    """Returns list of {address, class} rows (class=3 always)."""
    return [{"address": a, "class": "3"} for a in _extract_wallets_from_record(rec)]


def _map_to_elliptic_edges(rec) -> list[dict[str, str]]:
    """Returns list of {input_address, output_address} rows when >= 2 addresses found."""
    addrs = _extract_wallets_from_record(rec)
    if len(addrs) < 2:
        return []
    return [{"input_address": addrs[0], "output_address": a} for a in addrs[1:]]


def _map_to_ofac(rec) -> list[dict[str, str]]:
    url = rec.url or ""
    try:
        entity = urlparse(url).netloc or "OFAC Match via Crawler"
    except Exception:
        entity = "OFAC Match via Crawler"
    return [{"address": a, "entity_name": entity}
            for a in _extract_wallets_from_record(rec)]


# ---------------------------------------------------------------------------
# File writers (append-only, thread-safe via file lock pattern)
# ---------------------------------------------------------------------------

def _append_agora_csv(rows: list[dict]) -> None:
    """Appends rows to agora_sample.csv, creating the file+header if missing."""
    write_header = not os.path.exists(AGORA_CSV) or os.path.getsize(AGORA_CSV) == 0
    os.makedirs(os.path.dirname(AGORA_CSV), exist_ok=True)
    with open(AGORA_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Vendor", "Category", "Item", "Price", "Origin"])
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def _append_wallets_csv(rows: list[dict]) -> None:
    """Appends rows to wallets_classes.csv, deduplicating against existing addresses."""
    os.makedirs(os.path.dirname(WALLETS_CSV), exist_ok=True)
    existing: set[str] = set()
    if os.path.exists(WALLETS_CSV):
        with open(WALLETS_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.add(row.get("address", "").strip())
    new_rows = [r for r in rows if r["address"] not in existing]
    if not new_rows:
        return
    write_header = not os.path.exists(WALLETS_CSV) or os.path.getsize(WALLETS_CSV) == 0
    with open(WALLETS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["address", "class"])
        if write_header:
            writer.writeheader()
        writer.writerows(new_rows)


def _append_edgelist_csv(rows: list[dict]) -> None:
    """Appends rows to AddrAddr_edgelist.csv, deduplicating (src, dst) pairs."""
    os.makedirs(os.path.dirname(EDGELIST_CSV), exist_ok=True)
    existing: set[tuple[str, str]] = set()
    if os.path.exists(EDGELIST_CSV):
        with open(EDGELIST_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.add((row.get("input_address", ""), row.get("output_address", "")))
    new_rows = [r for r in rows
                if (r["input_address"], r["output_address"]) not in existing]
    if not new_rows:
        return
    write_header = not os.path.exists(EDGELIST_CSV) or os.path.getsize(EDGELIST_CSV) == 0
    with open(EDGELIST_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["input_address", "output_address"])
        if write_header:
            writer.writeheader()
        writer.writerows(new_rows)


def _append_ofac_json(rows: list[dict]) -> None:
    """Merges rows into sanctioned_addresses_with_entities.json, deduplicating by address."""
    os.makedirs(os.path.dirname(OFAC_JSON), exist_ok=True)
    existing: list[dict] = []
    existing_addrs: set[str] = set()
    if os.path.exists(OFAC_JSON) and os.path.getsize(OFAC_JSON) > 0:
        try:
            with open(OFAC_JSON, "r", encoding="utf-8") as f:
                existing = json.load(f)
            existing_addrs = {e.get("address", "") for e in existing}
        except (json.JSONDecodeError, OSError):
            existing = []
    new_entries = [r for r in rows if r["address"] not in existing_addrs]
    if not new_entries:
        return
    combined = existing + new_entries
    with open(OFAC_JSON, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)


def _populate_telegram_tables(db: Session, rec) -> None:
    """Project each non-empty crawler raw record into the existing Telegram tables."""
    from models import TelegramChannel, TelegramMessage

    raw_text = (rec.raw_text or "").strip()
    if not raw_text:
        return

    source_key = str(rec.source_id or "unknown")
    synthetic_channel_id = f"crawler-source-{source_key}"
    channel = db.query(TelegramChannel).filter(
        TelegramChannel.channel_id == synthetic_channel_id
    ).first()
    if channel is None:
        channel = TelegramChannel(
            channel_id=synthetic_channel_id,
            channel_name="Crawler Imported Intelligence",
            description="Synthetic channel populated from crawler raw records.",
            member_count=0,
        )
        db.add(channel)
        db.flush()

    content_key = rec.content_hash or hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    sender_handle = f"crawler_record_{content_key[:16]}"
    duplicate = db.query(TelegramMessage).filter(
        TelegramMessage.channel_id == channel.id,
        TelegramMessage.sender_handle == sender_handle,
        TelegramMessage.message_text == raw_text,
    ).first()
    if duplicate is None:
        db.add(TelegramMessage(
            channel_id=channel.id,
            sender_handle=sender_handle,
            message_text=raw_text,
            detected_wallets_json="[]",
            detected_keywords_json="[]",
            timestamp=datetime.now(timezone.utc),
        ))
    db.commit()


# ---------------------------------------------------------------------------
# Core processor
# ---------------------------------------------------------------------------

def process_pending_records(db: Session) -> int:
    """
    Reads all RawRecord rows with status 'pending_mapping' or 'relevant',
    classifies each, writes to the appropriate fixed dataset file, and
    updates the record's status.

    Returns the number of records processed.
    """
    from crawler.models.raw_record import RawRecord
    from models import CrawlerCandidate

    all_raw_records = db.query(RawRecord).all()
    for raw_record in all_raw_records:
        try:
            _populate_telegram_tables(db, raw_record)
        except Exception as exc:
            db.rollback()
            logger.error(
                "[crawler_updater] Telegram table population failed for record %s: %s",
                raw_record.id,
                exc,
                exc_info=True,
            )

    projected_review_records = 0
    review_queue = (
        db.query(RawRecord)
        .filter(RawRecord.status == "review_queue")
        .all()
    )
    for rec in review_queue:
        try:
            enrichment = _heuristic_enrichment(rec)
            before = db.query(CrawlerCandidate).filter(
                CrawlerCandidate.source_record_id == rec.id
            ).first()
            _project_crawler_candidate(
                db,
                rec,
                "review_queue",
                enrichment,
                None,
            )
            if before is None:
                projected_review_records += 1
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error(
                "[crawler_updater] Review-queue profile projection failed for record %s: %s",
                rec.id,
                exc,
                exc_info=True,
            )

    pending = (
        db.query(RawRecord)
        .filter(RawRecord.status.in_(["pending_mapping", "relevant"]))
        .all()
    )

    if not pending:
        return 0

    logger.info("[crawler_updater] Found %d pending RawRecord(s) to process.", len(pending))
    processed = 0

    for rec in pending:
        rec_id = str(rec.id)
        ai_result = _ai_decision(db, rec)
        if ai_result:
            ai_label, ai_enrichment, tier, ai_suspect_id = ai_result
            label = ai_label if ai_label in {"agora", "elliptic", "ofac", "no_match"} else _classify(rec)
            enrichment = ai_enrichment
        else:
            tier = "heuristic"
            label = _classify(rec)
            enrichment = {}
            ai_suspect_id = None
        heuristic_enrichment = _heuristic_enrichment(rec)
        for key, value in heuristic_enrichment.items():
            if value and not enrichment.get(key):
                enrichment[key] = value

        try:
            enriched = _apply_enrichment(db, rec, enrichment, tier, ai_suspect_id)
            if label == "agora":
                row = _map_to_agora(rec)
                _append_agora_csv([row])
                mapped_fields = list(row.keys())
                blank_fields  = [k for k, v in row.items() if not v]
                new_status    = "mapped_agora"
                logger.info(
                    "[crawler_updater] record=%s -> agora | mapped=%s | blank=%s",
                    rec_id, mapped_fields, blank_fields
                )

            elif label in ("elliptic", "ofac"):
                wallet_rows = _map_to_elliptic(rec)
                edge_rows   = _map_to_elliptic_edges(rec)
                _append_wallets_csv(wallet_rows)
                if edge_rows:
                    _append_edgelist_csv(edge_rows)
                new_status = "mapped_elliptic"
                logger.info(
                    "[crawler_updater] record=%s -> elliptic | wallets=%d | edges=%d",
                    rec_id, len(wallet_rows), len(edge_rows)
                )

                if label == "ofac":
                    ofac_rows = _map_to_ofac(rec)
                    _append_ofac_json(ofac_rows)
                    new_status = "mapped_ofac"
                    logger.info(
                        "[crawler_updater] record=%s -> ofac | entries=%d",
                        rec_id, len(ofac_rows)
                    )

            else:  # no_match
                new_status = "enriched" if enriched else "no_dataset_match"
                logger.info(
                    "[crawler_updater] record=%s -> no_match | "
                    "relevance=%s | keywords=%s | reason=no drug+market OR wallet signal",
                    rec_id,
                    rec.relevance_label,
                    rec.matched_keywords,
                )

            _project_crawler_candidate(db, rec, label, enrichment, ai_suspect_id)
            rec.status = new_status
            db.add(rec)
            db.commit()
            processed += 1

        except Exception as exc:
            logger.error(
                "[crawler_updater] Error processing record %s: %s",
                rec_id, exc, exc_info=True
            )
            db.rollback()

    logger.info("[crawler_updater] Finished batch: %d processed.", processed)
    return processed


# ---------------------------------------------------------------------------
# Background task entry point (called from main.py lifespan)
# ---------------------------------------------------------------------------

async def start_crawler_dataset_updater(poll_interval_seconds: int = 60) -> None:
    """
    Asyncio background task. Polls for new pending RawRecords every
    `poll_interval_seconds` and maps them into the fixed dataset files.

    If any records were mapped in a cycle (n > 0), immediately triggers
    db_sync.run_dataset_sync() so darknight.db reflects the new CSV rows
    before the next API query arrives.

    Usage in main.py lifespan:
        asyncio.create_task(start_crawler_dataset_updater())
    """
    from database import SessionLocal
    from db_sync import run_dataset_sync

    logger.info(
        "[crawler_updater] Background task started (poll interval: %ds).",
        poll_interval_seconds,
    )

    while True:
        db = None
        try:
            db = SessionLocal()
            n = process_pending_records(db)
            if n > 0:
                logger.info(
                    "[crawler_updater] Mapped %d record(s) this cycle — "
                    "triggering DB sync (reason: poll_cycle_update).",
                    n,
                )
                # Re-use the same session; both scripts are SQLAlchemy-based
                # and share the same transaction scope.
                run_dataset_sync(db, reason="poll_cycle_update")
            else:
                logger.debug("[crawler_updater] No new records this cycle — skipping DB sync.")
        except Exception as exc:
            logger.error("[crawler_updater] Unexpected error in poll cycle: %s", exc, exc_info=True)
        finally:
            if db is not None:
                db.close()

        await asyncio.sleep(poll_interval_seconds)


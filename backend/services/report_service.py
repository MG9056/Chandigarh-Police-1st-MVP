"""
Report Service — DarKnight Intelligence & Evidence Reporting

Orchestrates backend report generation for investigations:
1. Loads investigation details by public string investigation_id.
2. Gathers human-reviewed RELEVANT findings, promoted DataProvenance evidence, and RawRecords.
3. Constructs structured factual context clearly distinguishing:
   - ORIGINAL SOURCE DATA
   - EVIDENCE / PROVENANCE
   - INVESTIGATOR REVIEW NOTES
   - AI-GENERATED ANALYSIS
4. Assigns stable grounding tokens [EVIDENCE-1], [EVIDENCE-2]...
5. Instructs LLM (via existing AIService) with strict law-enforcement anti-hallucination rules.
6. Parses and validates structured report JSON, preserving evidence traceability mappings.
7. Persists Report record without modifying original findings, provenance, or raw records.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import (
    DataProvenance,
    Investigation,
    InvestigationFinding,
    InvestigationFindingStatus,
    RawRecord,
    Report,
    User,
)
from services.ai_service import ai_service

logger = logging.getLogger(__name__)


def build_evidence_context(
    investigation: Investigation,
    findings: List[InvestigationFinding],
    provenances: List[DataProvenance],
    raw_records_map: Dict[str, RawRecord],
) -> Tuple[str, Dict[str, Dict[str, Any]]]:
    """
    Builds a grounded evidence citation map and structured text context for the LLM.
    Assigns sequential stable tags [EVIDENCE-1], [EVIDENCE-2], ...
    """
    evidence_ref_map: Dict[str, Dict[str, Any]] = {}
    context_blocks: List[str] = []
    counter = 1

    # Map finding_id -> DataProvenance if promoted
    provenance_by_finding: Dict[int, DataProvenance] = {
        p.finding_id: p for p in provenances if p.finding_id is not None
    }

    # Process findings
    for finding in findings:
        ref_key = f"[EVIDENCE-{counter}]"
        counter += 1

        prov = provenance_by_finding.get(finding.id)
        raw_rec = raw_records_map.get(str(finding.raw_record_id))

        source_type = prov.source_type if prov else "Crawler Intelligence"
        source_name = (
            prov.source_name
            if prov
            else (str(raw_rec.source_id) if raw_rec and raw_rec.source_id else "Automated Collection")
        )
        source_url = raw_rec.url if raw_rec else (prov.source_url if prov else None)
        integrity_hash = (
            prov.integrity_hash
            if prov and prov.integrity_hash
            else (raw_rec.content_hash if raw_rec else None)
        )
        collected_at = (
            prov.collected_at.isoformat()
            if prov and prov.collected_at
            else (raw_rec.fetched_at.isoformat() if raw_rec and raw_rec.fetched_at else None)
        )

        # Truncate text snippet safely to prevent context overflow while preserving essential facts
        raw_text_snippet = ""
        if raw_rec:
            raw_text_snippet = (raw_rec.cleaned_text or raw_rec.raw_text or "").strip()
            if len(raw_text_snippet) > 1500:
                raw_text_snippet = raw_text_snippet[:1500] + " ... [TRUNCATED]"

        evidence_ref_map[ref_key] = {
            "ref": ref_key,
            "finding_id": finding.id,
            "provenance_id": prov.id if prov else None,
            "raw_record_id": str(finding.raw_record_id) if finding.raw_record_id else None,
            "source_type": source_type,
            "source_name": source_name,
            "source_url": source_url,
            "integrity_hash": integrity_hash,
            "collected_at": collected_at,
            "review_notes": finding.review_notes,
        }

        block = (
            f"=== EVIDENCE ITEM: {ref_key} ===\n"
            f"[PROVENANCE METADATA]\n"
            f"Source Type: {source_type}\n"
            f"Source Name / Channel: {source_name}\n"
            f"Source URL / Identifier: {source_url or 'N/A'}\n"
            f"Integrity Hash (SHA-256): {integrity_hash or 'N/A'}\n"
            f"Collected At: {collected_at or 'Unknown'}\n"
            f"\n[INVESTIGATOR REVIEW NOTES]\n"
            f"Status: {finding.review_status}\n"
            f"Notes: {finding.review_notes or 'No investigator notes provided.'}\n"
            f"Reviewed At: {finding.reviewed_at.isoformat() if finding.reviewed_at else 'N/A'}\n"
            f"\n[ORIGINAL SOURCE DATA]\n"
            f"Extracted Content: {raw_text_snippet or 'No raw text available.'}\n"
        )
        if raw_rec and raw_rec.matched_keywords:
            block += f"Matched Keywords: {json.dumps(raw_rec.matched_keywords)}\n"
        if raw_rec and raw_rec.extracted_candidates:
            block += f"Extracted Candidates / Entities: {json.dumps(raw_rec.extracted_candidates)}\n"

        context_blocks.append(block)

    # Also include any promoted DataProvenance records that weren't tied to the above findings
    handled_prov_ids = {p.id for p in provenance_by_finding.values()}
    for prov in provenances:
        if prov.id in handled_prov_ids:
            continue
        ref_key = f"[EVIDENCE-{counter}]"
        counter += 1

        raw_rec = raw_records_map.get(str(prov.raw_record_id)) if prov.raw_record_id else None
        raw_text_snippet = ""
        if raw_rec:
            raw_text_snippet = (raw_rec.cleaned_text or raw_rec.raw_text or "").strip()
            if len(raw_text_snippet) > 1500:
                raw_text_snippet = raw_text_snippet[:1500] + " ... [TRUNCATED]"

        evidence_ref_map[ref_key] = {
            "ref": ref_key,
            "finding_id": prov.finding_id,
            "provenance_id": prov.id,
            "raw_record_id": str(prov.raw_record_id) if prov.raw_record_id else None,
            "source_type": prov.source_type,
            "source_name": prov.source_name,
            "source_url": prov.source_url,
            "integrity_hash": prov.integrity_hash,
            "collected_at": prov.collected_at.isoformat() if prov.collected_at else None,
            "review_notes": "Directly promoted evidence item.",
        }

        block = (
            f"=== EVIDENCE ITEM: {ref_key} ===\n"
            f"[PROVENANCE METADATA]\n"
            f"Source Type: {prov.source_type}\n"
            f"Source Name / Channel: {prov.source_name}\n"
            f"Source URL / Identifier: {prov.source_url or 'N/A'}\n"
            f"Integrity Hash (SHA-256): {prov.integrity_hash or 'N/A'}\n"
            f"Collected At: {prov.collected_at.isoformat() if prov.collected_at else 'Unknown'}\n"
            f"\n[ORIGINAL SOURCE DATA]\n"
            f"Extracted Content: {raw_text_snippet or 'No raw text available.'}\n"
        )
        context_blocks.append(block)

    full_context = "\n----------------------------------------\n".join(context_blocks)
    return full_context, evidence_ref_map


def build_report_prompt(
    investigation: Investigation,
    evidence_context: str,
    valid_citations: List[str],
) -> str:
    """Builds the comprehensive instruction prompt for generating grounded intelligence reports."""
    citations_str = ", ".join(valid_citations)

    prompt = f"""You are generating an official, legally grounded Law Enforcement Intelligence Report for Chandigarh Police.

======================
INVESTIGATION OVERVIEW
======================
Case Number: {investigation.investigation_id}
Case Title: {investigation.title}
Case Type: {investigation.case_type or 'General Intelligence'}
Status: {investigation.status}
Priority: Level {investigation.priority}
Jurisdiction Unit: {investigation.unit or 'Cyber Crime Cell'}
Lead Investigator: {investigation.lead_investigator.full_name if investigation.lead_investigator else 'Unassigned'}
Description: {investigation.description or 'No case description provided.'}

======================
AVAILABLE EVIDENCE & PROVENANCE
======================
{evidence_context}

======================
STRICT MANDATORY RULES
======================
1. GROUNDING REQUIREMENT:
   - You MUST rely exclusively on the evidence provided above.
   - You MUST NOT invent, assume, or hallucinate ANY facts, suspects, handles, phone numbers, crypto wallet addresses, transaction IDs, locations, or dates.
   - If specific information (e.g., real-world identities, suspect locations, exact transaction amounts) is missing from the evidence, you MUST explicitly state that it is "Unknown / Not available in collected evidence".

2. EVIDENCE CITATIONS:
   - You MUST cite evidence references using the exact tags: {citations_str}.
   - Every factual finding, entity extraction, and timeline event MUST specify the relevant citation(s) from this list.
   - Do NOT create new citation tags not present in this list.

3. PROFESSIONAL LAW-ENFORCEMENT TONE:
   - Use objective, forensic intelligence report language.
   - Strictly distinguish verified facts from raw allegations, unverified chatter, or investigative indicators.
   - Clearly delineate investigator review opinions from raw source observations.

4. REQUIRED OUTPUT FORMAT:
   Return ONLY a valid JSON object with the following schema:
   {{
     "title": "Official Intelligence Report: [Title]",
     "executive_summary": "High-level forensic summary of the case and key evidence.",
     "investigation_overview": "Summary of case scope, background, and jurisdictional unit.",
     "key_findings": [
       {{
         "finding": "Specific factual finding description.",
         "citations": ["{valid_citations[0] if valid_citations else '[EVIDENCE-1]'}"],
         "verification_level": "VERIFIED_EVIDENCE | INVESTIGATIVE_LEAD | UNVERIFIED_CLAIM"
       }}
     ],
     "evidence_summary": "Summary of total evidence items analyzed and source types.",
     "entity_suspect_information": [
       {{
         "identifier": "Alias, username, wallet, or phone number",
         "role_or_activity": "Identified role or observed activity",
         "citations": ["{valid_citations[0] if valid_citations else '[EVIDENCE-1]'}"],
         "notes": "Contextual indicators or verified associations"
       }}
     ],
     "timeline": [
       {{
         "timestamp": "ISO or observed date/time string",
         "event": "Description of observed event",
         "citations": ["{valid_citations[0] if valid_citations else '[EVIDENCE-1]'}"],
         "source": "Source name"
       }}
     ],
     "intelligence_assessment": "Strategic intelligence assessment, observed threats, or recommended investigative next steps.",
     "source_and_evidence_references": [
       {{
         "citation": "{valid_citations[0] if valid_citations else '[EVIDENCE-1]'}",
         "source_type": "...",
         "source_name": "...",
         "description": "Short explanation of cited item"
       }}
     ],
     "ai_disclaimer": "This intelligence report was synthesized using AI assistance from verified investigative evidence records. AI analysis should be independently corroborated before judicial submission."
   }}
"""
    return prompt


def _parse_llm_json(response_text: str) -> Dict[str, Any]:
    """Extracts and parses JSON from the LLM response text."""
    clean_text = response_text.strip()

    # Remove markdown code block fences if present
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```(?:json)?\n?", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"\n?```$", "", clean_text)
        clean_text = clean_text.strip()

    # Try direct parsing
    try:
        return json.loads(clean_text)
    except Exception:
        pass

    # Try regex match for outermost JSON object
    match = re.search(r"(\{.*\})", clean_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # Fallback structure if JSON parse completely fails
    return {
        "title": "Intelligence Report (Raw Synthesis)",
        "executive_summary": clean_text[:500] if len(clean_text) > 500 else clean_text,
        "investigation_overview": "Automated synthesis generated from collected evidence.",
        "key_findings": [{"finding": clean_text, "citations": []}],
        "evidence_summary": "Evidence processed.",
        "entity_suspect_information": [],
        "timeline": [],
        "intelligence_assessment": "Please review full text content for detailed analysis.",
        "source_and_evidence_references": [],
        "ai_disclaimer": (
            "This intelligence report was synthesized using AI assistance from verified "
            "investigative evidence records. AI analysis should be independently corroborated "
            "before judicial submission."
        ),
    }


def _render_human_readable_report(
    structured: Dict[str, Any],
    investigation: Investigation,
    evidence_ref_map: Dict[str, Dict[str, Any]],
    model_used: str,
) -> str:
    """Formats structured report JSON into an official readable law-enforcement report document."""
    lines = [
        f"# {structured.get('title', f'Intelligence Report: {investigation.title}')}",
        "",
        "**Chandigarh Police — Department of Police Administration**  ",
        f"**Case Reference:** `{investigation.investigation_id}` | **Unit:** `{investigation.unit or 'Cyber Crime Cell'}`  ",
        f"**Generated At:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}` | **AI Model:** `{model_used}`  ",
        f"**Security Classification:** RESTRICTED / LAW ENFORCEMENT SENSITIVE  ",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        structured.get("executive_summary", "No executive summary provided."),
        "",
        "## 2. Investigation Overview",
        structured.get("investigation_overview", investigation.description or "N/A"),
        "",
        "## 3. Key Grounded Findings",
    ]

    findings = structured.get("key_findings", [])
    if findings:
        for idx, f in enumerate(findings, start=1):
            finding_text = f.get("finding", "")
            citations = " ".join(f.get("citations", []))
            level = f.get("verification_level", "")
            badge = f" `[{level}]`" if level else ""
            lines.append(f"{idx}. {finding_text}{badge} {citations}".strip())
    else:
        lines.append("No specific key findings noted.")

    lines.extend([
        "",
        "## 4. Entity & Suspect Information",
    ])

    entities = structured.get("entity_suspect_information", [])
    if entities:
        for ent in entities:
            ident = ent.get("identifier", "Unknown")
            role = ent.get("role_or_activity", "")
            citations = " ".join(ent.get("citations", []))
            notes = ent.get("notes", "")
            lines.append(f"- **{ident}**: {role} {citations} *(Notes: {notes})*".strip())
    else:
        lines.append("No distinct suspect entities identified in current evidence.")

    lines.extend([
        "",
        "## 5. Timeline of Events",
    ])

    timeline = structured.get("timeline", [])
    if timeline:
        for t in timeline:
            ts = t.get("timestamp", "Undated")
            event = t.get("event", "")
            citations = " ".join(t.get("citations", []))
            lines.append(f"- **[{ts}]** {event} {citations}".strip())
    else:
        lines.append("Timeline data not present in provided evidence.")

    lines.extend([
        "",
        "## 6. Strategic Intelligence Assessment",
        structured.get("intelligence_assessment", "No further intelligence assessment recorded."),
        "",
        "## 7. Source & Evidence Traceability",
    ])

    for ref_key, meta in evidence_ref_map.items():
        src_type = meta.get("source_type", "Unknown")
        src_name = meta.get("source_name", "N/A")
        hash_val = meta.get("integrity_hash") or "N/A"
        rec_id = meta.get("raw_record_id") or "N/A"
        lines.append(
            f"- **{ref_key}**: Source `{src_name}` ({src_type}) | Hash: `{hash_val}` | Record ID: `{rec_id}`"
        )

    lines.extend([
        "",
        "---",
        "",
        "### Legal & AI Compliance Disclaimer",
        structured.get(
            "ai_disclaimer",
            "This intelligence report was synthesized using AI assistance from verified "
            "investigative evidence records. AI analysis should be independently corroborated "
            "before judicial submission."
        ),
    ])

    return "\n".join(lines)


def generate_investigation_report(
    investigation_id: str,
    current_user: User,
    db: Session,
    title: Optional[str] = None,
) -> Report:
    """
    Executes the report generation pipeline for a specific investigation.

    Args:
        investigation_id: Public string case number (e.g. "INV-2026-001")
        current_user: Authenticated and authorized User
        db: Database session
        title: Optional custom report title

    Returns:
        Persisted Report entity.

    Raises:
        HTTPException(404): If investigation does not exist.
        HTTPException(400): If no relevant findings or promoted evidence exist.
        HTTPException(503): If AI service is unavailable or key not configured.
    """
    # 1. Load investigation
    investigation = (
        db.query(Investigation)
        .filter(Investigation.investigation_id == investigation_id)
        .first()
    )
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found.",
        )

    # 2. Query RELEVANT findings
    findings = (
        db.query(InvestigationFinding)
        .filter(
            InvestigationFinding.investigation_id == investigation.id,
            InvestigationFinding.review_status == InvestigationFindingStatus.RELEVANT,
        )
        .all()
    )

    # 3. Query promoted DataProvenance records for this investigation
    provenances = (
        db.query(DataProvenance)
        .filter(DataProvenance.investigation_id == investigation.investigation_id)
        .all()
    )

    # Guard: Require at least one reviewed/relevant finding or promoted evidence
    if not findings and not provenances:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot generate report: Investigation '{investigation_id}' has no relevant findings "
                f"or promoted evidence items to analyze."
            ),
        )

    # 4. Gather associated RawRecords
    raw_record_ids = {f.raw_record_id for f in findings if f.raw_record_id} | {
        p.raw_record_id for p in provenances if p.raw_record_id
    }
    raw_records_map: Dict[str, RawRecord] = {}
    if raw_record_ids:
        recs = db.query(RawRecord).all()
        for r in recs:
            if str(r.id) in raw_record_ids:
                raw_records_map[str(r.id)] = r

    # 5. Build structured evidence context and citations
    evidence_context, evidence_ref_map = build_evidence_context(
        investigation=investigation,
        findings=findings,
        provenances=provenances,
        raw_records_map=raw_records_map,
    )

    valid_citations = list(evidence_ref_map.keys())

    # 6. Build LLM prompt
    prompt = build_report_prompt(
        investigation=investigation,
        evidence_context=evidence_context,
        valid_citations=valid_citations,
    )

    system_instruction = (
        "You are an expert law-enforcement intelligence analysis system for Chandigarh Police DarKnight. "
        "Produce rigorous, strictly grounded intelligence reports citing provided evidence items. "
        "Never invent, assume, or hallucinate ungrounded facts."
    )

    # 7. Call AIService
    try:
        response_text, model_used = ai_service.generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.2,
        )
    except RuntimeError as re_err:
        logger.warning(f"AI service configuration error during report generation: {re_err}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI report generation service is currently unavailable. Intelligence service is not configured.",
        )
    except Exception as e:
        logger.error(f"Error during AI report generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI generation failed: {str(e)}",
        )

    # 8. Parse JSON and validate grounding
    structured_data = _parse_llm_json(response_text)

    # Validate that citations exist in evidence_ref_map (strip any fabricated citations)
    valid_keys_set = set(valid_citations)
    for section_key in ("key_findings", "entity_suspect_information", "timeline"):
        items = structured_data.get(section_key, [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and "citations" in item:
                    item["citations"] = [
                        c for c in item["citations"] if c in valid_keys_set
                    ]

    # Render formatted human-readable report
    human_report_text = _render_human_readable_report(
        structured=structured_data,
        investigation=investigation,
        evidence_ref_map=evidence_ref_map,
        model_used=model_used,
    )

    final_title = (
        title
        or structured_data.get("title")
        or f"Intelligence Report: {investigation.title}"
    )

    # 9. Persist Report model (original findings/evidence remain untouched)
    report_id_str = f"REP-{investigation.investigation_id}-{uuid4().hex[:8].upper()}"
    report = Report(
        report_id=report_id_str,
        investigation_id=investigation.investigation_id,
        title=final_title,
        content=human_report_text,
        structured_data=structured_data,
        evidence_references=evidence_ref_map,
        model_used=model_used,
        status="GENERATED",
        created_by_id=current_user.id,
        created_at=datetime.now(timezone.utc),
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    return report

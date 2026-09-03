from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional
import hashlib
import json

from database import get_db
from models import User, DataProvenance, AuditLog
from security import get_client_ip
from routers.auth_router import get_current_user
from audit_service import create_audit_log

router = APIRouter(prefix="/api", tags=["Evidence & Provenance"])

class ProvenanceCreateRequest(BaseModel):
    source_type: str  # Darknet, Telegram, Blockchain, Public Forum
    source_name: str
    source_identifier: str
    source_url: Optional[str] = None
    collection_method: Optional[str] = "Authorized automated collection"
    investigation_id: Optional[str] = None
    original_record_reference: Optional[str] = None
    raw_content: Optional[str] = None

@router.get("/evidence/{evidence_id}/download")
def download_evidence(
    evidence_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Simulated evidence file payload (for demonstration / hackathon feasibility)
    evidence_content = f"DARKNIGHT EVIDENCE REPORT\nID: {evidence_id}\nClassification: LAW ENFORCEMENT SENSITIVE\nCollected At: {datetime.now(timezone.utc).isoformat()}\nAuthorized Inspector: {current_user.full_name}".encode('utf-8')
    
    # Compute SHA-256 Integrity Hash
    sha256_hash = hashlib.sha256(evidence_content).hexdigest()

    # Audit log evidence download event
    create_audit_log(
        db=db,
        user=current_user,
        action="EVIDENCE_DOWNLOADED",
        result="SUCCESS",
        resource_type="EVIDENCE",
        resource_id=evidence_id,
        request=request,
        metadata={"integrity_sha256": sha256_hash}
    )

    return Response(
        content=evidence_content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="evidence_{evidence_id}.txt"',
            "X-Evidence-Integrity-SHA256": sha256_hash
        }
    )

@router.post("/provenance", status_code=status.HTTP_201_CREATED)
def record_provenance(
    req_data: ProvenanceCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    integrity_hash = None
    if req_data.raw_content:
        integrity_hash = hashlib.sha256(req_data.raw_content.encode('utf-8')).hexdigest()

    provenance = DataProvenance(
        source_type=req_data.source_type,
        source_name=req_data.source_name,
        source_identifier=req_data.source_identifier,
        source_url=req_data.source_url,
        collection_method=req_data.collection_method or "Authorized automated collection",
        investigation_id=req_data.investigation_id,
        original_record_reference=req_data.original_record_reference,
        integrity_hash=integrity_hash
    )
    db.add(provenance)
    db.commit()
    db.refresh(provenance)

    return {
        "message": "Data provenance recorded successfully",
        "provenance_id": provenance.id,
        "integrity_hash": provenance.integrity_hash,
        "collected_at": provenance.collected_at.isoformat()
    }

@router.get("/provenance/{record_id}")
def get_provenance(
    record_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    provenance = db.query(DataProvenance).filter(
        (DataProvenance.source_identifier == record_id) | (DataProvenance.id == (int(record_id) if record_id.isdigit() else -1))
    ).first()

    if not provenance:
        # Return fallback mock provenance structure for synthetic demo records
        return {
            "source_type": "Darknet Forum",
            "source_name": "Dread Archive",
            "source_identifier": record_id,
            "source_url": "http://dread4j62qdeao...onion/post/8841",
            "collection_method": "Authorized automated collection",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "original_record_reference": f"RAW-RECORD-{record_id}",
            "integrity_hash": hashlib.sha256(record_id.encode('utf-8')).hexdigest(),
            "ai_analysis_note": "Original raw record preserved without overwrite."
        }

    return {
        "id": provenance.id,
        "source_type": provenance.source_type,
        "source_name": provenance.source_name,
        "source_identifier": provenance.source_identifier,
        "source_url": provenance.source_url,
        "collection_method": provenance.collection_method,
        "collected_at": provenance.collected_at.isoformat(),
        "investigation_id": provenance.investigation_id,
        "original_record_reference": provenance.original_record_reference,
        "integrity_hash": provenance.integrity_hash
    }

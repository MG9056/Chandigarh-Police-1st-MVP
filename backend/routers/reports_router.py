"""
Reports Router — DarKnight Intelligence & Evidence Reporting (Phase 1)

Provides secured endpoints for generating, listing, retrieving,
and exporting intelligence reports for an investigation.

Endpoints:
- POST /api/investigations/{investigation_id}/reports
  Generates a grounded intelligence report.
  Requires: Authentication, Recent Re-Authentication (10m),
  v2 Investigation Modification Access.
  Auditing: Emits REPORT_GENERATED event on SUCCESS and FAILURE.

- GET /api/investigations/{investigation_id}/reports
  Lists all reports created for an investigation.
  Requires: READ permission.

- GET /api/investigations/{investigation_id}/reports/{report_id}
  Retrieves full report content and evidence citation map.
  Requires: READ permission.

- GET /api/investigations/{investigation_id}/reports/{report_id}/pdf
  Generates and downloads a PDF version of an existing report.
  Requires: READ permission.
"""

import logging
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from audit_service import create_audit_log
from database import get_db
from models import Investigation, Report, User
from rbac import (
    Permission,
    check_investigation_modification_access_v2,
    require_permission,
)
from routers.auth_router import get_current_user
from routers.reauth_router import require_recent_reauth
from services.report_service import generate_investigation_report


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/investigations/{investigation_id}/reports",
    tags=["Investigation Reports & Evidence"],
)


class ReportGenerateRequest(BaseModel):
    title: Optional[str] = None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_report(
    investigation_id: str,
    request: Request,
    req_body: Optional[ReportGenerateRequest] = None,
    current_user: User = Depends(get_current_user),
    reauth_user: User = Depends(require_recent_reauth),
    db: Session = Depends(get_db),
):
    """
    Generates a legally grounded intelligence report for an investigation.

    Verification chain:
    1. Authenticated user (get_current_user).
    2. Recent re-authentication within 10 minutes (require_recent_reauth).
    3. Investigation must exist.
    4. User must have modification access to this investigation.
    5. Investigation must have reviewed/relevant findings or promoted evidence.
    6. Generates grounded analysis using AIService.
    7. Persists Report without modifying raw collected records.
    8. Appends append-only REPORT_GENERATED audit log.
    """

    # 1. Verify investigation exists
    investigation = (
        db.query(Investigation)
        .filter(
            Investigation.investigation_id == investigation_id
        )
        .first()
    )

    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found.",
        )

    # 2. Verify authorization
    if not check_investigation_modification_access_v2(
        current_user,
        investigation,
        db,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You do not have permission to generate reports "
                "for this investigation."
            ),
        )

    # 3. Call report generation service
    custom_title = req_body.title if req_body else None

    try:
        report = generate_investigation_report(
            investigation_id=investigation_id,
            current_user=current_user,
            db=db,
            title=custom_title,
        )

    except HTTPException as http_err:
        error_summary = (
            "AI service unavailable"
            if http_err.status_code == 503
            else "Validation or processing error"
        )

        create_audit_log(
            db=db,
            action="REPORT_GENERATED",
            result="FAILURE",
            user=current_user,
            resource_type="INVESTIGATION",
            resource_id=investigation.investigation_id,
            request=request,
            metadata={
                "error": error_summary,
                "status_code": http_err.status_code,
            },
        )

        raise http_err

    except Exception as exc:
        logger.error(
            f"Unexpected error during report generation: {exc}"
        )

        create_audit_log(
            db=db,
            action="REPORT_GENERATED",
            result="FAILURE",
            user=current_user,
            resource_type="INVESTIGATION",
            resource_id=investigation.investigation_id,
            request=request,
            metadata={
                "error": "Unexpected report generation failure",
            },
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during report generation.",
        )

    # 4. Audit log success
    evidence_count = len(report.evidence_references or {})

    create_audit_log(
        db=db,
        action="REPORT_GENERATED",
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=investigation.investigation_id,
        request=request,
        metadata={
            "report_id": report.report_id,
            "evidence_count": evidence_count,
            "model": report.model_used,
        },
    )

    return {
        "message": (
            f"Report '{report.report_id}' generated successfully."
        ),
        "report_id": report.report_id,
        "investigation_id": report.investigation_id,
        "title": report.title,
        "content": report.content,
        "structured_data": report.structured_data,
        "evidence_references": report.evidence_references,
        "model_used": report.model_used,
        "status": report.status,
        "created_by_id": report.created_by_id,
        "created_at": report.created_at.isoformat(),
    }


@router.get("")
def list_reports(
    investigation_id: str,
    current_user: User = Depends(
        require_permission(Permission.READ)
    ),
    db: Session = Depends(get_db),
):
    """
    List all generated reports for an investigation.
    Requires broad READ permission.
    """

    investigation = (
        db.query(Investigation)
        .filter(
            Investigation.investigation_id == investigation_id
        )
        .first()
    )

    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found.",
        )

    reports = (
        db.query(Report)
        .filter(
            Report.investigation_id
            == investigation.investigation_id
        )
        .order_by(Report.created_at.desc())
        .all()
    )

    return {
        "investigation_id": investigation_id,
        "total": len(reports),
        "reports": [
            {
                "id": r.id,
                "report_id": r.report_id,
                "investigation_id": r.investigation_id,
                "title": r.title,
                "model_used": r.model_used,
                "status": r.status,
                "created_by_id": r.created_by_id,
                "created_by_email": (
                    r.created_by.email
                    if r.created_by
                    else None
                ),
                "created_at": (
                    r.created_at.isoformat()
                    if r.created_at
                    else None
                ),
            }
            for r in reports
        ],
    }


@router.get("/{report_id}")
def get_report(
    investigation_id: str,
    report_id: str,
    current_user: User = Depends(
        require_permission(Permission.READ)
    ),
    db: Session = Depends(get_db),
):
    """
    Retrieves full details and grounded evidence mappings
    for a specific report.

    Requires broad READ permission.
    """

    investigation = (
        db.query(Investigation)
        .filter(
            Investigation.investigation_id == investigation_id
        )
        .first()
    )

    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found.",
        )

    report = (
        db.query(Report)
        .filter(
            Report.report_id == report_id,
            Report.investigation_id
            == investigation.investigation_id,
        )
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Report '{report_id}' not found for "
                f"investigation '{investigation_id}'."
            ),
        )

    return {
        "id": report.id,
        "report_id": report.report_id,
        "investigation_id": report.investigation_id,
        "title": report.title,
        "content": report.content,
        "structured_data": report.structured_data,
        "evidence_references": report.evidence_references,
        "model_used": report.model_used,
        "status": report.status,
        "created_by_id": report.created_by_id,
        "created_by_email": (
            report.created_by.email
            if report.created_by
            else None
        ),
        "created_at": (
            report.created_at.isoformat()
            if report.created_at
            else None
        ),
    }


@router.get("/{report_id}/pdf")
def download_report_pdf(
    investigation_id: str,
    report_id: str,
    current_user: User = Depends(
        require_permission(Permission.READ)
    ),
    db: Session = Depends(get_db),
):
    """
    Generates and downloads a PDF version of an existing report.

    The PDF is generated entirely from information already stored
    in the database. No additional LLM call is made.
    """

    investigation = (
        db.query(Investigation)
        .filter(
            Investigation.investigation_id == investigation_id
        )
        .first()
    )

    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found.",
        )

    report = (
        db.query(Report)
        .filter(
            Report.report_id == report_id,
            Report.investigation_id
            == investigation.investigation_id,
        )
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Report '{report_id}' not found for "
                f"investigation '{investigation_id}'."
            ),
        )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        spaceAfter=12,
        alignment=TA_LEFT,
    )

    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        spaceBefore=14,
        spaceAfter=7,
    )

    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        spaceAfter=7,
    )

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
        title=report.title,
        author="DarKnight",
    )

    story = []

    # ---------------------------------------------------------
    # REPORT HEADER
    # ---------------------------------------------------------

    story.append(
        Paragraph(
            "DAR KNIGHT — INTELLIGENCE REPORT",
            title_style,
        )
    )

    story.append(
        Paragraph(
            report.title,
            heading_style,
        )
    )

    story.append(Spacer(1, 8))

    # ---------------------------------------------------------
    # ASSIGNED OFFICERS
    # ---------------------------------------------------------

    assigned_officers = []

    for assignment in investigation.assignments or []:
        if assignment.removed_at is not None:
            continue

        if assignment.assigned_to:
            officer = assignment.assigned_to

            assigned_officers.append(
                officer.full_name or officer.email
            )

    # ---------------------------------------------------------
    # LEAD INVESTIGATOR
    # ---------------------------------------------------------

    lead_investigator = "N/A"

    if investigation.lead_investigator:
        lead_investigator = (
            investigation.lead_investigator.full_name
            or investigation.lead_investigator.email
        )

    # ---------------------------------------------------------
    # CASE METADATA
    # ---------------------------------------------------------

    metadata = [
        [
            "Case ID",
            investigation.investigation_id,
        ],
        [
            "Case Title",
            investigation.title or "N/A",
        ],
        [
            "Case Type",
            investigation.case_type or "N/A",
        ],
        [
            "Case Status",
            investigation.status or "N/A",
        ],
        [
            "Priority",
            str(investigation.priority or "N/A"),
        ],
        [
            "Unit",
            investigation.unit or "N/A",
        ],
        [
            "Lead Investigator",
            lead_investigator,
        ],
        [
            "Assigned Officers",
            (
                ", ".join(assigned_officers)
                if assigned_officers
                else "None"
            ),
        ],
        [
            "Generated",
            (
                report.created_at.isoformat()
                if report.created_at
                else "N/A"
            ),
        ],
        [
            "Report ID",
            report.report_id,
        ],
    ]

    metadata_table = Table(
        metadata,
        colWidths=[120, 380],
    )

    metadata_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#eeeeee"),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#cccccc"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, -1),
                    "Helvetica",
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    "Helvetica-Bold",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ]
        )
    )

    story.append(metadata_table)

    # ---------------------------------------------------------
    # CASE DESCRIPTION
    # ---------------------------------------------------------

    if investigation.description:
        story.append(
            Paragraph(
                "CASE DESCRIPTION",
                heading_style,
            )
        )

        story.append(
            Paragraph(
                investigation.description,
                body_style,
            )
        )

    # ---------------------------------------------------------
    # REPORT CONTENT
    # ---------------------------------------------------------

    story.append(
        Paragraph(
            "INTELLIGENCE REPORT",
            heading_style,
        )
    )

    report_lines = report.content.split("\n")

    for line in report_lines:
        line = line.strip()

        if not line:
            story.append(Spacer(1, 5))
            continue

        escaped_line = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        story.append(
            Paragraph(
                escaped_line,
                body_style,
            )
        )

    # ---------------------------------------------------------
    # AI DISCLAIMER
    # ---------------------------------------------------------

    story.append(Spacer(1, 15))

    story.append(
        Paragraph(
            "AI-GENERATED CONTENT DISCLAIMER",
            heading_style,
        )
    )

    story.append(
        Paragraph(
            "This report was generated using DarKnight's "
            "AI-assisted intelligence analysis system. The "
            "report is grounded in reviewed findings and "
            "promoted evidence and should be validated by "
            "authorized investigators before operational or "
            "legal use.",
            body_style,
        )
    )

    # ---------------------------------------------------------
    # BUILD PDF
    # ---------------------------------------------------------

    document.build(story)

    buffer.seek(0)

    filename = f"{report.report_id}.pdf"

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            )
        },
    )
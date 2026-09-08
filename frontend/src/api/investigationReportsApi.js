import { apiFetch } from '../lib/apiClient';

/**
 * Investigation Reports API Client — Phase 1
 *
 * Wraps the investigation-scoped report endpoints:
 *   GET  /api/investigations/{id}/reports
 *   GET  /api/investigations/{id}/reports/{report_id}
 *   POST /api/investigations/{id}/reports
 *
 * POST requires recent re-authentication (within 10 minutes).
 * Callers must wrap the call with triggerReAuth() from AuthContext.
 */

/**
 * List all generated reports for an investigation.
 *
 * @param {string} investigationId  — e.g. "INV-2026-001"
 * @returns {Promise<{ investigation_id: string, total: number, reports: Array }>}
 */
export async function listInvestigationReports(investigationId) {
  const res = await apiFetch(`/api/investigations/${investigationId}/reports`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch investigation reports');
  }
  return res.json();
}

/**
 * Retrieve full content and evidence citations for a specific report.
 *
 * @param {string} investigationId
 * @param {string} reportId  — e.g. "REP-INV-2026-001-ABCD1234"
 * @returns {Promise<{
 *   id, report_id, investigation_id, title, content, structured_data,
 *   evidence_references, model_used, status, created_by_id,
 *   created_by_email, created_at
 * }>}
 */
export async function getInvestigationReport(investigationId, reportId) {
  const res = await apiFetch(
    `/api/investigations/${investigationId}/reports/${reportId}`,
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch report');
  }
  return res.json();
}

/**
 * Generate a new AI-grounded intelligence report for an investigation.
 *
 * IMPORTANT: This endpoint requires recent re-authentication (10-minute window).
 * The caller MUST invoke this function inside a triggerReAuth() callback.
 *
 * @param {string} investigationId
 * @param {string|null} title  — Optional custom title; backend/LLM auto-generates if omitted.
 * @returns {Promise<{
 *   message, report_id, investigation_id, title, content, structured_data,
 *   evidence_references, model_used, status, created_by_id, created_at
 * }>}
 * @throws {Error} 400 if no relevant findings/evidence, 403 if unauthorized,
 *                 503 if AI service unavailable
 */
export async function generateInvestigationReport(investigationId, title = null) {
  const body = title ? { title } : {};
  const res = await apiFetch(
    `/api/investigations/${investigationId}/reports`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to generate report');
  }
  return res.json();
}

/**
 * List all generated reports across all investigations.
 *
 * Used by the global Reports & Evidence dashboard.
 *
 * @returns {Promise<{ total: number, reports: Array }>}
 */
export async function listGlobalReports() {
  const res = await apiFetch('/api/reports');

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(
      err.detail || 'Failed to fetch global reports'
    );
  }

  return res.json();
}
export async function downloadInvestigationReportPdf(
  investigationId,
  reportId,
) {
  const res = await apiFetch(
    `/api/investigations/${investigationId}/reports/${reportId}/pdf`,
  );

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(
      err.detail || 'Failed to generate report PDF',
    );
  }

  return res.blob();
}
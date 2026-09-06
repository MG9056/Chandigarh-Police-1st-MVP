import { apiFetch } from '../lib/apiClient';

/**
 * Investigation Evidence API Client — Step 3
 *
 * Wraps the investigation-scoped evidence endpoints:
 *   GET  /api/investigations/{id}/evidence
 *   POST /api/investigations/{id}/evidence/promote/{finding_id}
 *
 * For global evidence list use GET /api/evidence directly via apiFetch.
 */

/**
 * List all evidence records promoted for this investigation.
 * @param {string} investigationId
 * @returns {Promise<{investigation_id, total, evidence: Array}>}
 */
export async function listInvestigationEvidence(investigationId) {
  const res = await apiFetch(`/api/investigations/${investigationId}/evidence`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch investigation evidence');
  }
  return res.json();
}

/**
 * Promote a RELEVANT InvestigationFinding to a formal evidence record.
 * Requires re-authentication (caller is responsible for triggering reauth flow).
 *
 * @param {string} investigationId
 * @param {number} findingId
 * @returns {Promise<{message, evidence_id, finding_id, integrity_hash, promoted_at}>}
 * @throws {Error} with detail message; 409 if already promoted, 400 if not RELEVANT, 403 if unauthorized
 */
export async function promoteToEvidence(investigationId, findingId) {
  const res = await apiFetch(
    `/api/investigations/${investigationId}/evidence/promote/${findingId}`,
    { method: 'POST' },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to promote finding to evidence');
  }
  return res.json();
}

/**
 * Global unscoped evidence list.
 * @param {number} skip
 * @param {number} limit
 * @returns {Promise<{total, skip, limit, evidence: Array}>}
 */
export async function listGlobalEvidence(skip = 0, limit = 50) {
  const res = await apiFetch(`/api/evidence?skip=${skip}&limit=${limit}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch global evidence');
  }
  return res.json();
}

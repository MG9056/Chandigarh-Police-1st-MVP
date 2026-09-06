import { apiFetch } from '../lib/apiClient';

/**
 * Investigation Findings API Client — Step 3
 *
 * Wraps the existing findings/list endpoint from Step 2 and the new evidence
 * promotion endpoint. The underlying intelligence review endpoints are untouched.
 */

/**
 * List reviewed findings for an investigation.
 * Calls GET /api/investigations/{id}/intelligence/findings/list
 *
 * @param {string} investigationId
 * @param {string|null} status - optional filter: RELEVANT | DISMISSED | PENDING_REVIEW
 * @param {number} skip
 * @param {number} limit
 * @returns {Promise<{investigation_id, total, skip, limit, findings: Array}>}
 */
export async function listInvestigationFindings(
  investigationId,
  status = null,
  skip = 0,
  limit = 100,
) {
  const params = new URLSearchParams({ skip, limit });
  if (status) params.set('status', status);
  const res = await apiFetch(
    `/api/investigations/${investigationId}/intelligence/findings/list?${params}`,
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch findings');
  }
  return res.json();
}

import { apiFetch } from '../lib/apiClient';

/**
 * Investigation Alerts API Client — Step 3
 */

/**
 * List alerts for an investigation.
 * @param {string} investigationId
 * @param {string|null} alertStatus - optional filter: OPEN | ACKNOWLEDGED | RESOLVED
 */
export async function listInvestigationAlerts(investigationId, alertStatus = null) {
  const qs = alertStatus ? `?status=${alertStatus}` : '';
  const res = await apiFetch(`/api/investigations/${investigationId}/alerts${qs}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch alerts');
  }
  return res.json();
}

/**
 * Create an alert for an investigation.
 * Requires re-auth (caller triggers reauth flow before calling).
 * @param {string} investigationId
 * @param {{ title, severity, description?, raw_record_id?, finding_id? }} payload
 */
export async function createAlert(investigationId, payload) {
  const res = await apiFetch(`/api/investigations/${investigationId}/alerts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to create alert');
  }
  return res.json();
}

/**
 * Resolve an investigation alert (requires re-auth).
 * @param {string} investigationId
 * @param {number} alertId
 */
export async function resolveAlert(investigationId, alertId) {
  const res = await apiFetch(
    `/api/investigations/${investigationId}/alerts/${alertId}/resolve`,
    { method: 'POST' },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to resolve alert');
  }
  return res.json();
}

/**
 * Global unscoped alert list.
 * @param {string|null} alertStatus
 * @param {number} skip
 * @param {number} limit
 */
export async function listGlobalAlerts(alertStatus = null, skip = 0, limit = 50) {
  const params = new URLSearchParams({ skip, limit });
  if (alertStatus) params.set('status', alertStatus);
  const res = await apiFetch(`/api/alerts?${params}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch global alerts');
  }
  return res.json();
}

/**
 * Hard-delete an alert (DGP/IGP only + re-auth).
 * @param {number} alertId
 */
export async function deleteAlert(alertId) {
  const res = await apiFetch(`/api/alerts/${alertId}`, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to delete alert');
  }
  return res.json();
}

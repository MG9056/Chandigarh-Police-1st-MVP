import { apiFetch } from '../lib/apiClient';

/**
 * Alerts & Suspicious Activity API Client.
 *
 * Uses apiFetch from ../lib/apiClient to ensure automatic JWT token refresh
 * on 401 Unauthorized responses.
 */

export async function fetchAlerts({ severity, status, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (severity && severity !== 'all') params.append('severity', severity.toLowerCase());
  if (status && status !== 'all') params.append('status', status.toLowerCase());
  if (limit) params.append('limit', String(limit));
  if (offset) params.append('offset', String(offset));

  const query = params.toString();
  const url = `/api/alerts${query ? `?${query}` : ''}`;

  const response = await apiFetch(url, { credentials: 'include' });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to fetch alerts (${response.status})`);
  }
  return response.json();
}

export async function fetchSuspiciousActivities({ status, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (status && status !== 'all') params.append('status', status.toLowerCase());
  if (limit) params.append('limit', String(limit));
  if (offset) params.append('offset', String(offset));

  const query = params.toString();
  const url = `/api/alerts/suspicious${query ? `?${query}` : ''}`;

  const response = await apiFetch(url, { credentials: 'include' });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to fetch suspicious activities (${response.status})`);
  }
  return response.json();
}

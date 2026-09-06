import { apiFetch } from '../lib/apiClient';
import API_BASE_URL from '../config/api';

export async function listInvestigationIntelligence(investigationId, statusFilter = null, skip = 0, limit = 50, query = null) {
  const params = new URLSearchParams();
  if (statusFilter) params.append('status', statusFilter);
  params.append('skip', skip);
  params.append('limit', limit);
  if (query?.trim()) params.append('q', query.trim());

  const response = await apiFetch(`${API_BASE_URL}/investigations/${investigationId}/intelligence?${params.toString()}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to list intelligence');
  }
  return response.json();
}

export async function getIntelligenceDetail(investigationId, rawRecordId) {
  const response = await apiFetch(`${API_BASE_URL}/investigations/${investigationId}/intelligence/${rawRecordId}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch intelligence detail');
  }
  return response.json();
}

export async function reviewIntelligence(investigationId, rawRecordId, reviewStatus, reviewNotes = '') {
  const response = await apiFetch(`${API_BASE_URL}/investigations/${investigationId}/intelligence/${rawRecordId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ review_status: reviewStatus, review_notes: reviewNotes }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to review intelligence');
  }
  return response.json();
}

export async function listInvestigationFindings(investigationId, statusFilter = null, skip = 0, limit = 50) {
  const params = new URLSearchParams();
  if (statusFilter) params.append('status', statusFilter);
  params.append('skip', skip);
  params.append('limit', limit);

  const response = await apiFetch(`${API_BASE_URL}/investigations/${investigationId}/intelligence/findings/list?${params.toString()}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to list findings');
  }
  return response.json();
}


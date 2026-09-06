import { apiFetch } from '../lib/apiClient';
import API_BASE_URL from '../config/api';

export async function listInvestigationSources(investigationId) {
  const response = await apiFetch(`${API_BASE_URL}/investigations/${investigationId}/sources`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to list sources');
  }
  return response.json();
}

export async function attachSource(investigationId, sourceId) {
  const response = await apiFetch(`${API_BASE_URL}/investigations/${investigationId}/sources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ source_id: sourceId }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to attach source');
  }
  return response.json();
}

export async function detachSource(investigationId, sourceId) {
  const response = await apiFetch(`${API_BASE_URL}/investigations/${investigationId}/sources/${sourceId}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to detach source');
  }
  return response.json();
}

export async function triggerSourceForInvestigation(investigationId, sourceId) {
  const response = await apiFetch(`${API_BASE_URL}/investigations/${investigationId}/sources/${sourceId}/trigger`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to trigger source');
  }
  return response.json();
}


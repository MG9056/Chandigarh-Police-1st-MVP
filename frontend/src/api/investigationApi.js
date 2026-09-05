import { apiFetch } from '../lib/apiClient';

/**
 * Investigation API client.
 * Uses apiFetch (not raw fetch) so the 15-min JWT access token is
 * auto-refreshed transparently on 401 responses.
 */

export async function createInvestigation(data) {
  const response = await apiFetch('/api/investigations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create investigation');
  }
  return response.json();
}

export async function listInvestigations(filters = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.append('status', filters.status);
  if (filters.priority !== undefined && filters.priority !== null) params.append('priority', filters.priority);
  if (filters.unit) params.append('unit', filters.unit);
  if (filters.skip) params.append('skip', filters.skip);
  if (filters.limit) params.append('limit', filters.limit);

  const response = await apiFetch(`/api/investigations?${params.toString()}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to list investigations');
  }
  return response.json();
}

export async function getInvestigation(investigationId) {
  const response = await apiFetch(`/api/investigations/${investigationId}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch investigation');
  }
  return response.json();
}

export async function updateInvestigation(investigationId, data) {
  const response = await apiFetch(`/api/investigations/${investigationId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update investigation');
  }
  return response.json();
}

export async function closeInvestigation(investigationId, data) {
  const response = await apiFetch(`/api/investigations/${investigationId}/close`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to close investigation');
  }
  return response.json();
}

export async function assignInvestigator(investigationId, assignedToId) {
  const response = await apiFetch(`/api/investigations/${investigationId}/assign`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ assigned_to_id: assignedToId }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to assign investigator');
  }
  return response.json();
}

export async function removeAssignment(investigationId, assignmentId) {
  const response = await apiFetch(`/api/investigations/${investigationId}/assign/${assignmentId}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to remove assignment');
  }
  return response.json();
}

export async function listAssignments(investigationId) {
  const response = await apiFetch(`/api/investigations/${investigationId}/assignments`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch assignments');
  }
  return response.json();
}


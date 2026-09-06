import { apiFetch } from '../lib/apiClient';
import API_BASE_URL from '../config/api';

export async function listInvestigationKeywords(investigationId) {
  const response = await apiFetch(`${API_BASE_URL}/investigations/${investigationId}/keywords`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to list keywords');
  }
  return response.json();
}

export async function addKeywordToInvestigation(investigationId, keywordId) {
  const response = await apiFetch(`${API_BASE_URL}/investigations/${investigationId}/keywords`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ keyword_id: keywordId }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to add keyword');
  }
  return response.json();
}

export async function removeKeywordFromInvestigation(investigationId, keywordId) {
  const response = await apiFetch(`${API_BASE_URL}/investigations/${investigationId}/keywords/${keywordId}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to remove keyword');
  }
  return response.json();
}


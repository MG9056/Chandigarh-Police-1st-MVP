import { apiFetch } from '../lib/apiClient';

/**
 * DarKnight AI API Client — Phase 1
 *
 * Communicates with backend /api/ai endpoints using centralized apiFetch
 * for session authentication, token refresh, and 401 handling.
 */

/**
 * Streams AI copilot message response.
 *
 * @param {Object} params
 * @param {string} params.message - User query
 * @param {Array} [params.history] - [{role: 'user'|'assistant', content: '...'}]
 * @param {Object} [params.context] - { activeView, investigationId }
 * @param {Function} onChunk - (chunkText: string) => void
 * @param {Function} onError - (errorMessage: string) => void
 * @param {Function} onComplete - () => void
 * @returns {Promise<void>}
 */
export async function streamAIMessage({ message, history, context }, onChunk, onError, onComplete) {
  try {
    const res = await apiFetch('/api/ai/message', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        history,
        context,
      }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const msg = errData.detail || "DarKnight AI couldn't process that request right now. Please try again.";
      if (onError) onError(msg);
      if (onComplete) onComplete();
      return;
    }

    if (!res.body) {
      if (onError) onError("No response stream received.");
      if (onComplete) onComplete();
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');

      // Keep the last incomplete line in the buffer
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data:')) continue;

        const dataStr = trimmed.slice(5).trim();
        if (dataStr === '[DONE]') {
          if (onComplete) onComplete();
          return;
        }

        try {
          const parsed = JSON.parse(dataStr);
          if (parsed.text && onChunk) {
            onChunk(parsed.text);
          }
        } catch {
          // If plain text data
          if (dataStr && onChunk) {
            onChunk(dataStr);
          }
        }
      }
    }

    // Process any remaining buffer content
    if (buffer.trim().startsWith('data:')) {
      const dataStr = buffer.trim().slice(5).trim();
      if (dataStr !== '[DONE]') {
        try {
          const parsed = JSON.parse(dataStr);
          if (parsed.text && onChunk) onChunk(parsed.text);
        } catch {
          if (dataStr && onChunk) onChunk(dataStr);
        }
      }
    }

    if (onComplete) onComplete();
  } catch (err) {
    console.error('Error streaming AI message:', err);
    if (onError) onError("Network failure or connection interrupted. Please try again.");
    if (onComplete) onComplete();
  }
}

/**
 * Fetches curated quick prompts for the AI empty state.
 * @returns {Promise<Array>}
 */
export async function fetchQuickPrompts() {
  try {
    const res = await apiFetch('/api/ai/prompts');
    if (res.ok) {
      const data = await res.json();
      return data.prompts || [];
    }
  } catch (err) {
    console.error('Error fetching quick prompts:', err);
  }
  return [];
}


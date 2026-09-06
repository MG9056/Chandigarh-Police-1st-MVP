import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { streamAIMessage, fetchQuickPrompts } from '../api/aiApi';

/**
 * Custom React Hook for DarKnight AI Copilot state management.
 *
 * Handles in-memory message history, streaming chunk accumulation, loading/error states,
 * quick prompts, and automatic state reset on logout.
 */
export function useAI(initialContext = {}) {
  const { isAuthenticated } = useAuth();
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState('idle'); // 'idle' | 'sending' | 'streaming' | 'completed' | 'error'
  const [errorMessage, setErrorMessage] = useState(null);
  const [quickPrompts, setQuickPrompts] = useState([]);
  const activeStreamIdRef = useRef(null);

  // Load quick prompts on mount
  useEffect(() => {
    if (isAuthenticated) {
      fetchQuickPrompts().then((prompts) => {
        if (prompts && prompts.length > 0) {
          setQuickPrompts(prompts);
        }
      });
    }
  }, [isAuthenticated]);

  // Reset conversation state on logout
  useEffect(() => {
    if (!isAuthenticated) {
      setMessages([]);
      setStatus('idle');
      setErrorMessage(null);
      activeStreamIdRef.current = null;
    }
  }, [isAuthenticated]);

  const clearChat = useCallback(() => {
    setMessages([]);
    setStatus('idle');
    setErrorMessage(null);
    activeStreamIdRef.current = null;
  }, []);

  const sendMessage = useCallback(
    async (text, contextOverride = null) => {
      const trimmed = text?.trim();
      if (!trimmed || status === 'sending' || status === 'streaming') return;

      setErrorMessage(null);
      setStatus('sending');

      const userMsgId = `user-${Date.now()}`;
      const assistantMsgId = `assistant-${Date.now()}`;
      activeStreamIdRef.current = assistantMsgId;

      const userMsg = {
        id: userMsgId,
        role: 'user',
        content: trimmed,
        timestamp: new Date().toISOString(),
      };

      const assistantMsg = {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
      };

      // Construct history for API request (excluding error messages)
      const history = messages
        .filter((m) => !m.error)
        .map((m) => ({ role: m.role, content: m.content }));

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setStatus('streaming');

      const mergedContext = {
        ...initialContext,
        ...(contextOverride || {}),
      };

      await streamAIMessage(
        {
          message: trimmed,
          history,
          context: mergedContext,
        },
        // On Chunk
        (chunkText) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? { ...msg, content: msg.content + chunkText }
                : msg
            )
          );
        },
        // On Error
        (errText) => {
          setStatus('error');
          setErrorMessage(errText);
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? {
                    ...msg,
                    content: msg.content || errText,
                    error: true,
                  }
                : msg
            )
          );
        },
        // On Complete
        () => {
          setStatus((prev) => (prev === 'error' ? 'error' : 'completed'));
          activeStreamIdRef.current = null;
        }
      );
    },
    [messages, status, initialContext]
  );

  return {
    messages,
    status,
    errorMessage,
    quickPrompts,
    sendMessage,
    clearChat,
    isStreaming: status === 'streaming' || status === 'sending',
  };
}


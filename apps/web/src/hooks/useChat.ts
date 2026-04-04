/**
 * hooks/useChat.ts — Custom hook for chat session state.
 *
 * Manages: session creation, message sending, phase tracking,
 * completeness, and queued question injection.
 *
 * T08: UI state management — no direct API import changes (T07 api/ frozen).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { createSession, sendMessage as apiSendMessage } from '../api/chatApi';
import type { ChatResponse, CreateSessionResponse } from '../types/chat';
import type { CompletenessInfo, ConversationPhase } from '../types/prd';

// ---------------------------------------------------------------------------
// Local message type (includes role for rendering)
// ---------------------------------------------------------------------------

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Hook state shape
// ---------------------------------------------------------------------------

export interface UseChatReturn {
  /** Active session UUID, null while initialising */
  sessionId: string | null;
  /** Ordered list of messages for display */
  messages: ChatMessage[];
  /** Latest ChatResponse from the API (has PRD data) */
  latestResponse: ChatResponse | null;
  /** Current conversation phase */
  phase: ConversationPhase;
  /** Actions available in the current phase */
  availableActions: string[];
  /** Completeness info from the latest response */
  completeness: CompletenessInfo;
  /** Suggested questions from the latest response */
  nextQuestions: string[];
  /** True while waiting for an API response */
  isLoading: boolean;
  /** Error message string, or null */
  error: string | null;
  /** Send a user message */
  sendMessage: (text: string) => Promise<void>;
  /** Queue a question into the input (sets the pendingInput) */
  setPendingInput: (text: string) => void;
  /** The pending input value (lifted so ChatPanel can consume) */
  pendingInput: string;
}

// ---------------------------------------------------------------------------
// Hook implementation
// ---------------------------------------------------------------------------

export function useChat(): UseChatReturn {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [latestResponse, setLatestResponse] = useState<ChatResponse | null>(null);
  const [phase, setPhase] = useState<ConversationPhase>('greeting');
  const [availableActions, setAvailableActions] = useState<string[]>([]);
  const [completeness, setCompleteness] = useState<CompletenessInfo>({
    filled: [],
    missing: [],
    progress: 0,
  });
  const [nextQuestions, setNextQuestions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingInput, setPendingInput] = useState('');

  // Prevent double-init in React strict mode
  const initRef = useRef(false);

  // ── Session initialisation ───────────────────────────────────────────────

  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;

    async function init() {
      try {
        const res: CreateSessionResponse = await createSession();
        setSessionId(res.session_id);

        // Add welcome message to chat
        const welcomeMsg: ChatMessage = {
          id: `sys-${Date.now()}`,
          role: 'assistant',
          content: res.message,
          timestamp: new Date().toISOString(),
        };
        setMessages([welcomeMsg]);
      } catch (err) {
        const msg = err instanceof Error ? err.message : '세션 생성에 실패했습니다.';
        setError(msg);
      }
    }

    void init();
  }, []);

  // ── Send message ─────────────────────────────────────────────────────────

  const sendMessage = useCallback(
    async (text: string) => {
      if (!sessionId || !text.trim() || isLoading) return;

      const trimmed = text.trim();

      // Optimistically add user message
      const userMsg: ChatMessage = {
        id: `u-${Date.now()}`,
        role: 'user',
        content: trimmed,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);
      setError(null);

      try {
        const response = await apiSendMessage({
          session_id: sessionId,
          message: trimmed,
        });

        // Add assistant reply
        const assistantMsg: ChatMessage = {
          id: `a-${Date.now()}`,
          role: 'assistant',
          content: response.assistant_message,
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);

        // Update derived state
        setLatestResponse(response);
        setPhase(response.current_phase);
        setAvailableActions(response.available_actions);
        setCompleteness(response.completeness);
        setNextQuestions(response.next_questions);
      } catch (err) {
        const msg = err instanceof Error ? err.message : '메시지 전송에 실패했습니다.';
        setError(msg);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, isLoading],
  );

  return {
    sessionId,
    messages,
    latestResponse,
    phase,
    availableActions,
    completeness,
    nextQuestions,
    isLoading,
    error,
    sendMessage,
    setPendingInput,
    pendingInput,
  };
}

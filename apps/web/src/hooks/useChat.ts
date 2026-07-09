/**
 * hooks/useChat.ts — Custom hook for chat session state.
 *
 * Manages: session creation, message sending, phase tracking,
 * completeness, and queued question injection.
 *
 * T08: UI state management — no direct API import changes (T07 api/ frozen).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { createSession, performAction as apiPerformAction, quickStartSimulation } from '../api/chatApi';
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
  /** Perform a specific phase transition action */
  performAction: (actionId: string, payload?: any) => Promise<void>;
  /** Cancel the current in-flight message request */
  cancelMessage: () => void;
  /** Run fast-track demo jump directly to validation/simulation */
  quickStart: (projectId: string) => Promise<void>;
  /** Currently streaming message content (assistant thinking) */
  streamingMessage: string | null;
  /** Current thinking status from the LLM */
  streamingStatus: string;
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
  const [streamingMessage, setStreamingMessage] = useState<string | null>(null);
  const [streamingStatus, setStreamingStatus] = useState<string>('');

  // Abort controller ref to cancel requests
  const abortControllerRef = useRef<AbortController | null>(null);

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

  const cancelMessage = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
    }
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
      setStreamingMessage(''); // Start streaming buffer
      setStreamingStatus('아이디어 분석 중...'); // Initial status
      setError(null);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        // Use Fetch API for streaming (SSE)
        const response = await fetch('/api/chat/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            session_id: sessionId,
            message: trimmed,
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Streaming failed: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error('Response body is null');

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          
          // SSE format: event: name\ndata: json\n\n
          const parts = buffer.split('\n\n');
          buffer = parts.pop() || '';

          for (const part of parts) {
            if (!part.trim()) continue;
            
            let currentEventType = '';
            const lines = part.split('\n');
            for (const line of lines) {
              const trimmedLine = line.trim();
              if (trimmedLine.startsWith('event:')) {
                currentEventType = trimmedLine.replace(/^event:\s*/, '').trim();
              } else if (trimmedLine.startsWith('data:')) {
                const dataStr = trimmedLine.replace(/^data:\s*/, '').trim();
                try {
                  const data = JSON.parse(dataStr);

                  if (currentEventType === 'token') {
                    setStreamingStatus(''); // Clear status when tokens appear
                    setStreamingMessage((prev) => (prev || '') + data.text);
                  } else if (currentEventType === 'status') {
                    setStreamingStatus(data.text);
                  } else if (currentEventType === 'done') {
                    // Add final assistant reply to list
                    const assistantMsg: ChatMessage = {
                      id: `a-${Date.now()}`,
                      role: 'assistant',
                      content: data.assistant_message,
                      timestamp: new Date().toISOString(),
                    };
                    setMessages((prev) => [...prev, assistantMsg]);

                    // Update derived state
                    setLatestResponse(data);
                    setPhase(data.current_phase);
                    setAvailableActions(data.available_actions);
                    setCompleteness(data.completeness);
                    setNextQuestions(data.next_questions || []);
                  } else if (currentEventType === 'error') {
                    setError(data.message);
                  }
                } catch (parseErr) {
                  console.error('Failed to parse SSE data:', dataStr, parseErr);
                }
              }
            }
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          console.log('Message request cancelled');
          return;
        }
        const msg = err instanceof Error ? err.message : '메시지 전송에 실패했습니다.';
        setError(msg);
      } finally {
        setIsLoading(false);
        setStreamingMessage(null); // End streaming buffer
        abortControllerRef.current = null;
      }
    },
    [sessionId, isLoading],
  );

  // ── Perform action ───────────────────────────────────────────────────────

  const performAction = useCallback(
    async (actionId: string, payload?: any) => {
      if (!sessionId || isLoading) return;
      setIsLoading(true);
      setError(null);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const response = await apiPerformAction(sessionId, actionId, payload, controller.signal);
        
        // Add assistant reply logic (optional, skip adding if silent action is preferred)
        if (response.assistant_message) {
            const assistantMsg: ChatMessage = {
                id: `a-${Date.now()}`,
                role: 'assistant',
                content: response.assistant_message,
                timestamp: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, assistantMsg]);
        }

        setLatestResponse(response);
        setPhase(response.current_phase);
        setAvailableActions(response.available_actions);
        setCompleteness(response.completeness);
        setNextQuestions(response.next_questions);
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') return;
        const msg = err instanceof Error ? err.message : '액션 수행에 실패했습니다.';
        setError(msg);
      } finally {
        setIsLoading(false);
        abortControllerRef.current = null;
      }
    },
    [sessionId, isLoading],
  );

  const quickStart = useCallback(
    async (projectId: string) => {
      if (!sessionId || isLoading) return;
      setIsLoading(true);
      setError(null);
      
      try {
        const response = await quickStartSimulation(sessionId, projectId);
        if (response.status === 'success') {
          // 1. Add instant jump messaging to chat
          const userMsg: ChatMessage = {
            id: `u-${Date.now()}`,
            role: 'user',
            content: "⚡ [퀵스타트] Simply AI Agent 데모 PRD를 로드하고 즉시 시뮬레이션 단계로 진입합니다.",
            timestamp: new Date().toISOString()
          };
          const assistantMsg: ChatMessage = {
            id: `a-${Date.now()}`,
            role: 'assistant',
            content: "알겠습니다. Simply AI Agent(가칭)의 완결된 B2B 엔터프라이즈 PRD 기획안과 상품개발/현업/C-level/이해관계자 생태계를 어우르는 12인의 다차원 전문가 그룹(PM, 아키텍트, 보안, 법무, CFO, QA, DevOps, 디자이너, 프론트엔드, 영업, CS/HR, 셀러대표)을 세션에 성공적으로 로드했습니다! 이제 정적 검증 및 시뮬레이션을 즉시 실행하실 수 있습니다.",
            timestamp: new Date().toISOString()
          };
          
          setMessages((prev) => [...prev, userMsg, assistantMsg]);
          
          // 2. Mock a full successful ChatResponse to trigger reactive updates in all panels
          const mockChatResponse: ChatResponse = {
            session_id: sessionId,
            assistant_message: assistantMsg.content,
            structured_prd: response.prd,
            prd_markdown: (response.prd.artifacts && typeof response.prd.artifacts === 'object' && 'prd_markdown' in response.prd.artifacts) 
              ? (response.prd.artifacts.prd_markdown as string) 
              : "## Simply AI Agent PRD",
            draft_status: 'ready_for_validation',
            completeness: {
              filled: ['product', 'users', 'problem', 'solution', 'scope', 'requirements', 'success_metrics', 'delivery', 'assumptions', 'risks', 'open_questions', 'validation'],
              missing: [],
              progress: 1.0
            },
            next_questions: [],
            current_phase: response.phase as ConversationPhase,
            available_actions: ['run_validation', 'save_checkpoint']
          };
          
          setLatestResponse(mockChatResponse);
          setPhase(response.phase as ConversationPhase);
          setAvailableActions(mockChatResponse.available_actions);
          setCompleteness(mockChatResponse.completeness);
          setNextQuestions([]);
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : '퀵스타트 진입에 실패했습니다.';
        setError(msg);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, isLoading]
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
    performAction,
    cancelMessage,
    quickStart,
    streamingMessage,
    streamingStatus,
  };
}

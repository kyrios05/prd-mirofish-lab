/**
 * api/chatApi.ts — Chat domain API functions.
 *
 * Mirrors all Chat endpoints from apps/api/app/routes/chat.py (T03 + T09).
 *
 * Endpoints covered
 * -----------------
 *   POST /chat/sessions                              → createSession()
 *   GET  /chat/sessions/{id}                         → getSessionStatus()
 *   POST /chat/message                               → sendMessage()
 *   POST /chat/sessions/{id}/checkpoint              → createCheckpoint()
 *   POST /chat/sessions/{id}/restore                 → restoreCheckpoint()
 *   GET  /chat/sessions/{id}/checkpoints             → listCheckpoints()
 *
 * T07: API wiring only — no state management, no side-effects beyond HTTP.
 */

import { get, post } from './client';
import type {
  ChatRequest,
  ChatResponse,
  CheckpointResponse,
  CheckpointsListResponse,
  CreateSessionResponse,
  RestoreRequest,
  RestoreResponse,
  SessionStatusResponse,
} from '../types/chat';

// ---------------------------------------------------------------------------
// Session management
// ---------------------------------------------------------------------------

/**
 * Create a new chat session.
 *
 * POST /chat/sessions → 201 CreateSessionResponse
 */
export async function createSession(): Promise<CreateSessionResponse> {
  return post<CreateSessionResponse>('/chat/sessions');
}

/**
 * Get the current status of an existing session.
 *
 * GET /chat/sessions/{session_id} → SessionStatusResponse
 *
 * @throws ApiError(404) if session not found
 */
export async function getSessionStatus(
  sessionId: string,
): Promise<SessionStatusResponse> {
  return get<SessionStatusResponse>(`/chat/sessions/${sessionId}`);
}

// ---------------------------------------------------------------------------
// Chat messaging
// ---------------------------------------------------------------------------

/**
 * Send a user message and receive the updated PRD draft + assistant reply.
 *
 * POST /chat/message → ChatResponse
 *
 * @throws ApiError(404) if session not found
 */
export async function sendMessage(req: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  return post<ChatResponse>('/chat/message', req, signal);
}

export async function performAction(sessionId: string, actionId: string, payload?: any, signal?: AbortSignal): Promise<ChatResponse> {
  return post<ChatResponse>('/chat/action', {
    session_id: sessionId,
    action_id: actionId,
    payload
  }, signal);
}

// ---------------------------------------------------------------------------
// Checkpointing (T09)
// ---------------------------------------------------------------------------

/**
 * Manually create a checkpoint for the session's current state.
 *
 * POST /chat/sessions/{session_id}/checkpoint?label=... → CheckpointResponse
 *
 * @param sessionId Active session UUID
 * @param label     Optional human-readable label for the checkpoint
 * @throws ApiError(404) if session not found
 */
export async function createCheckpoint(
  sessionId: string,
  label?: string,
): Promise<CheckpointResponse> {
  const params = label ? `?label=${encodeURIComponent(label)}` : '';
  return post<CheckpointResponse>(
    `/chat/sessions/${sessionId}/checkpoint${params}`,
  );
}

/**
 * Restore a session's PRD draft, turn_count, and phase from a checkpoint.
 * conversation_history is preserved.
 *
 * POST /chat/sessions/{session_id}/restore → RestoreResponse
 *
 * @throws ApiError(404) if session or checkpoint not found
 */
export async function restoreCheckpoint(
  sessionId: string,
  checkpointId: string,
): Promise<RestoreResponse> {
  const body: RestoreRequest = { checkpoint_id: checkpointId };
  return post<RestoreResponse>(`/chat/sessions/${sessionId}/restore`, body);
}

/**
 * List all checkpoints for a session, newest-first.
 *
 * GET /chat/sessions/{session_id}/checkpoints → CheckpointsListResponse
 *
 * @throws ApiError(404) if session not found
 */
export async function listCheckpoints(
  sessionId: string,
): Promise<CheckpointsListResponse> {
  return get<CheckpointsListResponse>(
    `/chat/sessions/${sessionId}/checkpoints`,
  );
}

// ---------------------------------------------------------------------------
// Quick-start simulation fast-track (Jump to validation/simulation)
// ---------------------------------------------------------------------------

export interface QuickStartResponse {
  status: string;
  phase: string;
  prd: Record<string, any>;
}

export async function quickStartSimulation(
  sessionId: string,
  projectId: string
): Promise<QuickStartResponse> {
  return post<QuickStartResponse>('/simulation/quick-start', {
    session_id: sessionId,
    project_id: projectId
  });
}


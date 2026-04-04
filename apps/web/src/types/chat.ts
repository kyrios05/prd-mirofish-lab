/**
 * types/chat.ts — Chat API request/response types.
 *
 * Mirrors the backend models in app/routes/chat.py (T03 + T09).
 * Field names and types match Pydantic model field definitions exactly.
 *
 * T07: type definitions only.
 */

import type { Checkpoint, CompletenessInfo, ConversationPhase, DraftStatus } from './prd';

// ---------------------------------------------------------------------------
// POST /chat/message
// ---------------------------------------------------------------------------

export interface ChatRequest {
  /** Active session UUID (from POST /chat/sessions). */
  session_id: string;
  /** User's chat message text (min length 1). */
  message: string;
  /** Optional extra context dict. */
  context?: Record<string, unknown>;
}

export interface ChatResponse {
  /** Echo of the session_id from the request. */
  session_id: string;
  /** Assistant's reply text. */
  assistant_message: string;
  /** Current PRD draft (PRDDocument.model_dump()), or null if no turns yet. */
  structured_prd: Record<string, unknown> | null;
  /** Rendered PRD as Markdown (T04). null when structured_prd is null. */
  prd_markdown: string | null;
  /** One of: 'empty' | 'incomplete' | 'ready_for_validation'. */
  draft_status: DraftStatus;
  /** Section completeness breakdown. */
  completeness: CompletenessInfo;
  /** Suggested next questions for missing sections (max 3). */
  next_questions: string[];
  /** Current conversation phase (T09). */
  current_phase: ConversationPhase;
  /** Actions available in the current phase (T09). */
  available_actions: string[];
}

// ---------------------------------------------------------------------------
// POST /chat/sessions
// ---------------------------------------------------------------------------

export interface CreateSessionResponse {
  /** Newly created session UUID. */
  session_id: string;
  /** ISO-8601 creation timestamp. */
  created_at: string;
  /** Welcome message. */
  message: string;
}

// ---------------------------------------------------------------------------
// GET /chat/sessions/{session_id}
// ---------------------------------------------------------------------------

export interface SessionStatusResponse {
  session_id: string;
  created_at: string;
  turn_count: number;
  has_prd_draft: boolean;
  draft_status: DraftStatus;
  completeness: CompletenessInfo;
  conversation_history: Array<{
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
  }>;
}

// ---------------------------------------------------------------------------
// POST /chat/sessions/{session_id}/checkpoint
// ---------------------------------------------------------------------------

export interface CheckpointResponse {
  /** UUID of the created checkpoint. */
  checkpoint_id: string;
  /** Human-readable label. */
  label: string;
  /** Phase at which the checkpoint was saved. */
  phase: string;
  /** Turn count at checkpoint. */
  turn_count: number;
}

// ---------------------------------------------------------------------------
// POST /chat/sessions/{session_id}/restore
// ---------------------------------------------------------------------------

export interface RestoreRequest {
  /** ID of the checkpoint to restore. */
  checkpoint_id: string;
}

export interface RestoreResponse {
  /** True if restore succeeded. */
  restored: boolean;
  /** Checkpoint ID that was restored. */
  checkpoint_id: string;
  /** Phase after restore. */
  current_phase: string;
  /** Turn count after restore. */
  turn_count: number;
  /** Whether PRD draft is present after restore. */
  prd_draft_present: boolean;
}

// ---------------------------------------------------------------------------
// GET /chat/sessions/{session_id}/checkpoints
// ---------------------------------------------------------------------------

export interface CheckpointsListResponse {
  session_id: string;
  checkpoints: Checkpoint[];
}

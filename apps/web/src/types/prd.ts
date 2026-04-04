/**
 * types/prd.ts — PRD domain types.
 *
 * Mirrors the backend Pydantic models in:
 *   app/schemas/common.py
 *   app/schemas/prd.py
 *   app/services/conversation_state.py
 *
 * T07: type definitions only — no runtime logic.
 * T08: UI components consume these types.
 */

// ---------------------------------------------------------------------------
// Conversation phase
// ---------------------------------------------------------------------------

/**
 * Explicit phases of the PRD generation conversation (T09).
 * Mirrors ConversationPhase(str, Enum) in conversation_state.py.
 */
export type ConversationPhase =
  | 'greeting'
  | 'interviewing'
  | 'reviewing'
  | 'ready_for_validation'
  | 'validated';

// ---------------------------------------------------------------------------
// PRD completeness
// ---------------------------------------------------------------------------

/**
 * Draft readiness status returned by completeness.py.
 */
export type DraftStatus = 'empty' | 'incomplete' | 'ready_for_validation';

/**
 * Completeness snapshot of the current PRD draft.
 * Mirrors CompletenessInfo in routes/chat.py.
 */
export interface CompletenessInfo {
  /** Section names that are present and non-empty. */
  filled: string[];
  /** Section names that are absent or empty. */
  missing: string[];
  /** Ratio of filled / total sections (0–1). */
  progress: number;
}

// ---------------------------------------------------------------------------
// PRD document
// ---------------------------------------------------------------------------

/**
 * Full PRD document as returned by PRDDocument.model_dump().
 * Using a flexible record type since the structure is deeply nested and
 * evolves with PRD_SCHEMA.json.  T08 components can cast inner sections
 * to more specific types as needed.
 */
export type PRDDocument = Record<string, unknown>;

// ---------------------------------------------------------------------------
// Checkpoint & phase history (T09)
// ---------------------------------------------------------------------------

/**
 * A point-in-time snapshot of the PRD draft and conversation state.
 * Mirrors Checkpoint dataclass in conversation_state.py.
 */
export interface Checkpoint {
  /** UUID4 string. */
  checkpoint_id: string;
  /** ISO-8601 UTC timestamp. */
  created_at: string;
  /** ConversationPhase value at the time of save. */
  phase: string;
  /** turn_count at the time of save. */
  turn_count: number;
  /** Deep copy of current_prd_draft at the time of save. */
  prd_snapshot: Record<string, unknown>;
  /** Human-readable label, e.g. "Turn 3 - users+problem 완성 후". */
  label: string;
}

/**
 * Records a single phase transition event.
 * Mirrors PhaseTransition dataclass in conversation_state.py.
 */
export interface PhaseTransition {
  from_phase: string;
  to_phase: string;
  /** Cause of the transition, e.g. "auto_advance", "user_request". */
  trigger: string;
  /** ISO-8601 UTC timestamp. */
  timestamp: string;
}

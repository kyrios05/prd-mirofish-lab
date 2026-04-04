/**
 * types/index.ts — Barrel re-export of all domain types.
 *
 * Usage:
 *   import type { ChatResponse, ConversationPhase, ValidationResult } from '@/types';
 *
 * T07: aggregation only, no logic.
 */

export type {
  // prd.ts
  ConversationPhase,
  DraftStatus,
  CompletenessInfo,
  PRDDocument,
  Checkpoint,
  PhaseTransition,
} from './prd';

export type {
  // chat.ts
  ChatRequest,
  ChatResponse,
  CreateSessionResponse,
  SessionStatusResponse,
  CheckpointResponse,
  RestoreRequest,
  RestoreResponse,
  CheckpointsListResponse,
} from './chat';

export type {
  // validation.ts
  ValidationRequest,
  SchemaErrorItem,
  ValidationResult,
  ValidationConfig,
  SimulationSpec,
  ValidationStatus,
  ValidationResponse,
} from './validation';

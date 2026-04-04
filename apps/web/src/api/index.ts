/**
 * api/index.ts — Barrel re-export of all API modules.
 *
 * Usage:
 *   import { createSession, sendMessage } from '@/api';
 *   import { runValidation } from '@/api';
 *   import { BASE_URL, ApiError } from '@/api';
 *
 * T07: aggregation only, no logic.
 */

// Base client (error class + request helpers)
export { BASE_URL, ApiError, request, get, post } from './client';

// Chat domain (6 functions)
export {
  createSession,
  getSessionStatus,
  sendMessage,
  createCheckpoint,
  restoreCheckpoint,
  listCheckpoints,
} from './chatApi';

// Validation domain (3 functions)
export { runValidation, packageOnly, schemaCheck } from './validationApi';

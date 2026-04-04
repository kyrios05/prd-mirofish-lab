/**
 * api/validationApi.ts — Validation domain API functions.
 *
 * Mirrors all Validation endpoints from apps/api/app/routes/validation.py
 * (T02, T05, T06).
 *
 * Endpoints covered
 * -----------------
 *   POST /validation/run          → runValidation()   (full pipeline, status="completed")
 *   POST /validation/package      → packageOnly()     (T05 only, status="packaged")
 *   POST /validation/schema-check → schemaCheck()     (T02 only)
 *
 * T07: API wiring only — no state management, no side-effects beyond HTTP.
 */

import { post } from './client';
import type { ValidationRequest, ValidationResponse } from '../types/validation';

// ---------------------------------------------------------------------------
// Full validation pipeline (T02 + T05 + T06)
// ---------------------------------------------------------------------------

/**
 * Run the full validation pipeline against a PRD dict.
 *
 * Pipeline: JSON Schema (T02) → Pydantic build (T02) →
 *           SimulationSpec (T05) → Mock engine (T06)
 *
 * POST /validation/run → ValidationResponse
 *
 * On success:  status="completed", result populated, simulation_spec present
 * On schema error: status="schema_invalid", schema_errors non-empty
 *
 * @throws ApiError on server error (5xx)
 */
export async function runValidation(
  req: ValidationRequest,
): Promise<ValidationResponse> {
  return post<ValidationResponse>('/validation/run', req);
}

// ---------------------------------------------------------------------------
// Package-only (T05, no mock engine)
// ---------------------------------------------------------------------------

/**
 * Validate and package the PRD as a SimulationSpec without running the
 * mock validation engine.
 *
 * POST /validation/package → ValidationResponse
 *
 * On success: status="packaged", simulation_spec present, result=null
 *
 * Useful for CI/CD debugging — verifies spec assembly without T06 overhead.
 *
 * @throws ApiError on server error (5xx)
 */
export async function packageOnly(
  req: ValidationRequest,
): Promise<ValidationResponse> {
  return post<ValidationResponse>('/validation/package', req);
}

// ---------------------------------------------------------------------------
// Schema check only (T02)
// ---------------------------------------------------------------------------

/**
 * Run JSON Schema validation only — no Pydantic build, no packaging,
 * no mock engine.
 *
 * POST /validation/schema-check → ValidationResponse
 *
 * schema_valid: true/false; schema_errors populated on failure;
 * simulation_spec and result are always null.
 *
 * @throws ApiError on server error (5xx)
 */
export async function schemaCheck(
  req: ValidationRequest,
): Promise<ValidationResponse> {
  return post<ValidationResponse>('/validation/schema-check', req);
}

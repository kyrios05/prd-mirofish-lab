/**
 * types/validation.ts — Validation API request/response types.
 *
 * Mirrors the backend models in:
 *   app/routes/validation.py    (ValidationRequest, ValidationResponse, SchemaErrorItem)
 *   app/schemas/simulation.py   (SimulationSpec, ValidationConfig)
 *   app/schemas/common.py       (ValidationResult)
 *
 * T07: type definitions only.
 */

// ---------------------------------------------------------------------------
// Request
// ---------------------------------------------------------------------------

export interface ValidationRequest {
  /** Session-derived project identifier, e.g. "proj-<session_id[:8]>". */
  project_id: string;
  /** Raw PRD dict (PRDDocument.model_dump() output). */
  prd: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Schema validation
// ---------------------------------------------------------------------------

export interface SchemaErrorItem {
  /** Human-readable error description. */
  message: string;
  /** JSON Pointer path to the offending node. */
  path: string;
  /** JSON Pointer path within the schema. */
  schema_path: string;
  /** jsonschema validator keyword, e.g. "required", "type". */
  validator: string;
}

// ---------------------------------------------------------------------------
// Validation result (T06 mock engine output)
// Mirrors ValidationResult in app/schemas/common.py.
// ---------------------------------------------------------------------------

export interface ValidationResult {
  /** 1–2 sentence product + goals summary. */
  summary: string;
  /** Top risks derived from focus_areas. */
  top_risks: string[];
  /** Flagged absent non-functional requirements or missing sections. */
  missing_requirements: string[];
  /** Persona-driven objections. */
  stakeholder_objections: string[];
  /** Scope reduction proposals when confidence is low. */
  scope_adjustments: string[];
  /** must_answer_questions + high-severity open questions. */
  recommended_questions: string[];
  /** Suggestions for filling empty optional fields. */
  rewrite_suggestions: string[];
}

// ---------------------------------------------------------------------------
// SimulationSpec (T05)
// Mirrors SimulationSpec in app/schemas/simulation.py.
// ---------------------------------------------------------------------------

export interface ValidationConfig {
  goals: string[];
  stakeholder_personas: Record<string, unknown>[];
  simulation_requirement: string;
  validation_templates: string[];
  must_answer_questions: string[];
  /** Auto-extracted from risks.title + open_questions.text. */
  focus_areas: string[];
}

export interface SimulationSpec {
  /** UUID4 string. */
  spec_id: string;
  /** ISO-8601 UTC creation timestamp. */
  created_at: string;
  /** { name, one_liner, category, stage, project_id } summary dict. */
  prd_summary: Record<string, unknown>;
  /** Full PRDDocument.model_dump() output. */
  prd_structured: Record<string, unknown>;
  /** render_prd_markdown() output (T04). */
  prd_markdown: string;
  /** Assembled validation configuration for MiroFish. */
  validation_config: ValidationConfig;
}

// ---------------------------------------------------------------------------
// Validation API response
// Mirrors ValidationResponse in app/routes/validation.py.
// ---------------------------------------------------------------------------

export type ValidationStatus =
  | 'completed'      // /validation/run success (T06 populated)
  | 'packaged'       // /validation/package success (no mock engine)
  | 'schema_invalid' // JSON schema check failed
  | 'prd_invalid'    // Pydantic construction failed
  | 'error';         // Unexpected server error

export interface ValidationResponse {
  /** Session-derived project identifier. */
  project_id: string;
  /** True if PRD passes JSON Schema validation. */
  schema_valid: boolean;
  /** Non-empty when schema_valid is false. */
  schema_errors: SchemaErrorItem[];
  /** Current pipeline stage outcome. */
  status: ValidationStatus;
  /** Populated by T06 mock engine on /validation/run. null otherwise. */
  result: ValidationResult | null;
  /** Populated by T05 packager. null on schema/prd errors. */
  simulation_spec: Record<string, unknown> | null;
}

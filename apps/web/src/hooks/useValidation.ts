/**
 * hooks/useValidation.ts — Custom hook for validation state.
 *
 * Manages: running validation, displaying results, error handling.
 *
 * T08: UI state management — no direct API changes (T07 api/ frozen).
 */

import { useCallback, useState } from 'react';
import { runValidation as apiRunValidation } from '../api/validationApi';
import type { ValidationResponse } from '../types/validation';

// ---------------------------------------------------------------------------
// Hook state shape
// ---------------------------------------------------------------------------

export interface UseValidationReturn {
  /** Latest validation response from the API */
  validationResponse: ValidationResponse | null;
  /** True while running validation */
  isRunning: boolean;
  /** Error message string, or null */
  error: string | null;
  /** Run validation against the given PRD dict */
  runValidation: (projectId: string, prd: Record<string, unknown>) => Promise<void>;
  /** Clear the current validation result */
  clearResult: () => void;
}

// ---------------------------------------------------------------------------
// Hook implementation
// ---------------------------------------------------------------------------

export function useValidation(): UseValidationReturn {
  const [validationResponse, setValidationResponse] = useState<ValidationResponse | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runValidation = useCallback(
    async (projectId: string, prd: Record<string, unknown>) => {
      setIsRunning(true);
      setError(null);

      try {
        const response = await apiRunValidation({ project_id: projectId, prd });
        setValidationResponse(response);
      } catch (err) {
        const msg = err instanceof Error ? err.message : '검증 실행에 실패했습니다.';
        setError(msg);
      } finally {
        setIsRunning(false);
      }
    },
    [],
  );

  const clearResult = useCallback(() => {
    setValidationResponse(null);
    setError(null);
  }, []);

  return {
    validationResponse,
    isRunning,
    error,
    runValidation,
    clearResult,
  };
}

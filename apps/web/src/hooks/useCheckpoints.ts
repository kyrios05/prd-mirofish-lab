/**
 * hooks/useCheckpoints.ts — Custom hook for checkpoint management.
 *
 * Manages: listing, creating, and restoring session checkpoints.
 *
 * T08: UI state management — no direct API changes (T07 api/ frozen).
 */

import { useCallback, useState } from 'react';
import {
  createCheckpoint as apiCreateCheckpoint,
  listCheckpoints as apiListCheckpoints,
  restoreCheckpoint as apiRestoreCheckpoint,
} from '../api/chatApi';
import type { Checkpoint } from '../types/prd';

// ---------------------------------------------------------------------------
// Hook state shape
// ---------------------------------------------------------------------------

export interface UseCheckpointsReturn {
  /** List of checkpoints for the current session */
  checkpoints: Checkpoint[];
  /** True while fetching/creating/restoring */
  isLoading: boolean;
  /** Error message string, or null */
  error: string | null;
  /** Fetch all checkpoints for the session */
  fetchCheckpoints: (sessionId: string) => Promise<void>;
  /** Create a new manual checkpoint */
  createCheckpoint: (sessionId: string, label?: string) => Promise<void>;
  /** Restore a checkpoint by ID */
  restore: (sessionId: string, checkpointId: string) => Promise<void>;
}

// ---------------------------------------------------------------------------
// Hook implementation
// ---------------------------------------------------------------------------

export function useCheckpoints(): UseCheckpointsReturn {
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCheckpoints = useCallback(async (sessionId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiListCheckpoints(sessionId);
      setCheckpoints(res.checkpoints);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '체크포인트 목록을 가져오는데 실패했습니다.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createCheckpoint = useCallback(
    async (sessionId: string, label?: string) => {
      setIsLoading(true);
      setError(null);
      try {
        await apiCreateCheckpoint(sessionId, label);
        // Refresh the list after creation
        const res = await apiListCheckpoints(sessionId);
        setCheckpoints(res.checkpoints);
      } catch (err) {
        const msg = err instanceof Error ? err.message : '체크포인트 생성에 실패했습니다.';
        setError(msg);
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const restore = useCallback(
    async (sessionId: string, checkpointId: string) => {
      setIsLoading(true);
      setError(null);
      try {
        await apiRestoreCheckpoint(sessionId, checkpointId);
        // Refresh list after restore
        const res = await apiListCheckpoints(sessionId);
        setCheckpoints(res.checkpoints);
      } catch (err) {
        const msg = err instanceof Error ? err.message : '체크포인트 복원에 실패했습니다.';
        setError(msg);
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  return {
    checkpoints,
    isLoading,
    error,
    fetchCheckpoints,
    createCheckpoint,
    restore,
  };
}

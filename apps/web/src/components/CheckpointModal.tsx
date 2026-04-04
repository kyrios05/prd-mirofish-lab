/**
 * CheckpointModal.tsx — Modal for listing and restoring checkpoints.
 *
 * T08: Checkpoint UI (list, create, restore).
 */

import { useEffect } from 'react';
import type { Checkpoint } from '../types/prd';
import type { UseCheckpointsReturn } from '../hooks/useCheckpoints';
import styles from '../styles/common.module.css';

interface CheckpointModalProps {
  sessionId: string;
  onClose: () => void;
  checkpointHook: UseCheckpointsReturn;
  /** Callback after a restore completes (e.g. to re-fetch session status) */
  onRestored?: () => void;
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export function CheckpointModal({
  sessionId,
  onClose,
  checkpointHook,
  onRestored,
}: CheckpointModalProps) {
  const { checkpoints, isLoading, error, fetchCheckpoints, createCheckpoint, restore } =
    checkpointHook;

  useEffect(() => {
    void fetchCheckpoints(sessionId);
  }, [sessionId, fetchCheckpoints]);

  async function handleCreate() {
    const label = `Manual – Turn ${checkpoints.length + 1}`;
    await createCheckpoint(sessionId, label);
  }

  async function handleRestore(cp: Checkpoint) {
    if (!window.confirm(`"${cp.label}" 체크포인트를 복원할까요?`)) return;
    await restore(sessionId, cp.checkpoint_id);
    onRestored?.();
    onClose();
  }

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div
        className={styles.modalBox}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="cp-modal-title"
      >
        {/* Header */}
        <div className={styles.modalHeader}>
          <span id="cp-modal-title" className={styles.modalTitle}>
            💾 Checkpoints
          </span>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button
              className={`${styles.btn} ${styles.btnPrimary}`}
              onClick={() => void handleCreate()}
              disabled={isLoading}
            >
              + Save now
            </button>
            <button className={styles.iconBtn} onClick={onClose} aria-label="Close">
              ✕
            </button>
          </div>
        </div>

        {/* Body */}
        <div className={styles.modalBody}>
          {error && (
            <p style={{ color: 'var(--color-danger)', fontSize: '0.8rem', marginBottom: '0.5rem' }}>
              {error}
            </p>
          )}

          {isLoading && checkpoints.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '2rem 0' }}>
              Loading…
            </p>
          ) : checkpoints.length === 0 ? (
            <p className={styles.noCheckpoints}>No checkpoints yet. Chat a bit, then save one!</p>
          ) : (
            <div className={styles.checkpointList}>
              {checkpoints.map((cp) => (
                <div key={cp.checkpoint_id} className={styles.checkpointItem}>
                  <div className={styles.checkpointInfo}>
                    <div className={styles.checkpointLabel}>{cp.label}</div>
                    <div className={styles.checkpointMeta}>
                      {formatDate(cp.created_at)} · Phase: {cp.phase} · Turn {cp.turn_count}
                    </div>
                  </div>
                  <button
                    className={styles.btn}
                    onClick={() => void handleRestore(cp)}
                    disabled={isLoading}
                    style={{ flexShrink: 0 }}
                  >
                    Restore
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

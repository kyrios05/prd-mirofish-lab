/**
 * App.tsx — Root application component: 3-panel PRD lab UI.
 *
 * T08: Implements ChatPanel | PRDPreview | ValidationPanel layout.
 *
 * Layout
 * ------
 *   Header (phase badge, session info)
 *   ┌─────────────┬───────────────┬─────────────────┐
 *   │  ChatPanel  │  PRDPreview   │ ValidationPanel │
 *   └─────────────┴───────────────┴─────────────────┘
 *   Footer (progress bar, checkpoint button)
 *
 * Responsive: 3-col desktop, 2-col tablet (ValidationPanel hidden),
 *             1-col (tab-style) on mobile.
 *
 * Scope guard
 * -----------
 * - No modifications to apps/api/
 * - No modifications to src/types/ or src/api/
 * - Only react-markdown added as extra dependency
 */

import { useState } from 'react';
import { useChat } from './hooks/useChat';
import { useValidation } from './hooks/useValidation';
import { useCheckpoints } from './hooks/useCheckpoints';
import { ChatPanel } from './components/ChatPanel';
import { PRDPreview } from './components/PRDPreview';
import { ValidationPanel } from './components/ValidationPanel';
import { PhaseBadge } from './components/PhaseBadge';
import { CheckpointModal } from './components/CheckpointModal';
import appStyles from './styles/app.module.css';
import commonStyles from './styles/common.module.css';

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

function App() {
  const chat = useChat();
  const validation = useValidation();
  const checkpoints = useCheckpoints();

  const [showCheckpointModal, setShowCheckpointModal] = useState(false);

  // Derive project_id from session_id (match backend: "proj-<first 8 chars>")
  const projectId = chat.sessionId ? `proj-${chat.sessionId.slice(0, 8)}` : null;

  // Pass a question from ValidationPanel back to ChatPanel
  function handleQuestionClick(question: string) {
    chat.setPendingInput(question);
  }

  function handleSaveCheckpoint() {
    setShowCheckpointModal(true);
  }

  function handleRunValidation() {
    if (!chat.latestResponse?.structured_prd || !projectId) return;
    void validation.runValidation(projectId, chat.latestResponse.structured_prd);
  }

  const progressPct = Math.round(chat.completeness.progress * 100);

  return (
    <div className={appStyles.appShell}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className={appStyles.header}>
        <div className={appStyles.headerLeft}>
          <span className={appStyles.appTitle}>🐟 PRD MiroFish Lab</span>
          <PhaseBadge phase={chat.phase} />
        </div>

        <div className={appStyles.headerRight}>
          {chat.sessionId && (
            <span className={appStyles.sessionInfo} title={chat.sessionId}>
              Session: {chat.sessionId.slice(0, 8)}…
            </span>
          )}
          <button
            className={commonStyles.iconBtn}
            onClick={() => setShowCheckpointModal(true)}
            title="Checkpoints"
            aria-label="Open checkpoints"
          >
            💾
          </button>
        </div>
      </header>

      {/* ── 3-column panel grid ─────────────────────────────────────────── */}
      <main className={appStyles.panelGrid}>
        {/* Column 1 — Chat */}
        <ChatPanel
          chat={chat}
          onRunValidation={handleRunValidation}
          onSaveCheckpoint={handleSaveCheckpoint}
        />

        {/* Column 2 — PRD Preview */}
        <PRDPreview chatResponse={chat.latestResponse} />

        {/* Column 3 — Validation (hidden on tablet) */}
        <div className={appStyles.validationPanel}>
          <ValidationPanel
            validation={validation}
            prd={chat.latestResponse?.structured_prd ?? null}
            projectId={projectId}
            draftStatus={chat.latestResponse?.draft_status ?? 'empty'}
            onQuestionClick={handleQuestionClick}
          />
        </div>
      </main>

      {/* ── Footer ──────────────────────────────────────────────────────── */}
      <footer className={appStyles.footer}>
        <div className={appStyles.footerProgress}>
          <span className={appStyles.progressLabel}>
            PRD {progressPct}%
          </span>
          <div className={appStyles.progressBar}>
            <div
              className={appStyles.progressFill}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        <div className={appStyles.footerActions}>
          <button
            className={commonStyles.btn}
            onClick={handleSaveCheckpoint}
            disabled={!chat.sessionId}
          >
            💾 Checkpoint
          </button>
          <button
            className={`${commonStyles.btn} ${commonStyles.btnPrimary}`}
            onClick={handleRunValidation}
            disabled={
              chat.latestResponse?.draft_status !== 'ready_for_validation' ||
              !chat.latestResponse?.structured_prd ||
              validation.isRunning
            }
            title={
              chat.latestResponse?.draft_status !== 'ready_for_validation'
                ? 'PRD 완성 후 검증 가능'
                : undefined
            }
          >
            🚀 Validate
          </button>
        </div>
      </footer>

      {/* ── Checkpoint Modal ─────────────────────────────────────────────── */}
      {showCheckpointModal && chat.sessionId && (
        <CheckpointModal
          sessionId={chat.sessionId}
          onClose={() => setShowCheckpointModal(false)}
          checkpointHook={checkpoints}
          onRestored={() => {
            // After restore, close modal – session state will update on next message
            setShowCheckpointModal(false);
          }}
        />
      )}
    </div>
  );
}

export default App;

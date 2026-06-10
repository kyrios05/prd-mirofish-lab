/**
 * App.tsx — Root application component: 2-panel PRD lab UI with slide animation.
 *
 * Layout
 * ------
 * When right panel is CLOSED (chat focus mode):
 *   ┌───────────────────────┬──┐
 *   │      ChatPanel        │▶ │  ← handle tab only
 *   └───────────────────────┴──┘
 *
 * When right panel is OPEN (PRD complete or manual toggle):
 *   ┌─────────────┬──┬────────────────────┐
 *   │  ChatPanel  │  │   PRD Preview      │ (flex: 7)
 *   │   (45%)     │  ├────────────────────┤
 *   │             │  │   Validation       │ (flex: 3, collapsible)
 *   └─────────────┴──┴────────────────────┘
 *
 * Auto-open trigger: completeness.progress >= 1.0
 * Manual toggle: handle tab click
 */

import { useEffect, useState } from 'react';
import { useChat } from './hooks/useChat';
import { useValidation } from './hooks/useValidation';
import { useCheckpoints } from './hooks/useCheckpoints';
import { ChatPanel } from './components/ChatPanel';
import { PRDPreview } from './components/PRDPreview';
import { ValidationPanel } from './components/ValidationPanel';
import { PhaseBadge } from './components/PhaseBadge';
import { CheckpointModal } from './components/CheckpointModal';
import { SimulationContainer } from './components/simulation/SimulationContainer';
import appStyles from './styles/app.module.css';
import commonStyles from './styles/common.module.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const REQUIRED_SECTIONS = [
  'metadata', 'product', 'users', 'problem', 'solution', 'scope', 
  'requirements', 'success_metrics', 'delivery', 'assumptions', 
  'risks', 'open_questions', 'validation'
];

const SECTION_LABELS: Record<string, string> = {
  metadata: '메타',
  product: '제품',
  users: '사용자',
  problem: '문제',
  solution: '솔루션',
  scope: '범위',
  requirements: '요구사항',
  success_metrics: '성공지표',
  delivery: '딜리버리',
  assumptions: '가정',
  risks: '리스크',
  open_questions: '미결',
  validation: '검증',
};

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

function App() {
  const chat = useChat();
  const validation = useValidation();
  const checkpoints = useCheckpoints();

  const [showCheckpointModal, setShowCheckpointModal] = useState(false);

  // ── Live mode state ──────────────────────────────────────────────────────
  const [liveMode, setLiveMode] = useState<boolean>(() => {
    const saved = localStorage.getItem('mirofish_live_mode');
    return saved === 'true';
  });

  useEffect(() => {
    localStorage.setItem('mirofish_live_mode', String(liveMode));
  }, [liveMode]);

  // ── Slide panel state ────────────────────────────────────────────────────
  const [rightPanelOpen, setRightPanelOpen] = useState(false);
  const [validationOpen, setValidationOpen] = useState(true);

  // Auto-open when PRD reaches 100%
  useEffect(() => {
    if (chat.completeness.progress >= 1.0 && !rightPanelOpen) {
      setRightPanelOpen(true);
    }
  }, [chat.completeness.progress, rightPanelOpen]);

  // ── Derived values ───────────────────────────────────────────────────────
  const projectId = chat.sessionId ? `proj-${chat.sessionId.slice(0, 8)}` : null;
  const progressPct = Math.round(chat.completeness.progress * 100);

  const isSimulationPhase = [
    'simulation_setup',
    'simulating',
    'simulation_result',
    'report_generating',
    'report_complete',
  ].includes(chat.phase);

  // ── Handlers ─────────────────────────────────────────────────────────────
  function handleQuestionClick(question: string) {
    chat.setPendingInput(question);
  }

  // Checkpoints
  function handleSaveCheckpoint() {
    setShowCheckpointModal(true);
  }

  function handleRunValidation() {
    if (!chat.latestResponse?.structured_prd || !projectId) return;
    void validation.runValidation(projectId, chat.latestResponse.structured_prd, liveMode);
  }

  // ── Simulation phase full-screen ─────────────────────────────────────────
  if (isSimulationPhase) {
    return (
      <SimulationContainer
        chat={chat}
        performAction={chat.performAction}
        liveMode={liveMode}
        setLiveMode={setLiveMode}
      />
    );
  }


  // ── Main render ──────────────────────────────────────────────────────────
  return (
    <div className={appStyles.appShell}>
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className={appStyles.header}>
        <div className={appStyles.headerLeft}>
          <span className={appStyles.appTitle}>🐟 PRD MiroFish Lab</span>
          <PhaseBadge phase={chat.phase} />
        </div>

        <div className={appStyles.headerRight}>
          <div className={appStyles.liveToggleContainer}>
            <button
              className={`${appStyles.liveToggleBtn} ${liveMode ? appStyles.liveOn : appStyles.liveOff}`}
              onClick={() => setLiveMode(!liveMode)}
              title={liveMode ? "Live Mode: Qwen Engine" : "Mock Mode: Simulation"}
            >
              <span className={appStyles.liveToggleDot}></span>
              {liveMode ? "Live ON (Qwen)" : "Live OFF (Mock)"}
            </button>
          </div>
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

      {/* ── Panel grid (2-column flex) ──────────────────────────────────── */}
      <main className={appStyles.panelGrid}>

        {/* ── Left: Chat ────────────────────────────────────────────────── */}
        <div
          className={`${appStyles.leftColumn} ${
            rightPanelOpen ? appStyles.leftColumnNarrow : appStyles.leftColumnFull
          }`}
        >
          <ChatPanel
            chat={chat}
            onRunValidation={handleRunValidation}
            onSaveCheckpoint={handleSaveCheckpoint}
            onAction={chat.performAction}
          />
        </div>

        {/* ── Panel handle (toggle tab) ──────────────────────────────────── */}
        <div
          className={appStyles.panelHandle}
          onClick={() => setRightPanelOpen((v) => !v)}
          title={rightPanelOpen ? '우측 패널 닫기' : '우측 패널 열기'}
          role="button"
          aria-label={rightPanelOpen ? '우측 패널 닫기' : '우측 패널 열기'}
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setRightPanelOpen((v) => !v);
            }
          }}
        >
          <span className={appStyles.panelHandleIcon}>
            {rightPanelOpen ? '◀◀' : '▶▶'}
          </span>
        </div>

        {/* ── Right column: PRD Preview + Validation ────────────────────── */}
        <div
          className={`${appStyles.rightColumn} ${
            rightPanelOpen
              ? appStyles.rightColumnVisible
              : appStyles.rightColumnHidden
          }`}
        >
          {/* PRD Preview (top, flex: 7) */}
          <div className={appStyles.rightTop}>
            <PRDPreview chatResponse={chat.latestResponse} />
          </div>

          <div className={appStyles.rightDivider} />

          {/* Validation sub-header (collapsible toggle) */}
          <div
            className={appStyles.validationSubHeader}
            onClick={() => setValidationOpen((v) => !v)}
            role="button"
            aria-expanded={validationOpen}
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setValidationOpen((v) => !v);
              }
            }}
          >
            <span className={appStyles.validationSubTitle}>
              🔍 Validation
            </span>
            <span
              className={`${appStyles.validationToggleIcon} ${
                validationOpen ? appStyles.validationToggleIconOpen : ''
              }`}
            >
              ▲
            </span>
          </div>

          {/* Validation (bottom, flex: 3) */}
          <div
            className={`${appStyles.rightBottom} ${
              validationOpen ? '' : appStyles.rightBottomClosed
            }`}
          >
            <ValidationPanel
              validation={validation}
              prd={chat.latestResponse?.structured_prd ?? null}
              projectId={projectId}
              draftStatus={chat.latestResponse?.draft_status ?? 'empty'}
              onQuestionClick={handleQuestionClick}
              onSimulationClick={() => chat.performAction('run_simulation')}
            />
          </div>
        </div>
      </main>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <footer className={appStyles.footer}>
        <div className={appStyles.footerLeft}>
          <div className={appStyles.footerProgress}>
            <span className={appStyles.progressLabel}>
              PRD 완성도: {progressPct}%
            </span>
            <div className={appStyles.progressBar}>
              <div
                className={appStyles.progressFill}
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
          
          <div className={appStyles.sectionChips}>
            {REQUIRED_SECTIONS.map((section) => {
              const isFilled = chat.completeness.filled.includes(section);
              return (
                <span 
                  key={section} 
                  className={`${appStyles.sectionChip} ${isFilled ? appStyles.sectionChipDone : ''}`}
                  title={isFilled ? `${section}: 완료` : `${section}: 미완료`}
                >
                  {isFilled ? '✓' : '○'} {SECTION_LABELS[section]}
                </span>
              );
            })}
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

      {/* ── Checkpoint Modal ──────────────────────────────────────────────── */}
      {showCheckpointModal && chat.sessionId && (
        <CheckpointModal
          sessionId={chat.sessionId}
          onClose={() => setShowCheckpointModal(false)}
          checkpointHook={checkpoints}
          onRestored={() => {
            setShowCheckpointModal(false);
          }}
        />
      )}
    </div>
  );
}

export default App;

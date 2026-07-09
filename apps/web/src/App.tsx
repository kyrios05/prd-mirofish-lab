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
import { AppShell, Group, Title, Button, Text, Progress, Select, useMantineColorScheme } from '@mantine/core';
import appStyles from './styles/app.module.css';

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
  const { setColorScheme } = useMantineColorScheme();

  const [showCheckpointModal, setShowCheckpointModal] = useState(false);
  const [theme, setTheme] = useState<string>(() => localStorage.getItem('prd_theme') || 'black');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    if (theme === 'sand') {
      setColorScheme('light');
    } else {
      setColorScheme('dark');
    }
    localStorage.setItem('prd_theme', theme);
  }, [theme, setColorScheme]);

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
        theme={theme}
        setTheme={setTheme}
      />
    );
  }

  // ── Main render ──────────────────────────────────────────────────────────
  return (
    <AppShell
      header={{ height: 60 }}
      footer={{ height: 72 }}
      styles={{
        main: {
          background: 'var(--bg-app)',
          color: 'var(--text-primary)',
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          paddingTop: 60,
          paddingBottom: 72,
        }
      }}
    >
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <AppShell.Header
        style={{
          background: 'rgba(9, 13, 22, 0.85)',
          backdropFilter: 'blur(12px)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 1.5rem',
        }}
      >
        <Group gap="md">
          <Title order={3} style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 800, background: 'linear-gradient(to right, #38bdf8, #818cf8)', WebkitBackgroundClip: 'text', color: 'transparent', letterSpacing: '-0.02em' }}>
            PRD MiroFish Lab
          </Title>
          <PhaseBadge phase={chat.phase} />
        </Group>

        <Group gap="md">
          <Select
            size="xs"
            value={theme}
            onChange={(val) => setTheme(val || 'black')}
            data={[
              { value: 'black', label: 'Theme: Black' },
              { value: 'ocean', label: 'Theme: Ocean' },
              { value: 'aurora', label: 'Theme: Aurora' },
              { value: 'sand', label: 'Theme: Sand' }
            ]}
            style={{ width: 130 }}
            styles={{
              input: {
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: 'var(--text-primary)',
              },
              dropdown: {
                background: 'var(--bg-panel)',
                border: '1px solid var(--border)',
              }
            }}
          />

          <Button
            size="xs"
            variant="subtle"
            color={liveMode ? 'teal' : 'gray'}
            onClick={() => setLiveMode(!liveMode)}
            leftSection={<span style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: liveMode ? '#10b981' : '#94a3b8',
              boxShadow: liveMode ? '0 0 8px #10b981' : 'none'
            }} />}
            styles={{
              root: {
                backgroundColor: liveMode ? 'rgba(16, 185, 129, 0.08)' : 'rgba(255, 255, 255, 0.03)',
                border: liveMode ? '1px solid rgba(16, 185, 129, 0.2)' : '1px solid rgba(255, 255, 255, 0.08)',
                '&:hover': {
                  backgroundColor: liveMode ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.06)',
                }
              }
            }}
          >
            {liveMode ? "Live ON (Qwen)" : "Live OFF (Mock)"}
          </Button>

          {chat.sessionId && (
            <Text size="xs" c="dimmed" style={{ fontFamily: 'monospace', background: 'rgba(255, 255, 255, 0.03)', padding: '4px 8px', borderRadius: 6, border: '1px solid rgba(255, 255, 255, 0.05)' }}>
              Session: {chat.sessionId.slice(0, 8)}
            </Text>
          )}

          <Button
            variant="light"
            color="indigo"
            size="xs"
            onClick={() => setShowCheckpointModal(true)}
          >
            Checkpoints
          </Button>
        </Group>
      </AppShell.Header>

      {/* ── Main Panel Grid ──────────────────────────────────────────────── */}
      <AppShell.Main>
        <div className={appStyles.panelGrid} style={{ height: '100%', display: 'flex', width: '100%' }}>
          {/* Left Panel: Chat */}
          <div
            className={`${appStyles.leftColumn} ${
              rightPanelOpen ? appStyles.leftColumnNarrow : appStyles.leftColumnFull
            }`}
            style={{ transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}
          >
            <ChatPanel
              chat={chat}
              onRunValidation={handleRunValidation}
              onSaveCheckpoint={handleSaveCheckpoint}
              onAction={chat.performAction}
            />
          </div>

          {/* Draggable/Toggle Handle */}
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
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.03)',
              borderLeft: '1px solid rgba(255, 255, 255, 0.05)',
              borderRight: '1px solid rgba(255, 255, 255, 0.05)',
            }}
          >
            <span className={appStyles.panelHandleIcon}>
              {rightPanelOpen ? '◀' : '▶'}
            </span>
          </div>

          {/* Right Panel: PRD Preview + Validation */}
          <div
            className={`${appStyles.rightColumn} ${
              rightPanelOpen
                ? appStyles.rightColumnVisible
                : appStyles.rightColumnHidden
            }`}
            style={{ 
              transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              display: 'flex',
              flexDirection: 'column',
              background: '#0e1524',
            }}
          >
            {/* PRD Preview (top, flex: 7) */}
            <div className={appStyles.rightTop} style={{ flex: 7, overflow: 'hidden' }}>
              <PRDPreview chatResponse={chat.latestResponse} />
            </div>

            <div className={appStyles.rightDivider} style={{ height: 1, backgroundColor: 'rgba(255, 255, 255, 0.05)' }} />

            {/* Validation collapsible header */}
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
              style={{
                background: 'rgba(255, 255, 255, 0.02)',
                borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                display: 'flex',
                justifyContent: 'space-between',
                padding: '0.75rem 1.25rem',
                cursor: 'pointer',
              }}
            >
              <Text size="sm" fw={700} c="indigo.3">
                Validation
              </Text>
              <span
                className={`${appStyles.validationToggleIcon} ${
                  validationOpen ? appStyles.validationToggleIconOpen : ''
                }`}
                style={{ fontSize: '0.8rem', opacity: 0.7 }}
              >
                ▲
              </span>
            </div>

            {/* Validation Panel (bottom, flex: 3 or collapsed) */}
            <div
              className={`${appStyles.rightBottom} ${
                validationOpen ? '' : appStyles.rightBottomClosed
              }`}
              style={{
                flex: validationOpen ? 3 : 0,
                minHeight: validationOpen ? 180 : 0,
                maxHeight: validationOpen ? 'none' : 0,
                overflow: 'hidden',
                transition: 'all 0.3s ease-in-out',
              }}
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
        </div>
      </AppShell.Main>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <AppShell.Footer
        style={{
          background: 'rgba(9, 13, 22, 0.9)',
          backdropFilter: 'blur(12px)',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 1.5rem',
          zIndex: 100,
        }}
      >
        <Group style={{ flex: 1, marginRight: '2rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', width: '220px', gap: 4 }}>
            <Group justify="space-between">
              <Text size="xs" fw={700}>PRD 완성도</Text>
              <Text size="xs" fw={700} c="indigo.4">{progressPct}%</Text>
            </Group>
            <Progress
              value={progressPct}
              size="sm"
              radius="xl"
              striped
              animated
              color="indigo"
            />
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginLeft: '1rem', maxWidth: 'calc(100vw - 650px)', overflow: 'hidden', height: 28 }}>
            {REQUIRED_SECTIONS.map((section) => {
              const isFilled = chat.completeness.filled.includes(section);
              return (
                <span 
                  key={section} 
                  className={`${appStyles.sectionChip} ${isFilled ? appStyles.sectionChipDone : ''}`}
                  title={isFilled ? `${section}: 완료` : `${section}: 미완료`}
                  style={{
                    fontSize: '0.68rem',
                    padding: '2px 8px',
                    borderRadius: 12,
                    background: isFilled ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                    border: isFilled ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(255, 255, 255, 0.05)',
                    color: isFilled ? '#10b981' : '#94a3b8',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 3,
                    whiteSpace: 'nowrap'
                  }}
                >
                  {isFilled ? '✓' : '○'} {SECTION_LABELS[section]}
                </span>
              );
            })}
          </div>
        </Group>

        <Group gap="sm">
          <Button
            variant="light"
            color="gray"
            size="sm"
            onClick={handleSaveCheckpoint}
            disabled={!chat.sessionId}
          >
            💾 Checkpoint
          </Button>
          <Button
            variant="gradient"
            gradient={{ from: 'indigo', to: 'cyan' }}
            size="sm"
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
            Validate
          </Button>
        </Group>
      </AppShell.Footer>

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
    </AppShell>
  );
}

export default App;

/**
 * PRDPreview.tsx — Middle panel: Markdown/JSON toggle, completeness progress,
 * section checklist, and draft status badge.
 *
 * T08: PRD preview UI component.
 */

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import type { ChatResponse } from '../types/chat';
import styles from '../styles/prd.module.css';
import commonStyles from '../styles/common.module.css';

// ---------------------------------------------------------------------------
// Draft status badge
// ---------------------------------------------------------------------------

const DRAFT_LABELS: Record<string, string> = {
  empty: 'Empty',
  incomplete: 'Incomplete',
  ready_for_validation: 'Ready',
};

const DRAFT_CLASSES: Record<string, string> = {
  empty: commonStyles.draftEmpty,
  incomplete: commonStyles.draftIncomplete,
  ready_for_validation: commonStyles.draftReady,
};

function DraftStatusBadge({ status }: { status: string }) {
  const label = DRAFT_LABELS[status] ?? status;
  const cls = DRAFT_CLASSES[status] ?? '';
  return <span className={`${commonStyles.draftBadge} ${cls}`}>{label}</span>;
}

// ---------------------------------------------------------------------------
// PRDPreview
// ---------------------------------------------------------------------------

interface PRDPreviewProps {
  /** Latest ChatResponse from useChat */
  chatResponse: ChatResponse | null;
}

export function PRDPreview({ chatResponse }: PRDPreviewProps) {
  const [view, setView] = useState<'markdown' | 'json'>('markdown');

  const hasData = !!chatResponse?.structured_prd;
  const completeness = chatResponse?.completeness ?? { filled: [], missing: [], progress: 0 };
  const progressPct = Math.round(completeness.progress * 100);
  const draftStatus = chatResponse?.draft_status ?? 'empty';
  const prdMarkdown = chatResponse?.prd_markdown ?? null;
  const structuredPrd = chatResponse?.structured_prd ?? null;

  return (
    <div className={styles.panel}>
      {/* Panel header */}
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>📄 PRD Preview</span>
        <div className={styles.headerActions}>
          <DraftStatusBadge status={draftStatus} />
          {hasData && (
            <div className={styles.toggleGroup}>
              <button
                className={`${styles.toggleBtn} ${view === 'markdown' ? styles.toggleBtnActive : ''}`}
                onClick={() => setView('markdown')}
              >
                MD
              </button>
              <button
                className={`${styles.toggleBtn} ${view === 'json' ? styles.toggleBtnActive : ''}`}
                onClick={() => setView('json')}
              >
                JSON
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Progress section */}
      {hasData && (
        <div className={styles.progressSection}>
          <div className={styles.progressRow}>
            <span className={styles.progressPercent}>
              {progressPct}% complete
            </span>
            <DraftStatusBadge status={draftStatus} />
          </div>
          <div className={styles.progressBar}>
            <div
              className={styles.progressFill}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}

      {/* Content */}
      {!hasData ? (
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>📝</div>
          <div className={styles.emptyText}>
            채팅을 시작하면 PRD 초안이 여기에 표시됩니다.
          </div>
        </div>
      ) : (
        <div className={styles.content}>
          {view === 'markdown' ? (
            prdMarkdown ? (
              <div className="markdown-prose">
                <ReactMarkdown>{prdMarkdown}</ReactMarkdown>
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                Markdown을 생성하는 중…
              </p>
            )
          ) : (
            <pre className={styles.jsonView}>
              {JSON.stringify(structuredPrd, null, 2)}
            </pre>
          )}

          {/* Section checklist */}
          {(completeness.filled.length > 0 || completeness.missing.length > 0) && (
            <div className={styles.sectionChecklist}>
              <div className={styles.sectionChecklistTitle}>Sections</div>
              {completeness.filled.map((s) => (
                <div key={s} className={`${styles.sectionItem} ${styles.sectionFilled}`}>
                  <span className={styles.sectionIcon}>✓</span>
                  <span>{s}</span>
                </div>
              ))}
              {completeness.missing.map((s) => (
                <div key={s} className={`${styles.sectionItem} ${styles.sectionMissing}`}>
                  <span className={styles.sectionIcon}>○</span>
                  <span>{s}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

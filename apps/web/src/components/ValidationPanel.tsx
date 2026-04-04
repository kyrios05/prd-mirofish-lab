/**
 * ValidationPanel.tsx — Right panel: Run Validation button, loading state,
 * result accordion sections, and schema error display.
 *
 * T08: Validation UI component.
 */

import { useState } from 'react';
import type { UseValidationReturn } from '../hooks/useValidation';
import type { ValidationResult } from '../types/validation';
import styles from '../styles/validation.module.css';

// ---------------------------------------------------------------------------
// Result section accordion
// ---------------------------------------------------------------------------

interface ResultSectionProps {
  icon: string;
  title: string;
  items: string[];
  /** Optional click handler per item (for recommended_questions) */
  onItemClick?: (item: string) => void;
}

function ResultSection({ icon, title, items, onItemClick }: ResultSectionProps) {
  const [open, setOpen] = useState(true);

  if (items.length === 0) return null;

  return (
    <div className={styles.resultSection}>
      <div
        className={styles.sectionHeader}
        onClick={() => setOpen((p) => !p)}
        role="button"
        aria-expanded={open}
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && setOpen((p) => !p)}
      >
        <div className={styles.sectionTitle}>
          <span className={styles.sectionIcon}>{icon}</span>
          {title}
          <span className={styles.sectionCount}>{items.length}</span>
        </div>
        <span className={`${styles.chevron} ${open ? styles.chevronOpen : ''}`}>▶</span>
      </div>

      {open && (
        <div className={styles.sectionBody}>
          <ul className={styles.resultList}>
            {items.map((item, i) => (
              <li
                key={i}
                className={`${styles.resultItem} ${onItemClick ? styles.questionItem : ''}`}
                onClick={onItemClick ? () => onItemClick(item) : undefined}
                style={{ cursor: onItemClick ? 'pointer' : 'default' }}
              >
                <div className={styles.resultBullet} />
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ValidationPanel
// ---------------------------------------------------------------------------

interface ValidationPanelProps {
  /** From useValidation() hook */
  validation: UseValidationReturn;
  /** PRD data from the latest chat response */
  prd: Record<string, unknown> | null;
  /** Project id (derived from sessionId) */
  projectId: string | null;
  /** draft_status from the latest chat response */
  draftStatus: string;
  /** Callback to inject a question into the chat input */
  onQuestionClick?: (question: string) => void;
}

export function ValidationPanel({
  validation,
  prd,
  projectId,
  draftStatus,
  onQuestionClick,
}: ValidationPanelProps) {
  const { validationResponse, isRunning, error, runValidation } = validation;

  const canRun = draftStatus === 'ready_for_validation' && !!prd && !!projectId && !isRunning;

  function handleRun() {
    if (!prd || !projectId) return;
    void runValidation(projectId, prd);
  }

  const result: ValidationResult | null = validationResponse?.result ?? null;
  const schemaErrors = validationResponse?.schema_errors ?? [];

  return (
    <div className={styles.panel}>
      {/* Panel header */}
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>🔬 Validation</span>
        {validationResponse && (
          <span
            style={{
              fontSize: '0.72rem',
              fontWeight: 600,
              padding: '0.15rem 0.5rem',
              borderRadius: 10,
              background:
                validationResponse.status === 'completed'
                  ? '#d1fae5'
                  : validationResponse.status === 'schema_invalid'
                  ? '#fee2e2'
                  : '#fef3c7',
              color:
                validationResponse.status === 'completed'
                  ? '#065f46'
                  : validationResponse.status === 'schema_invalid'
                  ? '#991b1b'
                  : '#92400e',
            }}
          >
            {validationResponse.status}
          </span>
        )}
      </div>

      <div className={styles.content}>
        {/* Run button */}
        <button
          className={styles.runBtn}
          onClick={handleRun}
          disabled={!canRun}
          title={
            draftStatus !== 'ready_for_validation'
              ? 'PRD가 완성되면 검증을 실행할 수 있습니다.'
              : !prd
              ? '먼저 PRD를 작성하세요.'
              : undefined
          }
        >
          {isRunning ? (
            <>
              <div className={styles.spinner} />
              검증 중…
            </>
          ) : (
            '🚀 Run Validation'
          )}
        </button>

        {/* Error */}
        {error && (
          <div
            style={{
              background: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: 'var(--radius-md)',
              padding: '0.75rem',
              fontSize: '0.825rem',
              color: '#991b1b',
            }}
          >
            ⚠ {error}
          </div>
        )}

        {/* Schema errors */}
        {schemaErrors.length > 0 && (
          <div className={styles.errorList}>
            <div
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                color: '#991b1b',
                marginBottom: '0.35rem',
              }}
            >
              Schema Errors ({schemaErrors.length})
            </div>
            {schemaErrors.map((e, i) => (
              <div key={i}>
                <div className={styles.errorItem}>{e.message}</div>
                {e.path && <div className={styles.errorPath}>@ {e.path}</div>}
              </div>
            ))}
          </div>
        )}

        {/* Placeholder / no result */}
        {!result && !isRunning && !error && schemaErrors.length === 0 && (
          <div className={styles.placeholder}>
            <div className={styles.placeholderIcon}>
              {draftStatus === 'ready_for_validation' ? '✅' : '⏳'}
            </div>
            <div className={styles.placeholderText}>
              {draftStatus === 'ready_for_validation'
                ? '"Run Validation" 버튼을 눌러 검증을 시작하세요.'
                : '인터뷰를 완료하면 검증이 활성화됩니다.'}
            </div>
          </div>
        )}

        {/* Result */}
        {result && (
          <>
            {/* Summary */}
            <div className={styles.summaryCard}>
              <p className={styles.summaryText}>{result.summary}</p>
            </div>

            {/* Accordion sections */}
            <ResultSection
              icon="⚠️"
              title="Top Risks"
              items={result.top_risks}
            />
            <ResultSection
              icon="❌"
              title="Missing Requirements"
              items={result.missing_requirements}
            />
            <ResultSection
              icon="👥"
              title="Stakeholder Objections"
              items={result.stakeholder_objections}
            />
            <ResultSection
              icon="✂️"
              title="Scope Adjustments"
              items={result.scope_adjustments}
            />
            <ResultSection
              icon="❓"
              title="Recommended Questions"
              items={result.recommended_questions}
              onItemClick={onQuestionClick}
            />
            <ResultSection
              icon="✏️"
              title="Rewrite Suggestions"
              items={result.rewrite_suggestions}
            />
          </>
        )}
      </div>
    </div>
  );
}

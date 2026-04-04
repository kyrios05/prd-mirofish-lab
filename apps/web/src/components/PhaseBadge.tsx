/**
 * PhaseBadge.tsx — Conversation phase indicator badge.
 *
 * T08: Shared UI component used in Header and ChatPanel.
 */

import type { ConversationPhase } from '../types/prd';
import styles from '../styles/common.module.css';

// Phase label mapping
const PHASE_LABELS: Record<ConversationPhase, string> = {
  greeting: 'Greeting',
  interviewing: 'Interviewing',
  reviewing: 'Reviewing',
  ready_for_validation: 'Ready',
  validated: 'Validated',
};

// Phase CSS class mapping
const PHASE_CLASSES: Record<ConversationPhase, string> = {
  greeting: styles.phaseGreeting,
  interviewing: styles.phaseInterviewing,
  reviewing: styles.phaseReviewing,
  ready_for_validation: styles.phaseReady,
  validated: styles.phaseValidated,
};

interface PhaseBadgeProps {
  phase: ConversationPhase;
}

export function PhaseBadge({ phase }: PhaseBadgeProps) {
  const label = PHASE_LABELS[phase] ?? phase;
  const cls = PHASE_CLASSES[phase] ?? '';
  return (
    <span className={`${styles.phaseBadge} ${cls}`}>
      {label}
    </span>
  );
}

/**
 * PhaseBadge.tsx — Conversation phase indicator badge.
 *
 * T08: Shared UI component used in Header and ChatPanel.
 */

import type { ConversationPhase } from '../types/prd';
import { Badge } from '@mantine/core';

// Phase label mapping
const PHASE_LABELS: Record<ConversationPhase, string> = {
  greeting: 'Greeting',
  interviewing: 'Interviewing',
  reviewing: 'Reviewing',
  ready_for_validation: 'Ready',
  validated: 'Validated',
  simulation_setup: 'Sim Setup',
  simulating: 'Simulating',
  simulation_result: 'Sim Result',
  report_generating: 'Reporting',
  report_complete: 'Complete',
};

// Phase Mantine color mapping
const PHASE_COLORS: Record<ConversationPhase, string> = {
  greeting: 'gray',
  interviewing: 'blue',
  reviewing: 'yellow',
  ready_for_validation: 'cyan',
  validated: 'green',
  simulation_setup: 'indigo',
  simulating: 'orange',
  simulation_result: 'violet',
  report_generating: 'pink',
  report_complete: 'grape',
};

interface PhaseBadgeProps {
  phase: ConversationPhase;
}

export function PhaseBadge({ phase }: PhaseBadgeProps) {
  const label = PHASE_LABELS[phase] ?? phase;
  const color = PHASE_COLORS[phase] ?? 'blue';
  return (
    <Badge color={color} variant="light" size="sm" radius="sm">
      {label}
    </Badge>
  );
}

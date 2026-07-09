/**
 * PRDPreview.tsx — Middle panel: Markdown/JSON toggle, completeness progress,
 * section checklist, and draft status badge.
 *
 * T08: PRD preview UI component.
 */

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatResponse } from '../types/chat';
import { Box, Group, Text, Progress, SegmentedControl, Badge, ScrollArea, Paper, Stack } from '@mantine/core';
import styles from '../styles/prd.module.css';

// ---------------------------------------------------------------------------
// Draft status badge
// ---------------------------------------------------------------------------

const DRAFT_COLORS: Record<string, string> = {
  empty: 'gray',
  incomplete: 'yellow',
  ready_for_validation: 'green',
};

const DRAFT_LABELS: Record<string, string> = {
  empty: 'Empty',
  incomplete: 'Incomplete',
  ready_for_validation: 'Ready',
};

function DraftStatusBadge({ status }: { status: string }) {
  const label = DRAFT_LABELS[status] ?? status;
  const color = DRAFT_COLORS[status] ?? 'blue';
  return (
    <Badge color={color} variant="light" size="sm" radius="sm">
      {label}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// PRDPreview
// ---------------------------------------------------------------------------

interface PRDPreviewProps {
  chatResponse: ChatResponse | null;
}

export function PRDPreview({ chatResponse }: PRDPreviewProps) {
  const [view, setView] = useState<string>('markdown');

  const hasData = !!chatResponse?.structured_prd;
  const completeness = chatResponse?.completeness ?? { filled: [], missing: [], progress: 0 };
  const progressPct = Math.round(completeness.progress * 100);
  const draftStatus = chatResponse?.draft_status ?? 'empty';
  const prdMarkdown = chatResponse?.prd_markdown ?? null;
  const structuredPrd = chatResponse?.structured_prd ?? null;

  return (
    <Box style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-panel)' }}>
      {/* Panel header */}
      <Group justify="space-between" px="md" py="xs" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)', background: 'rgba(255, 255, 255, 0.02)' }}>
        <Text fw={700} size="sm" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          PRD Preview
        </Text>
        <Group gap="xs">
          <DraftStatusBadge status={draftStatus} />
          {hasData && (
            <SegmentedControl
              size="xs"
              value={view}
              onChange={setView}
              data={[
                { label: 'MD', value: 'markdown' },
                { label: 'JSON', value: 'json' },
              ]}
              styles={{
                root: {
                  background: 'rgba(0, 0, 0, 0.2)',
                  border: '1px solid rgba(255, 255, 255, 0.08)'
                }
              }}
            />
          )}
        </Group>
      </Group>

      {/* Progress section */}
      {hasData && (
        <Box px="md" py="xs" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.03)', background: 'rgba(255, 255, 255, 0.01)' }}>
          <Stack gap={4}>
            <Group justify="space-between">
              <Text size="xs" fw={600} c="dimmed">
                PRD Completeness
              </Text>
              <Text size="xs" fw={700} c="indigo.4">
                {progressPct}%
              </Text>
            </Group>
            <Progress
              value={progressPct}
              size="sm"
              radius="xl"
              striped
              animated
              color="indigo"
            />
          </Stack>
        </Box>
      )}

      {/* Content */}
      <ScrollArea style={{ flex: 1, padding: '16px' }}>
        {!hasData ? (
          <Box style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '6rem 0', opacity: 0.4 }}>
            <Text size="sm" mt="xs">채팅을 시작하면 PRD 초안이 여기에 표시됩니다.</Text>
          </Box>
        ) : (
          <Stack gap="lg">
            {view === 'markdown' ? (
              prdMarkdown ? (
                <div className={styles.markdownProse}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {prdMarkdown}
                  </ReactMarkdown>
                </div>
              ) : (
                <Text size="sm" c="dimmed">
                  Markdown을 생성하는 중…
                </Text>
              )
            ) : (
              <pre style={{
                margin: 0,
                padding: '12px',
                borderRadius: '8px',
                background: 'rgba(0, 0, 0, 0.3)',
                border: '1px solid rgba(255, 255, 255, 0.05)',
                color: '#38bdf8',
                fontFamily: 'monospace',
                fontSize: '0.85rem',
                overflowX: 'auto'
              }}>
                {JSON.stringify(structuredPrd, null, 2)}
              </pre>
            )}

            {/* Section checklist */}
            {(completeness.filled.length > 0 || completeness.missing.length > 0) && (
              <Paper
                withBorder
                p="md"
                bg="rgba(255, 255, 255, 0.01)"
                style={{ borderColor: 'rgba(255, 255, 255, 0.05)' }}
              >
                <Text size="xs" fw={700} mb="xs" c="dimmed" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  PRD Section Checklist
                </Text>
                <Group gap="xs" style={{ flexWrap: 'wrap' }}>
                  {completeness.filled.map((s) => (
                    <Badge
                      key={s}
                      variant="dot"
                      color="green"
                      size="sm"
                      radius="sm"
                      styles={{
                        root: {
                          background: 'rgba(16, 185, 129, 0.05)',
                          border: '1px solid rgba(16, 185, 129, 0.15)',
                          color: '#10b981'
                        }
                      }}
                    >
                      {s}
                    </Badge>
                  ))}
                  {completeness.missing.map((s) => (
                    <Badge
                      key={s}
                      variant="dot"
                      color="yellow"
                      size="sm"
                      radius="sm"
                      styles={{
                        root: {
                          background: 'rgba(245, 158, 11, 0.05)',
                          border: '1px solid rgba(245, 158, 11, 0.15)',
                          color: '#f59e0b'
                        }
                      }}
                    >
                      {s}
                    </Badge>
                  ))}
                </Group>
              </Paper>
            )}
          </Stack>
        )}
      </ScrollArea>
    </Box>
  );
}


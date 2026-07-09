/**
 * ValidationPanel.tsx — Right panel: Run Validation button, loading state,
 * result accordion sections, and schema error display.
 *
 * T08: Validation UI component.
 */

import { useState } from 'react';
import type { UseValidationReturn } from '../hooks/useValidation';
import type { ValidationResult } from '../types/validation';
import { Box, Button, Accordion, Alert, Text, Badge, Group, ScrollArea, Center, Stack, List, Progress } from '@mantine/core';

// ---------------------------------------------------------------------------
// ValidationPanel
// ---------------------------------------------------------------------------

interface ValidationPanelProps {
  validation: UseValidationReturn;
  prd: Record<string, unknown> | null;
  projectId: string | null;
  draftStatus: string;
  onQuestionClick?: (question: string) => void;
  onSimulationClick?: () => void;
}

export function ValidationPanel({
  validation,
  prd,
  projectId,
  draftStatus,
  onQuestionClick,
  onSimulationClick,
}: ValidationPanelProps) {
  const { validationResponse, isRunning, error, runValidation } = validation;

  const [progressVal, setProgressVal] = useState<number | null>(null);
  const [progressValMsg, setProgressValMsg] = useState<string>('');
  
  const [simulationProgress, setSimulationProgress] = useState<number | null>(null);
  const [simulationMsg, setSimulationMsg] = useState<string>('');

  const canRun = draftStatus === 'ready_for_validation' && !!prd && !!projectId && !isRunning && progressVal === null;

  function handleRun() {
    if (!prd || !projectId) return;
    setProgressVal(0);
    setProgressValMsg('🔍 PRD 구조화 데이터 파싱 및 스키마 유효성 검사 중...');
    
    let current = 0;
    const interval = setInterval(() => {
      current += 100 / 30; // 3초에 100% 도달
      if (current >= 100) {
        clearInterval(interval);
        setProgressVal(null);
        setProgressValMsg('');
        void runValidation(projectId, prd);
      } else {
        setProgressVal(Math.min(current, 99));
        if (current > 70) {
          setProgressValMsg('📊 검증 결과 리포트 및 지표 정적 매칭 생성 중...');
        } else if (current > 35) {
          setProgressValMsg('⚖️ 12대 부서 비즈니스 정합성 및 RAG 매뉴얼 정합성 정밀 분석 중...');
        }
      }
    }, 100);
  }

  function handleSimulate() {
    if (!onSimulationClick) return;
    setSimulationProgress(0);
    setSimulationMsg('🚀 MiroFish 시뮬레이션 환경 초기화 중...');
    
    let current = 0;
    const interval = setInterval(() => {
      current += 100 / 30; // 3초에 100% 도달
      if (current >= 100) {
        clearInterval(interval);
        setSimulationProgress(null);
        setSimulationMsg('');
        onSimulationClick();
      } else {
        setSimulationProgress(Math.min(current, 99));
        if (current > 70) {
          setSimulationMsg('🕸️ 메시 에이전트 스웜(Swarm) 네트워크 채널 개방 중...');
        } else if (current > 40) {
          setSimulationMsg('🧬 30인의 전문가 페르소나 및 지식 그래프 토폴로지 구성 중...');
        }
      }
    }, 100);
  }

  const result: ValidationResult | null = validationResponse?.result ?? null;
  const schemaErrors = validationResponse?.schema_errors ?? [];

  // Show simulation button if validation is completed and we have result
  const showSimulationBtn = validationResponse?.status === 'completed' && !!result;

  const statusColors: Record<string, string> = {
    completed: 'green',
    schema_invalid: 'red',
    failed: 'red',
    pending: 'yellow',
  };

  return (
    <Box style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-panel)' }}>
      <ScrollArea style={{ flex: 1, padding: '16px' }}>
        <Stack gap="md">
          {/* Status badge & title */}
          {validationResponse && (
            <Group justify="space-between">
              <Text size="xs" fw={700} c="dimmed">Validation Status</Text>
              <Badge color={statusColors[validationResponse.status] ?? 'blue'} variant="light" size="sm">
                {validationResponse.status}
              </Badge>
            </Group>
          )}

          {/* Action Buttons */}
          <Stack gap="xs">
            <Button
              variant="gradient"
              gradient={{ from: 'indigo', to: 'cyan' }}
              fullWidth
              onClick={handleRun}
              disabled={!canRun || progressVal !== null}
              loading={isRunning && progressVal === null}
              loaderProps={{ type: 'dots' }}
              title={
                draftStatus !== 'ready_for_validation'
                  ? 'PRD가 완성되면 검증을 실행할 수 있습니다.'
                  : !prd
                  ? '먼저 PRD를 작성하세요.'
                  : undefined
              }
            >
              Run Validation
            </Button>

            {progressVal !== null && (
              <Box mt="2px">
                <Progress value={progressVal} animated color="cyan" size="sm" />
                <Text size="10px" c="dimmed" mt={4} ta="center">
                  {progressValMsg} ({Math.round(progressVal)}%)
                </Text>
              </Box>
            )}
            
            {showSimulationBtn && (
              <>
                <Button
                  variant="filled"
                  color="indigo"
                  fullWidth
                  disabled={simulationProgress !== null}
                  onClick={handleSimulate}
                >
                  Simulate in MiroFish
                </Button>
                {simulationProgress !== null && (
                  <Box mt="2px">
                    <Progress value={simulationProgress} animated color="indigo" size="sm" />
                    <Text size="10px" c="dimmed" mt={4} ta="center">
                      {simulationMsg} ({Math.round(simulationProgress)}%)
                    </Text>
                  </Box>
                )}
              </>
            )}
          </Stack>

          {/* Error Alert */}
          {error && (
            <Alert color="red" title="검증 에러" radius="md">
              {error}
            </Alert>
          )}

          {/* Schema Errors List */}
          {schemaErrors.length > 0 && (
            <Alert color="red" title={`Schema Errors (${schemaErrors.length})`} radius="md">
              <Stack gap="xs">
                {schemaErrors.map((e, i) => (
                  <Box key={i}>
                    <Text size="xs" fw={600} c="red.4">{e.message}</Text>
                    {e.path && <Text size="10px" c="dimmed">Path: {e.path}</Text>}
                  </Box>
                ))}
              </Stack>
            </Alert>
          )}

          {/* Placeholder / No Result */}
          {!result && !isRunning && !error && schemaErrors.length === 0 && (
            <Center style={{ minHeight: '120px' }}>
              <Stack align="center" gap={8} style={{ opacity: 0.5 }}>
                <Text size="xl">
                  {draftStatus === 'ready_for_validation' ? '✓' : '...'}
                </Text>
                <Text size="xs" ta="center">
                  {draftStatus === 'ready_for_validation'
                    ? '"Run Validation" 버튼을 눌러 정적 검증을 시작하세요.'
                    : '인터뷰를 완료하면 정적 검증이 활성화됩니다.'}
                </Text>
              </Stack>
            </Center>
          )}

          {/* Validation Result Accordion */}
          {result && (
            <Stack gap="sm">
              {/* Summary Card */}
              <Alert color="indigo" title="Validation Summary" radius="md" variant="light">
                <Text size="sm" style={{ lineHeight: 1.5 }}>{result.summary}</Text>
              </Alert>

              {/* Mantine Accordion */}
              <Accordion variant="separated" radius="md" styles={{
                item: {
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid rgba(255, 255, 255, 0.05)'
                },
                control: {
                  padding: '8px 12px',
                },
                panel: {
                  padding: '8px 12px',
                  background: 'rgba(0, 0, 0, 0.1)',
                }
              }}>
                {result.top_risks.length > 0 && (
                  <Accordion.Item value="risks">
                    <Accordion.Control>
                      <Group gap="xs">
                        <Text size="xs" fw={700}>Top Risks</Text>
                        <Badge size="xs" color="yellow" variant="light">{result.top_risks.length}</Badge>
                      </Group>
                    </Accordion.Control>
                    <Accordion.Panel>
                      <List size="xs" spacing="xs" style={{ color: '#cbd5e1' }}>
                        {result.top_risks.map((item, idx) => (
                          <List.Item key={idx}>{item}</List.Item>
                        ))}
                      </List>
                    </Accordion.Panel>
                  </Accordion.Item>
                )}

                {result.missing_requirements.length > 0 && (
                  <Accordion.Item value="missing">
                    <Accordion.Control>
                      <Group gap="xs">
                        <Text size="xs" fw={700}>Missing Requirements</Text>
                        <Badge size="xs" color="red" variant="light">{result.missing_requirements.length}</Badge>
                      </Group>
                    </Accordion.Control>
                    <Accordion.Panel>
                      <List size="xs" spacing="xs" style={{ color: '#cbd5e1' }}>
                        {result.missing_requirements.map((item, idx) => (
                          <List.Item key={idx}>{item}</List.Item>
                        ))}
                      </List>
                    </Accordion.Panel>
                  </Accordion.Item>
                )}

                {result.stakeholder_objections.length > 0 && (
                  <Accordion.Item value="objections">
                    <Accordion.Control>
                      <Group gap="xs">
                        <Text size="xs" fw={700}>Stakeholder Objections</Text>
                        <Badge size="xs" color="orange" variant="light">{result.stakeholder_objections.length}</Badge>
                      </Group>
                    </Accordion.Control>
                    <Accordion.Panel>
                      <List size="xs" spacing="xs" style={{ color: '#cbd5e1' }}>
                        {result.stakeholder_objections.map((item, idx) => (
                          <List.Item key={idx}>{item}</List.Item>
                        ))}
                      </List>
                    </Accordion.Panel>
                  </Accordion.Item>
                )}

                {result.scope_adjustments.length > 0 && (
                  <Accordion.Item value="scope">
                    <Accordion.Control>
                      <Group gap="xs">
                        <Text size="xs" fw={700}>Scope Adjustments</Text>
                        <Badge size="xs" color="cyan" variant="light">{result.scope_adjustments.length}</Badge>
                      </Group>
                    </Accordion.Control>
                    <Accordion.Panel>
                      <List size="xs" spacing="xs" style={{ color: '#cbd5e1' }}>
                        {result.scope_adjustments.map((item, idx) => (
                          <List.Item key={idx}>{item}</List.Item>
                        ))}
                      </List>
                    </Accordion.Panel>
                  </Accordion.Item>
                )}

                {result.recommended_questions.length > 0 && (
                  <Accordion.Item value="questions">
                    <Accordion.Control>
                      <Group gap="xs">
                        <Text size="xs" fw={700}>Recommended Questions</Text>
                        <Badge size="xs" color="teal" variant="light">{result.recommended_questions.length}</Badge>
                      </Group>
                    </Accordion.Control>
                    <Accordion.Panel>
                      <List size="xs" spacing="xs">
                        {result.recommended_questions.map((item, idx) => (
                          <List.Item
                            key={idx}
                            onClick={onQuestionClick ? () => onQuestionClick(item) : undefined}
                            style={{
                              cursor: onQuestionClick ? 'pointer' : 'default',
                              color: '#38bdf8',
                              textDecoration: 'underline'
                            }}
                          >
                            {item}
                          </List.Item>
                        ))}
                      </List>
                    </Accordion.Panel>
                  </Accordion.Item>
                )}

                {result.rewrite_suggestions.length > 0 && (
                  <Accordion.Item value="rewrite">
                    <Accordion.Control>
                      <Group gap="xs">
                        <Text size="xs" fw={700}>Rewrite Suggestions</Text>
                        <Badge size="xs" color="grape" variant="light">{result.rewrite_suggestions.length}</Badge>
                      </Group>
                    </Accordion.Control>
                    <Accordion.Panel>
                      <List size="xs" spacing="xs" style={{ color: '#cbd5e1' }}>
                        {result.rewrite_suggestions.map((item, idx) => (
                          <List.Item key={idx}>{item}</List.Item>
                        ))}
                      </List>
                    </Accordion.Panel>
                  </Accordion.Item>
                )}
              </Accordion>
            </Stack>
          )}
        </Stack>
      </ScrollArea>
    </Box>
  );
}


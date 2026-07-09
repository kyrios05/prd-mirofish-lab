/**
 * ChatPanel.tsx — Left panel: conversation bubbles, input, phase badge,
 * action buttons, and next-question chips.
 *
 * T08: Core chat UI component.
 */

import { useEffect, useRef, useState } from 'react';
import type { UseChatReturn } from '../hooks/useChat';
import { PhaseBadge } from './PhaseBadge';
import { Paper, ScrollArea, Stack, Group, Text, Button, Textarea, ActionIcon, Avatar, Loader, Box, Alert } from '@mantine/core';
import styles from '../styles/chat.module.css';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';

// ---------------------------------------------------------------------------
// Action label mapping
// ---------------------------------------------------------------------------

const ACTION_LABELS: Record<string, string> = {
  continue: '계속하기',
  skip_section: '섹션 건너뛰기',
  save_checkpoint: '체크포인트 저장',
  confirm: '확인완료',
  edit_section: '섹션 수정',
  run_validation: '정적 검증하기',
  run_simulation: '시뮬레이션',
  go_back: '돌아가기',
};

function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

// ---------------------------------------------------------------------------
// Demo PRD template constant
// ---------------------------------------------------------------------------

const DEMO_PRD_CONTENT = `1. 제품의 핵심 아이디어 및 타겟
제품명: Simply AI Agent (가칭)

핵심 아이디어: 단순히 답변만 하는 챗봇을 넘어, 기업의 시스템 속에서 자율적으로 업무(Action)를 완수하는 '실행형 에이전트'입니다.

타겟 고객사 (B2B):
대형 이커머스: 실시간 주문/환불 등 액션 중심 업무가 많은 곳
금융권: 높은 보안 규제와 정확한 약관 상담이 필수적인 곳
가전/렌탈: 복잡한 매뉴얼 기반의 기술 상담 및 AS 접수가 필요한 곳

사용자 페르소나:
최종 고객: 대기 없는 즉각적 해결을 원하는 사용자
CS 운영 관리자: 운영 비용 절감과 자동화 지표를 관리하는 리더
IT 보안 담당자: 외부 LLM 사용 시 개인정보 유출을 감시하는 전문가

비대상 그룹: 연동할 시스템이 없는 소규모 SMB, 디지털 전환이 전무한 기업, 보안 및 실시간성이 중요하지 않은 서비스

2. MVP 범위 및 확장 계획
MVP 핵심 집중 영역: Agentic Intelligence (MCP)와 K-Security (PII Masking)의 결합을 통한 '안전한 자율 실행' 증명

In-Scope: 이커머스 3대 시나리오(배송조회, 취소, 50만 원 이하 환불), 50ms PII 마스킹, 표준 MCP 연동, 기본 TCR 대시보드, HWP 표 파싱
Out-of-Scope: 음성 AI(Voicebot) 연동, 다국어 지원, 비표준 레거시 전용 어댑터 개발, 복잡한 부서별 권한 관리

향후 확장 계획: 금융권 전용 On-prem Proxy, 가전/렌탈용 이미지 시각 진단, EvalOps 자동화, 멀티모달 지식 그래프

3. 요구사항 상세 가이드라인
기능적 요구사항 (Functional)
MCP 액션 플로우 (HITL): AI 판단 불능이나 고액 건 발생 시, '전용 관리자 툴'의 승인 대기 큐로 대화 요약 및 근거와 함께 토스하여 상담원이 즉시 승인/반려할 수 있게 함
K-RAG/HWP 파싱: 단순 텍스트를 넘어 표(Table) 구조를 마크다운/JSON으로 재구성하여 인식함으로써 환각 현상 방지
관리자 대시보드: TCR, MTTR 외에 AI 신뢰도 분포도, 토큰 효율성 리포트, 에이전트 상담 이탈 지점 분석 포함

비기능적 요구사항 (Non-functional)
성능 (Performance): End-to-End 응답 속도 마지노선 1.5초~2.0초 (TTFT 800ms 포함)
보안 및 규정: ISMS-P 및 CSAP(공공) 인증 준수 아키텍처, 데이터 학습 방지(Zero-Retention) 협약
가용성: 목표 SLA 99.9% 이상, 장애 시 대체 LLM으로 즉시 전환되는 Failover 체계

4. 지표 및 성공의 정의
북극성 지표: 에이전트 업무 완결율 (TCR) - 상담원 개입 없이 AI가 업무를 스스로 완수한 비율 (목표 40% 이상)

핵심 성과 지표 (Key Metrics):
비즈니스: 상담 운영 비용 30% 절감, 상담원 평균 처리 시간(AHT) 단축
사용자: E2E Latency 1.5초 준수, 상담원 연결 요청률 감소
기술: RAG 환각률 3% 미만, PII 마스킹 성공률 100%, MCP 성공률 95%

가드레일 지표: 근거 기반 정확도(Grounding Score) - TCR을 높이느라 AI가 거짓 답변을 하는지 감시

5. 실행 계획 및 리스크 관리
우선순위:
P0: PII 마스킹, MCP 기본 액션, HWP/표 파싱
P1: HITL 알림, 기본 운영 대시보드

마일스톤: 2026.06 BMT → 07 PoC → 08 CBT → 2026.09 정식 런칭 (확신도: 보통)
배포 전략: 전략적 파트너 1곳 베타 → 이커머스 산업군 Limited Release → 전 시장 GA
핵심 의존성: 고객사 레거시 API 개방, 글로벌 LLM의 응답 안정성, ISMS-P 인증 심사 완료
주요 가정: 고객사의 RESTful API 보유, 비식별 데이터 전송 보안 정책 허용, AI에 대한 업무 권한 위임 수용

리스크 대응:
Latency 지연: 비동기(Async) 액션 및 중간 음성 피드백 활용
엣지 케이스: 정식 런칭 전 4주 이상의 Shadow Mode 테스트 기간 확보

해결되지 않은 질문들: TCR 기반 성과형 과금 모델 도입 여부, 데이터 소유권 귀속 주체, AI 오작동 시 법적 책임 소재`;

// ---------------------------------------------------------------------------
// Timestamp helper
// ---------------------------------------------------------------------------

function shortTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function stripJsonBlocks(text: string): string {
  if (!text) return '';
  let clean = text.replace(/```(?:json)?\s*[\s\S]*?```/g, '').trim();

  if (clean.startsWith('{') && clean.endsWith('}')) {
    try {
      JSON.parse(clean);
      return '';
    } catch {
      // Not valid JSON, keep it
    }
  }

  return clean;
}

// ---------------------------------------------------------------------------
// ChatPanel
// ---------------------------------------------------------------------------

interface ChatPanelProps {
  chat: UseChatReturn;
  onRunValidation?: () => void;
  onSaveCheckpoint?: () => void;
  onAction?: (actionId: string, payload?: any) => Promise<void>;
}

export function ChatPanel({
  chat,
  onRunValidation,
  onSaveCheckpoint,
  onAction,
}: ChatPanelProps) {
  const {
    messages,
    phase,
    availableActions,
    isLoading,
    error,
    sendMessage,
    setPendingInput,
    pendingInput,
    streamingMessage,
    streamingStatus,
  } = chat;

  const [localInput, setLocalInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Sync pendingInput (from question chips) into local state
  useEffect(() => {
    if (pendingInput) {
      setLocalInput(pendingInput);
      setPendingInput('');
      textareaRef.current?.focus();
    }
  }, [pendingInput, setPendingInput]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  function handleSend() {
    if (!localInput.trim() || isLoading) return;
    void sendMessage(localInput);
    setLocalInput('');
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleAction(action: string) {
    if (action === 'run_validation') {
      onRunValidation?.();
      return;
    }
    if (action === 'save_checkpoint') {
      onSaveCheckpoint?.();
      return;
    }

    if (
      [
        'run_simulation',
        'start_simulation',
        'stop_simulation',
        'generate_report',
        'generate_report_complete',
        'rewrite_prd',
      ].includes(action)
    ) {
      void onAction?.(action);
      return;
    }

    void sendMessage(`/${action}`);
  }

  function handleInsertDemo() {
    if (isLoading) return;
    setLocalInput(DEMO_PRD_CONTENT);
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
      }
    }, 0);
  }

  return (
    <Box style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-panel)' }}>
      {/* Panel Header */}
      <Group justify="space-between" px="md" py="xs" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)', background: 'rgba(255, 255, 255, 0.02)' }}>
        <Text fw={700} size="sm" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          Chat
        </Text>
        <PhaseBadge phase={phase} />
      </Group>

      {/* Message List */}
      <ScrollArea style={{ flex: 1, padding: '16px' }}>
        <Stack gap="md">
          {messages.length === 0 ? (
            <Text size="sm" mt="xs">세션을 초기화하는 중입니다…</Text>
          ) : (
            messages.map((msg) => (
              <Group
                key={msg.id}
                align="flex-start"
                justify={msg.role === 'user' ? 'flex-end' : 'flex-start'}
                gap="sm"
              >
                {msg.role !== 'user' && (
                  <Avatar color="teal" radius="xl" size="sm">AI</Avatar>
                )}
                
                <Stack gap={4} style={{ maxWidth: '75%' }} align={msg.role === 'user' ? 'flex-end' : 'flex-start'}>
                  <Paper
                    shadow="xs"
                    p="sm"
                    radius="md"
                    bg={msg.role === 'user' ? 'var(--bubble-user-bg)' : 'var(--bubble-assistant-bg)'}
                    c={msg.role === 'user' ? 'var(--bubble-user-text)' : 'var(--bubble-assistant-text)'}
                    style={{
                      border: '1px solid var(--border)'
                    }}
                  >
                    {msg.role === 'assistant' ? (
                      <div className={styles.markdownProse}>
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm, remarkBreaks]}
                          components={{
                            a: ({ node, ...props }) => (
                              <a {...props} target="_blank" rel="noopener noreferrer" style={{ color: '#38bdf8' }} />
                            ),
                            code: ({ node, className, children, ...props }) => {
                              const match = /language-(\w+)/.exec(className || '');
                              const isInline = !match;
                              return isInline ? (
                                <code style={{ background: 'rgba(255, 255, 255, 0.1)', padding: '2px 4px', borderRadius: 4, fontFamily: 'monospace', fontSize: '0.85em' }} {...props}>
                                  {children}
                                </code>
                              ) : (
                                <pre style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '12px', borderRadius: 8, overflowX: 'auto', margin: '8px 0' }}>
                                  <code className={className} style={{ fontFamily: 'monospace', fontSize: '0.85em' }} {...props}>
                                    {children}
                                  </code>
                                </pre>
                              );
                            },
                          }}
                        >
                          {stripJsonBlocks(msg.content) || '알겠습니다. PRD 내용을 업데이트했습니다.'}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <Text size="sm">{msg.content}</Text>
                    )}
                  </Paper>
                  <Text size="10px" c="dimmed">{shortTime(msg.timestamp)}</Text>
                </Stack>

                {msg.role === 'user' && (
                  <Avatar color="indigo" radius="xl" size="sm">U</Avatar>
                )}
              </Group>
            ))
          )}

          {isLoading && (
            <Group align="flex-start" gap="sm">
              <Avatar color="teal" radius="xl" size="sm">AI</Avatar>
              <Stack gap={4} style={{ maxWidth: '75%' }}>
                <Paper
                  shadow="xs"
                  p="sm"
                  radius="md"
                  bg="var(--bubble-assistant-bg)"
                  c="var(--bubble-assistant-text)"
                  style={{ border: '1px solid var(--border)' }}
                >
                  {streamingMessage ? (
                    <div className={styles.markdownProse}>
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm, remarkBreaks]}
                        components={{
                          code: ({ node, className, children, ...props }) => {
                            const match = /language-(\w+)/.exec(className || '');
                            const isInline = !match;
                            return isInline ? (
                              <code style={{ background: 'rgba(255, 255, 255, 0.1)', padding: '2px 4px', borderRadius: 4, fontFamily: 'monospace', fontSize: '0.85em' }} {...props}>{children}</code>
                            ) : (
                              <pre style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '12px', borderRadius: 8, overflowX: 'auto' }}>
                                <code className={className} style={{ fontFamily: 'monospace', fontSize: '0.85em' }} {...props}>{children}</code>
                              </pre>
                            );
                          },
                        }}
                      >
                        {streamingMessage + ' ▌'}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <Group gap="xs">
                      <Loader size="xs" color="indigo" />
                      <Text size="sm" c="dimmed">
                        {streamingStatus || '기획안 분석 중...'}
                      </Text>
                    </Group>
                  )}
                </Paper>
              </Stack>
            </Group>
          )}
          <div ref={bottomRef} />
        </Stack>
      </ScrollArea>

      {error && (
        <Alert color="red" radius={0} variant="filled" style={{ padding: '8px 16px' }}>
          {error}
        </Alert>
      )}

      {/* Action buttons */}
      {availableActions.length > 0 && (
        <Group gap="xs" px="md" py="xs" style={{ borderTop: '1px solid rgba(255, 255, 255, 0.05)', background: 'rgba(255, 255, 255, 0.01)' }}>
          {availableActions.map((action) => (
            <Button
              key={action}
              size="xs"
              variant="light"
              color="indigo"
              onClick={() => handleAction(action)}
              disabled={isLoading}
            >
              {actionLabel(action)}
            </Button>
          ))}
        </Group>
      )}

      {/* Input controls */}
      <Stack gap="xs" p="md" style={{ borderTop: '1px solid rgba(255, 255, 255, 0.05)', background: 'rgba(255, 255, 255, 0.02)' }}>
        <Group gap="xs">
          <Button
            size="xs"
            variant="subtle"
            color="indigo"
            onClick={handleInsertDemo}
            disabled={isLoading}
            style={{ flex: 1 }}
          >
            PRD 데모 내용 채우기
          </Button>
          <Button
            size="xs"
            variant="subtle"
            color="cyan"
            onClick={() => chat.quickStart("proj-simply-001")}
            disabled={isLoading}
            style={{ flex: 1 }}
          >
            데모 시뮬레이션 즉시 실행
          </Button>
        </Group>
        
        <Group align="flex-end" gap="xs">
          <Textarea
            ref={textareaRef}
            placeholder="메시지를 입력하세요..."
            value={localInput}
            onChange={(e) => setLocalInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            style={{ flex: 1 }}
            autosize
            minRows={1}
            maxRows={4}
            styles={{
              input: {
                background: 'var(--bg-app)',
                border: '1px solid var(--border)',
                color: 'var(--text-primary)',
                '&:focus': {
                  borderColor: 'var(--mantine-color-indigo-5)'
                }
              }
            }}
          />
          {isLoading ? (
            <ActionIcon
              size="lg"
              color="red"
              variant="filled"
              onClick={chat.cancelMessage}
              title="응답 중지"
            >
              Stop
            </ActionIcon>
          ) : (
            <ActionIcon
              size="lg"
              color="indigo"
              variant="filled"
              onClick={handleSend}
              disabled={!localInput.trim()}
              title="메시지 전송"
            >
              ↑
            </ActionIcon>
          )}
        </Group>
      </Stack>
    </Box>
  );
}

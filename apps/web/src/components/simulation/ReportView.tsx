import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Box, Paper, Title, Text, Button, Group, Loader, List, ThemeIcon } from '@mantine/core';

interface Props {
  sessionId: string;
  runId: string | null;
  performAction: (actionId: string, payload?: Record<string, unknown>) => Promise<void>;
  phase: string;
}

export function ReportView({ performAction, phase, sessionId, runId }: Props) {
  const [reportLog, setReportLog] = useState<string[]>([]);
  const [markdownResult, setMarkdownResult] = useState<string | null>(null);
  
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (phase === 'report_generating' || phase === 'report_complete') {
      // 상대 경로(/api)를 사용해야 dev 프록시와 nginx 배포 환경 모두에서 동작한다.
      // (하드코딩된 localhost:8000은 배포 빌드에서 영구 로딩 상태를 유발했다.)
      const eventSource = new EventSource(`/api/simulation/${encodeURIComponent(runId ?? "current")}/report/stream?session_id=${encodeURIComponent(sessionId)}`);
      let completeTimer: ReturnType<typeof setTimeout> | undefined;
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'report_error') {
            setError(data.markdown || data.message || '보고서 생성에 실패했습니다.');
            eventSource.close();
          } else if (data.type === 'report_complete') {
            setMarkdownResult(data.markdown);
            eventSource.close();
            if (phase === 'report_generating') completeTimer = setTimeout(() => performAction('generate_report_complete', {run_id: runId}), 1000);
          } else {
            setReportLog(prev => [...prev, data.title || data.type]);
          }
        } catch (e) {
          console.error('Error parsing report SSE', e);
        }
      };
      eventSource.onerror = () => {
        setError('보고서 연결이 끊겼습니다. 저장된 결과 조회 또는 재시도를 진행해주세요.');
        eventSource.close();
      };
      return () => {
        eventSource.close();
        if (completeTimer) clearTimeout(completeTimer);
      };
    }
  }, [phase, performAction, sessionId, runId, attempt]);

  return (
    <Box style={{ flex: 1, padding: '24px', display: 'flex', flexDirection: 'column', overflowY: 'auto', background: 'var(--bg-app)', width: '100%' }}>
      <Box style={{ maxWidth: '800px', margin: '0 auto', width: '100%' }}>
        {phase === 'simulation_result' && (
          <Paper
            shadow="xl"
            p="xl"
            withBorder
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              borderColor: 'rgba(255, 255, 255, 0.05)',
              textAlign: 'center',
              backdropFilter: 'blur(20px)'
            }}
          >
            <Title order={2} mb="md" style={{ color: '#fff', fontFamily: 'Outfit, sans-serif' }}>
              Simulation Complete
            </Title>
            <Text size="sm" c="dimmed" mb="xl" style={{ lineHeight: 1.6 }}>
              The multi-agent simulation has run its course. Developer and Product Personas have interacted and generated various findings, risks, and suggestions based on the PRD.
            </Text>
            <Button 
              size="md"
              variant="gradient"
              gradient={{ from: 'indigo', to: 'cyan' }}
              onClick={() => performAction('generate_report', {run_id: runId})}
            >
              Start Generating Report
            </Button>
          </Paper>
        )}

        {phase === 'report_generating' && (
          <Paper
            shadow="xl"
            p="xl"
            withBorder
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              borderColor: 'rgba(255, 255, 255, 0.05)',
              backdropFilter: 'blur(20px)'
            }}
          >
            <Group gap="xs" mb="lg">
              <Title order={3} style={{ color: '#fff', margin: 0, fontSize: '1.25rem' }}>
                Generating Report
              </Title>
              {!error && <Loader size="xs" color="indigo" />}
            </Group>
            
            {error && <Box role="alert" mb="md">
              <Text c="red" style={{ whiteSpace: 'pre-wrap' }}>{error}</Text>
              <Button mt="sm" onClick={async () => {
                try {
                  const response = await fetch(`/api/simulation/${encodeURIComponent(runId ?? "current")}/report?session_id=${encodeURIComponent(sessionId)}&retry=true`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
                  if (!response.ok) throw new Error('재시도 요청에 실패했습니다. 잠시 후 다시 시도해주세요.');
                  setError(null); setReportLog([]); setAttempt(value => value + 1);
                } catch (cause) { setError(cause instanceof Error ? cause.message : '재시도 실패'); }
              }}>보고서 다시 시도</Button>
            </Box>}
            <List
              spacing="xs"
              size="xs"
              center
              icon={
                <ThemeIcon color="teal" size={16} radius="xl">
                  ✓
                </ThemeIcon>
              }
              style={{ color: '#cbd5e1' }}
            >
              {reportLog.map((log, i) => (
                <List.Item key={i}>{log}</List.Item>
              ))}
            </List>
          </Paper>
        )}

        {phase === 'report_complete' && (
          <Paper
            shadow="xl"
            p="xl"
            withBorder
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              borderColor: 'rgba(255, 255, 255, 0.05)',
              backdropFilter: 'blur(20px)'
            }}
          >
            <Group justify="space-between" mb="xl" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
              <Title order={3} style={{ color: '#fff', margin: 0, fontSize: '1.25rem', fontFamily: 'Outfit, sans-serif' }}>
                Final Simulation Report
              </Title>
              <Group gap="xs">
                 <Button 
                   size="xs"
                   variant="outline"
                   color="gray"
                   onClick={() => performAction('download_report')}
                 >
                   Download Markdown
                 </Button>
                 <Button 
                   size="xs"
                   variant="gradient"
                   gradient={{ from: 'indigo', to: 'cyan' }}
                   onClick={() => performAction('rewrite_prd')}
                 >
                   Auto-Rewrite PRD
                 </Button>
                 <Button 
                   size="xs"
                   variant="filled"
                   color="dark"
                   onClick={() => performAction('go_back')}
                 >
                   Chat with AI
                 </Button>
              </Group>
            </Group>
            
            <Box style={{ color: '#cbd5e1', lineHeight: '1.7', fontSize: '0.95rem' }} className="markdown-body">
              <style>{`
                .markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4, .markdown-body h5, .markdown-body h6 {
                  color: #f8fafc !important;
                  margin-top: 1.5rem;
                  margin-bottom: 1rem;
                  font-weight: 700;
                  border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
                  padding-bottom: 0.3em;
                }
                .markdown-body p, .markdown-body li {
                  color: #cbd5e1 !important;
                  line-height: 1.7;
                }
                .markdown-body ul, .markdown-body ol {
                  padding-left: 1.5rem;
                  margin-bottom: 1rem;
                }
                .markdown-body li {
                  margin-bottom: 0.5rem;
                }
                .markdown-body hr {
                  border-color: rgba(255, 255, 255, 0.08) !important;
                  margin: 2rem 0;
                }
                .markdown-body table {
                  width: 100%;
                  border-collapse: collapse;
                  margin-bottom: 1rem;
                }
                .markdown-body th, .markdown-body td {
                  border: 1px solid rgba(255, 255, 255, 0.08);
                  padding: 8px 12px;
                  text-align: left;
                }
                .markdown-body th {
                  background-color: rgba(255, 255, 255, 0.02);
                  color: #f8fafc;
                }
                .markdown-body td {
                  color: #cbd5e1;
                }
              `}</style>
              <ReactMarkdown>{markdownResult || '저장된 보고서를 불러오는 중입니다.'}</ReactMarkdown>
            </Box>
          </Paper>
        )}
      </Box>
    </Box>
  );
}

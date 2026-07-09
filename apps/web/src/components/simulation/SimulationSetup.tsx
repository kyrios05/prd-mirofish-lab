import { useState, useEffect } from 'react';
import { Container, Grid, Card, TextInput, Textarea, Button, Text, Group, Box, Center, ActionIcon, Title, Paper, Badge, Stack, Progress } from '@mantine/core';

interface Stakeholder {
  name: string;
  role: string;
  review_angle: string;
  likely_objections: string[];
}

interface Props {
  performAction: (actionId: string, payload?: any) => Promise<void>;
  prd: any;
  liveMode?: boolean;
}

export function SimulationSetup({ performAction, prd, liveMode }: Props) {
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [stakeholders, setStakeholders] = useState<Stakeholder[]>([]);
  const [step, setStep] = useState<'initial' | 'config'>('initial');

  const [analyzeProgress, setAnalyzeProgress] = useState<number | null>(null);
  const [analyzeMsg, setAnalyzeMsg] = useState('');

  const [startProgress, setStartProgress] = useState<number | null>(null);
  const [startMsg, setStartMsg] = useState('');

  useEffect(() => {
    if (prd?.validation?.stakeholder_personas && prd.validation.stakeholder_personas.length > 0) {
      setStakeholders(prd.validation.stakeholder_personas);
      setStep('config');
    }
  }, [prd]);

  const handleAnalyze = () => {
    setAnalyzing(true);
    setAnalyzeProgress(0);
    setAnalyzeMsg('🔍 PRD 요구사항 도메인 추출 분석 중...');
    
    let current = 0;
    const interval = setInterval(async () => {
      current += 100 / 30; // 3초에 100% 도달
      if (current >= 100) {
        clearInterval(interval);
        setAnalyzeProgress(null);
        setAnalyzeMsg('');
        
        try {
          const response = await fetch('/api/simulation/propose-stakeholders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...(prd || {}), live: liveMode }),
          });
          const data = await response.json();
          if (data.status === 'success') {
            setStakeholders(data.stakeholders);
            setStep('config');
          }
        } catch (error) {
          console.error('Failed to propose stakeholders:', error);
        } finally {
          setAnalyzing(false);
        }
      } else {
        setAnalyzeProgress(Math.min(current, 99));
        if (current > 70) {
          setAnalyzeMsg('📑 30인 전문가 풀 매칭 및 페르소나 데이터 매핑 중...');
        } else if (current > 35) {
          setAnalyzeMsg('🤝 이해관계자 리스크 모델 및 피치덱 가이드라인 계산 중...');
        }
      }
    }, 100);
  };

  const handleStart = () => {
    setLoading(true);
    setStartProgress(0);
    setStartMsg('🌐 실시간 지식 그래프 네트워크 엔진 마운트 중...');
    
    let current = 0;
    const interval = setInterval(async () => {
      current += 100 / 30; // 3초에 100% 도달
      if (current >= 100) {
        clearInterval(interval);
        setStartProgress(null);
        setStartMsg('');
        
        await performAction("start_simulation", { stakeholder_personas: stakeholders, live: liveMode });
        setLoading(false);
      } else {
        setStartProgress(Math.min(current, 99));
        if (current > 70) {
          setStartMsg('⚖️ 30인 다자간 이해관계 합의 에이전트 초기 상태 검증 중...');
        } else if (current > 40) {
          setStartMsg('📡 에이전트 브로드캐스트 라우터 및 RAG 인덱서 초기화 중...');
        }
      }
    }, 100);
  };

  const updateStakeholder = (index: number, field: keyof Stakeholder, value: any) => {
    const updated = [...stakeholders];
    updated[index] = { ...updated[index], [field]: value };
    setStakeholders(updated);
  };

  const removeStakeholder = (index: number) => {
    setStakeholders(stakeholders.filter((_, i) => i !== index));
  };

  const addStakeholder = () => {
    setStakeholders([...stakeholders, {
      name: "New Stakeholder",
      role: "Other",
      review_angle: "Evaluate core functional requirements.",
      likely_objections: ["Anticipated objection description"]
    }]);
  };

  if (step === 'initial') {
    return (
      <Center style={{ flex: 1, padding: '2rem', background: 'radial-gradient(circle at center, #111827 0%, #090d16 100%)' }}>
        <Paper
          shadow="xl"
          p="xl"
          radius="lg"
          style={{
            maxWidth: '650px',
            width: '100%',
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid rgba(255, 255, 255, 0.05)',
            backdropFilter: 'blur(20px)',
            textAlign: 'center'
          }}
        >
          <Badge color="indigo" variant="light" size="lg" mb="md">
            Simulation Step 01
          </Badge>
          <Title order={2} style={{ marginBottom: '1rem', color: 'var(--text-primary)', fontSize: '2.2rem', fontFamily: 'Outfit, sans-serif' }}>
            Reality Seeds
          </Title>
          <Text size="sm" c="dimmed" mb="xl" style={{ lineHeight: 1.6 }}>
            To stress-test your PRD, we first need to identify the key stakeholders who will participate in the simulation. These agents will use their unique personas to challenge your requirements.
          </Text>

          <Button 
            size="lg"
            variant="gradient"
            gradient={{ from: 'indigo', to: 'cyan' }}
            onClick={handleAnalyze}
            loading={analyzing && analyzeProgress === null}
            disabled={analyzeProgress !== null}
            fullWidth
          >
            {analyzing ? 'Analyzing PRD...' : 'Identify Stakeholders'}
          </Button>

          {analyzeProgress !== null && (
            <Box mt="md" w="100%">
              <Progress value={analyzeProgress} animated color="indigo" size="md" />
              <Text size="xs" c="dimmed" mt={8} ta="center">
                {analyzeMsg} ({Math.round(analyzeProgress)}%)
              </Text>
            </Box>
          )}
        </Paper>
      </Center>
    );
  }

  return (
    <Box style={{ flex: 1, padding: '24px', overflowY: 'auto', background: '#090d16', width: '100%' }}>
      <Container size="xl">
        <Group justify="space-between" align="flex-end" mb="xl" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: '16px' }}>
          <Box>
            <Title order={2} style={{ color: 'var(--text-primary)', fontFamily: 'Outfit, sans-serif' }}>Persona Configuration</Title>
            <Text size="sm" c="dimmed" mt={4}>
              Review and refine the stakeholders who will stress-test your product.
            </Text>
          </Box>
          <Stack gap="xs" align="flex-end">
            <Group gap="sm">
              <Button variant="outline" color="gray" onClick={addStakeholder} disabled={startProgress !== null}>
                + Add Stakeholder
              </Button>
              <Button 
                variant="gradient"
                gradient={{ from: 'teal', to: 'lime' }}
                onClick={handleStart} 
                loading={loading && startProgress === null}
                disabled={startProgress !== null}
              >
                Start Simulation
              </Button>
            </Group>
            {startProgress !== null && (
              <Box w={300}>
                <Progress value={startProgress} animated color="teal" size="sm" />
                <Text size="10px" c="dimmed" mt={4} ta="right">
                  {startMsg} ({Math.round(startProgress)}%)
                </Text>
              </Box>
            )}
          </Stack>
        </Group>

        <Grid>
          {stakeholders.map((s, idx) => (
            <Grid.Col key={idx} span={{ base: 12, md: 6, lg: 4 }}>
              <Card
                shadow="xl"
                p="md"
                withBorder
                style={{
                  background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%)',
                  border: '1px solid rgba(99, 102, 241, 0.25)',
                  boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.4)',
                  backdropFilter: 'blur(8px)',
                  position: 'relative',
                  overflow: 'visible'
                }}
              >
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  onClick={() => removeStakeholder(idx)}
                  style={{ position: 'absolute', top: 12, right: 12 }}
                >
                  &times;
                </ActionIcon>
                
                <Group gap="md" mb="md">
                  <Center style={{ width: 44, height: 44, borderRadius: 8, background: 'rgba(99, 102, 241, 0.1)', color: '#818cf8', fontWeight: 700, fontSize: '0.85rem' }}>
                    {s.role ? s.role.slice(0, 2).toUpperCase() : 'ST'}
                  </Center>
                  <Box style={{ flex: 1 }}>
                    <TextInput 
                      value={s.name} 
                      onChange={(e) => updateStakeholder(idx, 'name', e.target.value)}
                      variant="unstyled"
                      styles={{
                        input: {
                          color: 'var(--text-primary)',
                          fontWeight: 700,
                          fontSize: '1.1rem',
                          height: 'auto',
                          padding: 0
                        }
                      }}
                    />
                    <TextInput 
                      value={s.role} 
                      onChange={(e) => updateStakeholder(idx, 'role', e.target.value)}
                      variant="unstyled"
                      styles={{
                        input: {
                          color: 'var(--mantine-color-indigo-4)',
                          fontWeight: 600,
                          fontSize: '0.8rem',
                          height: 'auto',
                          padding: 0
                        }
                      }}
                    />
                  </Box>
                </Group>

                <Stack gap="sm">
                  <Box>
                    <Text size="10px" fw={700} c="dimmed" mb={4} style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Review Angle
                    </Text>
                    <Textarea 
                      value={s.review_angle || ''} 
                      onChange={(e) => updateStakeholder(idx, 'review_angle', e.target.value)}
                      autosize
                      minRows={2}
                      maxRows={4}
                      placeholder="PRD에서 어떤 점을 검증하는지 기재합니다."
                      styles={{
                        input: {
                          background: 'rgba(0, 0, 0, 0.2)',
                          border: '1px solid rgba(255, 255, 255, 0.05)',
                          color: '#cbd5e1',
                          fontSize: '0.85rem'
                        }
                      }}
                    />
                  </Box>

                  <Box>
                    <Text size="10px" fw={700} c="dimmed" mb={4} style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Likely Objections (Enter-separated)
                    </Text>
                    <Textarea 
                      value={s.likely_objections ? s.likely_objections.join('\n') : ''} 
                      onChange={(e) => updateStakeholder(idx, 'likely_objections', e.target.value.split('\n'))}
                      autosize
                      minRows={2}
                      maxRows={4}
                      placeholder="예상되는 이의나 지적 사항을 입력하세요."
                      styles={{
                        input: {
                          background: 'rgba(0, 0, 0, 0.2)',
                          border: '1px solid rgba(255, 255, 255, 0.05)',
                          color: '#cbd5e1',
                          fontSize: '0.85rem'
                        }
                      }}
                    />
                  </Box>
                </Stack>
              </Card>
            </Grid.Col>
          ))}
        </Grid>
      </Container>
    </Box>
  );
}

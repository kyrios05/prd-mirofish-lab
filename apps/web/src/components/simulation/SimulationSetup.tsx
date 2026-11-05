import { useState } from 'react';
import { Container, Grid, Card, TextInput, Textarea, Button, Text, Group, Box, Center, ActionIcon, Title, Paper, Badge, Stack, Progress, NativeSelect } from '@mantine/core';

interface Stakeholder {
  name: string;
  role: string;
  review_angle: string;
  likely_objections: string[];
  source_uuid?: string | null;
}

interface Props {
  sessionId: string;
  performAction: (actionId: string, payload?: Record<string, unknown>) => Promise<void>;
  liveMode?: boolean;
  prd?: Record<string, unknown> | null;
}

export function SimulationSetup({ performAction, liveMode, prd, sessionId }: Props) {
  const [seedSource, setSeedSource] = useState('llm');
  const [selectionId, setSelectionId] = useState<string | null>(null);
  const [datasetSource, setDatasetSource] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [stakeholders, setStakeholders] = useState<Stakeholder[]>([]);
  const [step, setStep] = useState<'initial' | 'config'>('initial');

  const [analyzeProgress, setAnalyzeProgress] = useState<number | null>(null);
  const analyzeMsg = '';
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const [startProgress, setStartProgress] = useState<number | null>(null);
  const [startMsg, setStartMsg] = useState('');

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setAnalyzeError(null);
    setAnalyzeProgress(null);
    setSelectionId(null);
    setDatasetSource(null);
    try {
      const nemotron = seedSource === 'nemotron';
      if (nemotron && !liveMode) throw new Error('Nemotron 시드 생성은 Live ON에서 사용할 수 있습니다.');
      const response = await fetch(nemotron ? '/api/simulation/reality-seeds/nemotron' : '/api/simulation/propose-stakeholders', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(nemotron ? {session_id: sessionId, prd} : {live: liveMode, prd}),
      });
      const data = await response.json();
      if (!response.ok || data.status !== 'success') throw new Error(data.detail || data.message || 'Seed 생성에 실패했습니다.');
      setStakeholders(data.stakeholders.map((member: Stakeholder, index: number) => ({...member, source_uuid: data.members?.[index]?.source_uuid})));
      setSelectionId(data.selection_id ?? null);
      setDatasetSource(data.provenance?.dataset_url ?? null);
      setStep('config');
    } catch (error) {
      setAnalyzeError(error instanceof Error ? error.message : 'Seed 생성에 실패했습니다.');
    } finally { setAnalyzing(false); }
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
        
        await performAction("start_simulation", {
          stakeholder_personas: stakeholders.map(member => ({name: member.name, role: member.role, review_angle: member.review_angle, likely_objections: member.likely_objections})),
          live: liveMode, seed_selection_id: selectionId,
          stakeholder_seed_refs: stakeholders.map(member => member.source_uuid ?? null),
        });
        setLoading(false);
      } else {
        setStartProgress(Math.min(current, 99));
        if (current > 70) {
          setStartMsg('선택한 참여자 설정 확인 중...');
        } else if (current > 40) {
          setStartMsg('시뮬레이션 실행 요청 준비 중...');
        }
      }
    }, 100);
  };

  const updateStakeholder = (index: number, field: keyof Stakeholder, value: string | string[]) => {
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

          <NativeSelect label="Seed 생성 방식" value={seedSource} onChange={event => setSeedSource(event.currentTarget.value)} mb="md"
            data={[{value: 'llm', label: 'PRD 기반 이해관계자'}, {value: 'nemotron', label: 'Nemotron 한국 사용자 8명 + 전문 검토자 4명'}]} disabled={analyzing} />
          {seedSource === 'nemotron' && <Text size="xs" c="dimmed" mb="md">Live ON 필요 · NVIDIA 합성 페르소나 후보에서 PRD에 맞게 선정합니다. 실제 고객 조사 결과를 뜻하지 않습니다.</Text>}
          <Button
            size="lg"
            variant="gradient"
            gradient={{ from: 'indigo', to: 'cyan' }}
            onClick={handleAnalyze}
            loading={analyzing && analyzeProgress === null}
            disabled={analyzing || (seedSource === 'nemotron' && !liveMode)}
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
          {analyzeError && <Text size="sm" c="red.4" mt="md">{analyzeError}</Text>}
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
            {datasetSource && <Text size="xs" c="teal" mt="sm">출처: <a href={datasetSource} target="_blank" rel="noreferrer">NVIDIA Nemotron-Personas-Korea</a> · CC BY 4.0 · 원본 UUID와 추가 생성 관점은 실행에 별도 저장됩니다. 편집 사항은 원본과 구분됩니다.</Text>}
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
                disabled={startProgress !== null || stakeholders.length < 8}
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
                    {s.source_uuid !== undefined && <Badge size="xs" mb="xs" color={s.source_uuid ? 'teal' : 'indigo'}>{s.source_uuid ? `Nemotron · ${s.source_uuid.slice(0, 8)}` : '추가 생성 전문 검토자'}</Badge>}
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

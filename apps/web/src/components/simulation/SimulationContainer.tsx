import { SimulationSetup } from './SimulationSetup';
import { SimulationRunner } from './SimulationRunner';
import { ReportView } from './ReportView';
import { Box, Group, Title, Button, Badge, Select } from '@mantine/core';

interface SimulationContainerProps {
  chat: any;
  performAction: (actionId: string, payload?: Record<string, any>) => Promise<void>;
  liveMode: boolean;
  setLiveMode: (live: boolean) => void;
  theme: string;
  setTheme: (theme: string) => void;
}

export function SimulationContainer({ chat, performAction, liveMode, setLiveMode, theme, setTheme }: SimulationContainerProps) {
  const { phase } = chat;

  return (
    <Box style={{ 
      position: 'fixed', 
      top: 0, 
      left: 0, 
      width: '100vw', 
      height: '100vh', 
      display: 'flex', 
      flexDirection: 'column', 
      backgroundColor: 'var(--bg-app)', 
      color: 'var(--text-primary)', 
      zIndex: 10000,
      overflow: 'hidden'
    }}>
      <Group justify="space-between" px="xl" py="md" style={{ 
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)', 
        background: 'rgba(9, 13, 22, 0.85)',
        backdropFilter: 'blur(12px)',
        flexShrink: 0 
      }}>
        <Title order={3} style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 800, background: 'linear-gradient(to right, #38bdf8, #818cf8)', WebkitBackgroundClip: 'text', color: 'transparent', letterSpacing: '-0.02em' }}>
          MiroFish Simulation Lab
        </Title>
        <Group gap="md">
          <Select
            size="xs"
            value={theme}
            onChange={(val) => setTheme(val || 'black')}
            data={[
              { value: 'black', label: 'Theme: Black' },
              { value: 'ocean', label: 'Theme: Ocean' },
              { value: 'aurora', label: 'Theme: Aurora' },
              { value: 'sand', label: 'Theme: Sand' }
            ]}
            style={{ width: 130 }}
            styles={{
              input: {
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: 'var(--text-primary)',
              },
              dropdown: {
                background: 'var(--bg-panel)',
                border: '1px solid var(--border)',
              }
            }}
          />

          <Button
            size="xs"
            variant="subtle"
            color={liveMode ? 'teal' : 'gray'}
            onClick={() => setLiveMode(!liveMode)}
            leftSection={<span style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: liveMode ? '#10b981' : '#94a3b8',
              boxShadow: liveMode ? '0 0 8px #10b981' : 'none'
            }} />}
            styles={{
              root: {
                backgroundColor: liveMode ? 'rgba(16, 185, 129, 0.08)' : 'rgba(255, 255, 255, 0.03)',
                border: liveMode ? '1px solid rgba(16, 185, 129, 0.2)' : '1px solid rgba(255, 255, 255, 0.08)',
                '&:hover': {
                  backgroundColor: liveMode ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.06)',
                }
              }
            }}
          >
            {liveMode ? "Live ON (Qwen)" : "Live OFF (Mock)"}
          </Button>
          <Badge size="lg" color="indigo" radius="sm" style={{ letterSpacing: '0.05em' }}>
            {phase.toUpperCase().replace('_', ' ')}
          </Badge>
        </Group>
      </Group>
      <Box style={{ flex: 1, display: 'flex', width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}>
        {phase === 'simulation_setup' && <SimulationSetup performAction={performAction} prd={chat.current_prd_draft} liveMode={liveMode} />}
        {phase === 'simulating' && <SimulationRunner performAction={performAction} />}
        {(phase === 'simulation_result' || phase === 'report_generating' || phase === 'report_complete') && (
          <ReportView performAction={performAction} phase={phase} />
        )}
      </Box>
    </Box>
  );
}

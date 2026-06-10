import { SimulationSetup } from './SimulationSetup';
import { SimulationRunner } from './SimulationRunner';
import { ReportView } from './ReportView';

interface SimulationContainerProps {
  chat: any;
  performAction: (actionId: string, payload?: Record<string, any>) => Promise<void>;
  liveMode: boolean;
  setLiveMode: (live: boolean) => void;
}

export function SimulationContainer({ chat, performAction, liveMode, setLiveMode }: SimulationContainerProps) {
  const { phase } = chat;

  return (
    <div style={{ 
      position: 'fixed', 
      top: 0, 
      left: 0, 
      width: '100vw', 
      height: '100vh', 
      display: 'flex', 
      flexDirection: 'column', 
      backgroundColor: '#020617', 
      color: '#f8fafc', 
      fontFamily: 'Inter, sans-serif',
      zIndex: 10000,
      overflow: 'hidden'
    }}>
      <header style={{ 
        padding: '1rem 2rem', 
        borderBottom: '1px solid #1e293b', 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        background: 'rgba(2, 6, 23, 0.8)',
        backdropFilter: 'blur(10px)',
        flexShrink: 0 
      }}>
        <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.025em', background: 'linear-gradient(to right, #38bdf8, #818cf8)', WebkitBackgroundClip: 'text', color: 'transparent' }}>
          🐟 MiroFish Simulation Lab
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            {/* Live Mode Toggle */}
            <button
              onClick={() => setLiveMode(!liveMode)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.4rem 1rem',
                borderRadius: '8px',
                fontSize: '0.75rem',
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.25s ease-in-out',
                border: liveMode ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(100, 116, 139, 0.4)',
                background: liveMode ? 'rgba(16, 185, 129, 0.08)' : 'rgba(100, 116, 139, 0.08)',
                color: liveMode ? '#10b981' : '#94a3b8',
                boxShadow: liveMode ? '0 0 10px rgba(10, 253, 148, 0.2)' : '0 0 10px rgba(100, 116, 139, 0.1)',
                backdropFilter: 'blur(4px)',
                outline: 'none'
              }}
              title={liveMode ? "Live Mode: Qwen Engine" : "Mock Mode: Simulation"}
            >
              <span style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: liveMode ? '#10b981' : '#64748b',
                boxShadow: liveMode ? '0 0 8px #10b981' : '0 0 8px #64748b',
                transition: 'all 0.25s ease-in-out'
              }}></span>
              {liveMode ? "Live ON (Qwen)" : "Live OFF (Mock)"}
            </button>
            <div style={{ padding: '0.4rem 1rem', borderRadius: '20px', background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.2)', color: '#38bdf8', fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.1em' }}>
              {phase.toUpperCase().replace('_', ' ')}
            </div>
        </div>
      </header>
      <main style={{ flex: 1, display: 'flex', width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}>
        {phase === 'simulation_setup' && <SimulationSetup performAction={performAction} prd={chat.current_prd_draft} liveMode={liveMode} />}
        {phase === 'simulating' && <SimulationRunner performAction={performAction} />}
        {(phase === 'simulation_result' || phase === 'report_generating' || phase === 'report_complete') && (
            <ReportView performAction={performAction} phase={phase} />
        )}
      </main>
    </div>
  );
}

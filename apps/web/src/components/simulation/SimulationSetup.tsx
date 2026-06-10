import { useState, useEffect } from 'react';

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

  // Initialize from PRD if already present
  useEffect(() => {
    if (prd?.validation?.stakeholder_personas && prd.validation.stakeholder_personas.length > 0) {
      setStakeholders(prd.validation.stakeholder_personas);
      setStep('config');
    }
  }, [prd]);

  const handleAnalyze = async () => {
    if (!prd) {
      console.warn("PRD draft is missing, sending empty object");
    }
    setAnalyzing(true);
    try {
      const response = await fetch('/api/simulation/propose-stakeholders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(prd || {}),
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
  };

  const handleStart = async () => {
    setLoading(true);
    // Send the possibly EDITED stakeholders back to the backend
    await performAction("start_simulation", { stakeholder_personas: stakeholders, live: liveMode });
    setLoading(false);
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
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem', background: 'radial-gradient(circle at center, #1e293b 0%, #020617 100%)' }}>
        <div style={{ maxWidth: '800px', width: '90%', background: 'rgba(30, 41, 59, 0.5)', padding: '3.5rem', borderRadius: '24px', backdropFilter: 'blur(20px)', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)', border: '1px solid rgba(255, 255, 255, 0.1)', textAlign: 'center' }}>
          <div style={{ display: 'inline-block', padding: '0.5rem 1rem', background: '#3b82f620', color: '#3b82f6', borderRadius: '12px', fontSize: '0.875rem', fontWeight: 600, marginBottom: '1.5rem' }}>Simulation Step 01</div>
          <h3 style={{ marginTop: 0, marginBottom: '1.5rem', color: '#f8fafc', fontSize: '2.5rem', fontWeight: 800, letterSpacing: '-0.05em' }}>Reality Seeds</h3>
          <p style={{ color: '#94a3b8', marginBottom: '3rem', fontSize: '1.125rem', lineHeight: 1.8, maxWidth: '600px', margin: '0 auto 3rem auto' }}>
            To stress-test your PRD, we first need to identify the key stakeholders who will participate in the simulation. These agents will use their unique personas to challenge your requirements.
          </p>

          <button 
            onClick={handleAnalyze}
            disabled={analyzing}
            style={{ 
              width: '100%', 
              maxWidth: '400px',
              padding: '1.25rem', 
              background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)', 
              color: 'white', 
              border: 'none', 
              borderRadius: '12px', 
              fontSize: '1.125rem', 
              fontWeight: 700, 
              cursor: analyzing ? 'not-allowed' : 'pointer', 
              opacity: analyzing ? 0.7 : 1, 
              transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              boxShadow: '0 10px 15px -3px rgba(37, 99, 235, 0.3)'
            }}
          >
            {analyzing ? 'Analyzing PRD...' : '🔍 Identify Stakeholders'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, padding: '3rem', overflowY: 'auto', background: '#020617' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '3rem' }}>
          <div>
            <h3 style={{ margin: 0, color: '#f8fafc', fontSize: '2.5rem', fontWeight: 800, letterSpacing: '-0.05em' }}>Persona Configuration</h3>
            <p style={{ color: '#94a3b8', marginTop: '0.5rem', fontSize: '1.125rem' }}>
              Review and refine the stakeholders who will stress-test your product.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '1rem' }}>
            <button onClick={addStakeholder} style={{ padding: '0.75rem 1.5rem', background: 'rgba(255, 255, 255, 0.05)', color: '#cbd5e1', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '10px', fontWeight: 600, cursor: 'pointer' }}>+ Add Stakeholder</button>
            <button 
              onClick={handleStart} 
              disabled={loading}
              style={{ 
                padding: '0.75rem 2rem', 
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', 
                color: 'white', 
                border: 'none', 
                borderRadius: '10px', 
                fontWeight: 700, 
                fontSize: '1rem',
                cursor: loading ? 'not-allowed' : 'pointer',
                boxShadow: '0 10px 15px -3px rgba(16, 185, 129, 0.3)'
              }}
            >
              {loading ? 'Initializing Engine...' : '🚀 Start Simulation'}
            </button>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '1.5rem' }}>
          {stakeholders.map((s, idx) => (
            <div key={idx} style={{ background: 'rgba(30, 41, 59, 0.6)', borderRadius: '20px', border: '1px solid rgba(255, 255, 255, 0.1)', padding: '1.5rem', position: 'relative' }}>
              <button 
                onClick={() => removeStakeholder(idx)}
                style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: '1.2rem' }}
              >
                &times;
              </button>
              
              <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', alignItems: 'center' }}>
                <div style={{ width: '48px', height: '48px', background: '#3b82f620', color: '#3b82f6', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.5rem' }}>
                  {s.role.toLowerCase().includes('pm') ? '🧑‍💼' : s.role.toLowerCase().includes('dev') ? '👨‍💻' : '👤'}
                </div>
                <div style={{ flex: 1 }}>
                  <input 
                    value={s.name} 
                    onChange={(e) => updateStakeholder(idx, 'name', e.target.value)}
                    style={{ background: 'none', border: 'none', color: '#f8fafc', fontSize: '1.25rem', fontWeight: 700, width: '100%', marginBottom: '0.25rem' }}
                  />
                  <input 
                    value={s.role} 
                    onChange={(e) => updateStakeholder(idx, 'role', e.target.value)}
                    style={{ background: 'none', border: 'none', color: '#3b82f6', fontSize: '0.875rem', fontWeight: 600, width: '100%' }}
                  />
                </div>
              </div>

              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{ display: 'block', color: '#64748b', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', marginBottom: '0.5rem', letterSpacing: '0.05em' }}>Review Angle</label>
                <textarea 
                  value={s.review_angle || ''} 
                  onChange={(e) => updateStakeholder(idx, 'review_angle', e.target.value)}
                  style={{ width: '100%', background: 'rgba(15, 23, 42, 0.5)', border: '1px solid rgba(255, 255, 255, 0.05)', borderRadius: '8px', padding: '0.75rem', color: '#cbd5e1', fontSize: '0.9rem', lineHeight: 1.5, resize: 'none', height: '80px' }}
                  placeholder="PRD에서 어떤 점을 검증하는지 기재합니다."
                />
              </div>

              <div>
                <label style={{ display: 'block', color: '#64748b', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', marginBottom: '0.5rem', letterSpacing: '0.05em' }}>Likely Objections (Enter-separated)</label>
                <textarea 
                  value={s.likely_objections ? s.likely_objections.join('\n') : ''} 
                  onChange={(e) => updateStakeholder(idx, 'likely_objections', e.target.value.split('\n'))}
                  style={{ width: '100%', background: 'rgba(15, 23, 42, 0.5)', border: '1px solid rgba(255, 255, 255, 0.05)', borderRadius: '8px', padding: '0.75rem', color: '#cbd5e1', fontSize: '0.9rem', lineHeight: 1.5, resize: 'none', height: '80px' }}
                  placeholder="예상되는 이의나 지적 사항을 한 줄에 하나씩 입력하세요."
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

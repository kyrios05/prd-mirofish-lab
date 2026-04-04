/**
 * App.tsx — Root application component.
 *
 * T07: Minimal smoke-test shell.
 *   • Calls GET /health on mount to verify backend connectivity.
 *   • Displays connection status, backend version, and available endpoints.
 *   • Provides a foundation for T08 (3-panel UI).
 *
 * T08 will replace the body of this component with ChatPanel + PRDPreview +
 * ValidationPanel.  The health-check hook can be extracted to a custom hook
 * in T08 if needed.
 *
 * Scope guard
 * -----------
 * - UI panel components (ChatPanel etc.): T08
 * - State management library: T08
 * - Styling/design system: T08
 */

import { useEffect, useState } from 'react';
import { BASE_URL, ApiError } from './api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HealthResponse {
  status: string;
  version?: string;
  [key: string]: unknown;
}

type ConnectionStatus = 'checking' | 'connected' | 'error';

// ---------------------------------------------------------------------------
// App component
// ---------------------------------------------------------------------------

function App() {
  const [status, setStatus] = useState<ConnectionStatus>('checking');
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>('');

  useEffect(() => {
    let cancelled = false;

    async function checkHealth() {
      try {
        const res = await fetch(`${BASE_URL}/health`);
        if (!res.ok) {
          throw new ApiError(res.status, `HTTP ${res.status} ${res.statusText}`);
        }
        const data = (await res.json()) as HealthResponse;
        if (!cancelled) {
          setHealthData(data);
          setStatus('connected');
        }
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ApiError) {
            setErrorMessage(`API error ${err.status}: ${err.message}`);
          } else if (err instanceof Error) {
            setErrorMessage(err.message);
          } else {
            setErrorMessage('Unknown error');
          }
          setStatus('error');
        }
      }
    }

    void checkHealth();
    return () => { cancelled = true; };
  }, []);

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>PRD MiroFish Lab</h1>
        <p style={styles.subtitle}>AI-driven PRD generation &amp; validation</p>
      </header>

      <main style={styles.main}>
        {/* ── API Connection Status ────────────────────────────────────── */}
        <section style={styles.card}>
          <h2 style={styles.cardTitle}>Backend Connection</h2>

          {status === 'checking' && (
            <p style={styles.statusChecking}>⏳ Checking API connection…</p>
          )}

          {status === 'connected' && (
            <>
              <p style={styles.statusOk}>✅ API Connected</p>
              <p style={styles.detail}>
                <strong>Endpoint:</strong> <code>{BASE_URL}</code>
              </p>
              {healthData && (
                <pre style={styles.pre}>
                  {JSON.stringify(healthData, null, 2)}
                </pre>
              )}
            </>
          )}

          {status === 'error' && (
            <>
              <p style={styles.statusError}>❌ API Unreachable</p>
              <p style={styles.detail}>
                <strong>Target:</strong> <code>{BASE_URL}</code>
              </p>
              <p style={styles.errorMsg}>{errorMessage}</p>
              <p style={styles.hint}>
                Start the backend with:{' '}
                <code>cd apps/api &amp;&amp; uvicorn app.main:app --reload</code>
              </p>
            </>
          )}
        </section>

        {/* ── Available Endpoints ──────────────────────────────────────── */}
        <section style={styles.card}>
          <h2 style={styles.cardTitle}>Available API Endpoints</h2>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Method</th>
                <th style={styles.th}>Path</th>
                <th style={styles.th}>Description</th>
              </tr>
            </thead>
            <tbody>
              {ENDPOINTS.map((ep, i) => (
                <tr key={i} style={i % 2 === 0 ? styles.trEven : styles.trOdd}>
                  <td style={{ ...styles.td, ...styles.method }}>{ep.method}</td>
                  <td style={{ ...styles.td, ...styles.path }}><code>{ep.path}</code></td>
                  <td style={styles.td}>{ep.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* ── T08 Placeholder ──────────────────────────────────────────── */}
        <section style={styles.card}>
          <h2 style={styles.cardTitle}>UI Status</h2>
          <p style={styles.detail}>
            🚧 <strong>T08</strong> — 3-panel UI (Chat | PRD Preview | Validation) coming next.
          </p>
          <p style={styles.detail}>
            TypeScript types and API client are ready in{' '}
            <code>src/types/</code> and <code>src/api/</code>.
          </p>
        </section>
      </main>
    </div>
  );
}

export default App;

// ---------------------------------------------------------------------------
// Endpoint reference table
// ---------------------------------------------------------------------------

const ENDPOINTS = [
  { method: 'POST', path: '/chat/sessions',                         description: 'Create new session' },
  { method: 'GET',  path: '/chat/sessions/{id}',                    description: 'Session status' },
  { method: 'POST', path: '/chat/message',                          description: 'Send chat message → PRD draft' },
  { method: 'POST', path: '/chat/sessions/{id}/checkpoint',         description: 'Create checkpoint' },
  { method: 'POST', path: '/chat/sessions/{id}/restore',            description: 'Restore checkpoint' },
  { method: 'GET',  path: '/chat/sessions/{id}/checkpoints',        description: 'List checkpoints' },
  { method: 'POST', path: '/validation/run',                        description: 'Full validation pipeline' },
  { method: 'POST', path: '/validation/package',                    description: 'Package SimulationSpec only' },
  { method: 'POST', path: '/validation/schema-check',               description: 'JSON Schema check only' },
  { method: 'GET',  path: '/health',                                description: 'Health check' },
  { method: 'GET',  path: '/',                                      description: 'Root info' },
];

// ---------------------------------------------------------------------------
// Inline styles (replaced by design system in T08)
// ---------------------------------------------------------------------------

const styles: Record<string, React.CSSProperties> = {
  container: {
    fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
    maxWidth: 900,
    margin: '0 auto',
    padding: '2rem 1.5rem',
    color: '#1a1a2e',
    lineHeight: 1.6,
  },
  header: {
    borderBottom: '2px solid #e2e8f0',
    paddingBottom: '1rem',
    marginBottom: '2rem',
  },
  title: {
    fontSize: '1.75rem',
    fontWeight: 700,
    margin: 0,
    color: '#0f172a',
  },
  subtitle: {
    margin: '0.25rem 0 0',
    color: '#64748b',
    fontSize: '1rem',
  },
  main: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1.5rem',
  },
  card: {
    background: '#ffffff',
    border: '1px solid #e2e8f0',
    borderRadius: 8,
    padding: '1.5rem',
    boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
  },
  cardTitle: {
    fontSize: '1.1rem',
    fontWeight: 600,
    margin: '0 0 1rem',
    color: '#334155',
  },
  statusChecking: { color: '#92400e', fontSize: '1rem', margin: 0 },
  statusOk: { color: '#166534', fontSize: '1rem', margin: '0 0 0.5rem', fontWeight: 600 },
  statusError: { color: '#991b1b', fontSize: '1rem', margin: '0 0 0.5rem', fontWeight: 600 },
  detail: { margin: '0.25rem 0', color: '#475569', fontSize: '0.9rem' },
  errorMsg: { color: '#991b1b', fontFamily: 'monospace', fontSize: '0.875rem', margin: '0.5rem 0' },
  hint: { color: '#6b7280', fontSize: '0.875rem', margin: '0.5rem 0' },
  pre: {
    background: '#f8fafc',
    border: '1px solid #e2e8f0',
    borderRadius: 4,
    padding: '0.75rem',
    fontSize: '0.8rem',
    overflowX: 'auto',
    margin: '0.5rem 0 0',
  },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' },
  th: {
    textAlign: 'left',
    padding: '0.5rem 0.75rem',
    background: '#f1f5f9',
    fontWeight: 600,
    color: '#374151',
    borderBottom: '1px solid #e2e8f0',
  },
  td: { padding: '0.4rem 0.75rem', borderBottom: '1px solid #f1f5f9', verticalAlign: 'top' },
  trEven: { background: '#ffffff' },
  trOdd: { background: '#fafafa' },
  method: { fontWeight: 600, color: '#1d4ed8', minWidth: 60 },
  path: { minWidth: 280, color: '#374151' },
};

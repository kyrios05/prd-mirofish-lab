import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  /**
   * Dev-server proxy — routes /api/* to the FastAPI backend during local
   * development, avoiding CORS preflight issues.
   *
   * Usage in API calls (alternative pattern):
   *   fetch('/api/chat/sessions')   ← proxied to http://localhost:8000/chat/sessions
   *
   * The default API client (src/api/client.ts) uses VITE_API_URL directly
   * (http://localhost:8000), so this proxy is an optional convenience for
   * T08 components that prefer relative paths.
   */
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Strip the /api prefix before forwarding
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})

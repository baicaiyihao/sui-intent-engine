import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// VITE_API_BASE controls where the Vite dev-server proxies /api /intent /market to.
// - Local dev (default): http://localhost:8000 / :8001 (Vite splits routes by path prefix)
// - Point at production: https://sui-intent.duckdns.org (so dev mirrors prod wiring)
const API_BASE = process.env.VITE_API_BASE || ''

export default defineConfig(({ mode }) => {
  // Load .env / .env.local so VITE_API_BASE is picked up
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const base = env.VITE_API_BASE || API_BASE

  // Helper: build proxy target with /api|/intent|/market prefix routed to the right backend
  // Both backends are fronted by a single nginx entry in production, so default to API_BASE
  // and let the upstream nginx path routing handle backend-A vs backend-B split.
  const target = base || 'http://localhost:8000'
  const targetB = base || 'http://localhost:8001'

  return {
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        // backend-A: /api/v1/analyze, /api/v1/backtest, /api/v1/strategy*, /api/v1/indicator*, /api/v1/script, /api/v1/ai
        '/api/v1/analyze':    { target, changeOrigin: true, secure: false },
        '/api/v1/backtest':   { target, changeOrigin: true, secure: false },
        '/api/v1/strategy':   { target, changeOrigin: true, secure: false },
        '/api/v1/strategies': { target, changeOrigin: true, secure: false },
        '/api/v1/indicator':  { target, changeOrigin: true, secure: false },
        '/api/v1/script':     { target, changeOrigin: true, secure: false },
        '/api/v1/ai':         { target, changeOrigin: true, secure: false },

        // backend-B: /api/v1/market, /api/v1/cache, /api/v1/deepbook, /intent/, /market/
        '/api/v1/market':     { target: targetB, changeOrigin: true, secure: false },
        '/api/v1/cache':      { target: targetB, changeOrigin: true, secure: false },
        '/api/v1/deepbook':   { target: targetB, changeOrigin: true, secure: false },
        '/intent':            { target: targetB, changeOrigin: true, secure: false },
        '/market':            { target: targetB, changeOrigin: true, secure: false }
      }
    }
  }
})

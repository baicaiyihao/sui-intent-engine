import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Production API base — used by Vercel rewrites AND by Vite dev proxy.
// Local dev will route through duckdns the same way the deployed Vercel site does.
const PROD_API = 'https://sui-intent.duckdns.org'

export default defineConfig(({ mode }) => {
  // loadEnv reads .env / .env.local / .env.[mode] from project root and surfaces
  // VITE_* variables on import.meta.env at runtime.
  const env = loadEnv(mode, process.cwd(), '')

  // Allow override via .env.local (VITE_API_BASE=...) — defaults to production URL.
  const base = env.VITE_API_BASE || PROD_API

  // Both backends live behind one nginx entry in production, so use the same base
  // and let upstream nginx path routing handle backend-A vs backend-B.
  const targetA = base
  const targetB = base

  return {
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        // ---------- backend-A (quant_core :8000) — nginx routes these ----------
        '/api/v1/analyze':    { target: targetA, changeOrigin: true, secure: false },
        '/api/v1/backtest':   { target: targetA, changeOrigin: true, secure: false },
        '/api/v1/strategy':   { target: targetA, changeOrigin: true, secure: false },
        '/api/v1/strategies': { target: targetA, changeOrigin: true, secure: false },
        '/api/v1/indicator':  { target: targetA, changeOrigin: true, secure: false },
        '/api/v1/script':     { target: targetA, changeOrigin: true, secure: false },
        '/api/v1/ai':         { target: targetA, changeOrigin: true, secure: false },

        // ---------- backend-B (sui_intent_server :8001) — nginx routes these ----------
        '/api/v1/market':     { target: targetB, changeOrigin: true, secure: false },
        '/api/v1/cache':      { target: targetB, changeOrigin: true, secure: false },
        '/api/v1/deepbook':   { target: targetB, changeOrigin: true, secure: false },
        '/intent':            { target: targetB, changeOrigin: true, secure: false },
        '/market':            { target: targetB, changeOrigin: true, secure: false }
      }
    },
    build: {
      // Vercel serves /dist as static files, but if any code uses import.meta.env.VITE_API_BASE
      // we want it inlined at build time.
      sourcemap: false
    }
  }
})

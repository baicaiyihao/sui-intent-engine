import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // quant_core (8000): AI signals, indicators, quick-question, backtest
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      // sui_intent_server (8001): natural language trade intent parsing
      '/intent': {
        target: 'http://localhost:8001',
        changeOrigin: true
      },
      '/market': {
        target: 'http://localhost:8001',
        changeOrigin: true
      }
    }
  }
})

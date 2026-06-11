import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Components hardcode https://sui-intent.duckdns.org as their API base, so Vite proxy
// is no longer needed — Vite just serves the React app.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000
  }
})

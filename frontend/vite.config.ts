import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // The client filter imports ../backend/app/wordlist.txt so both sides share one list.
    fs: { allow: ['..'] },
    // RIVER_API_URL lets a second dev stack run beside the default one (e.g. API on another port).
    proxy: { '/api': process.env.RIVER_API_URL || 'http://127.0.0.1:8000' },
  },
})

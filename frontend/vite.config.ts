import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // The client filter imports ../backend/app/wordlist.txt so both sides share one list.
    fs: { allow: ['..'] },
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})

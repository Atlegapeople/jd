import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    allowedHosts: [
      'localhost',
      '127.0.0.1',
      '42a0-102-219-162-104.ngrok-free.app',
      '10ad-102-219-162-104.ngrok-free.app'
    ]
  }
})

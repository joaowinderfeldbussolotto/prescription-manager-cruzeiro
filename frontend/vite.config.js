import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Em dev local (`npm run dev`), o Vite faz proxy de /api pro backend, então
// o browser enxerga tudo na mesma origem e o cookie de sessão "só funciona".
// Em produção (Docker) quem faz esse proxy é o nginx (ver nginx.conf).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'
  return {
    plugins: [react()],
    server: {
      host: true,
      port: 5173,
      proxy: {
        '/api': { target, changeOrigin: true },
      },
    },
    preview: { host: true, port: 4173 },
  }
})

import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// `npm run dev` serves the UI with hot reload and forwards API/media requests to the
// Python backend (run `python3 app.py` alongside it, or set BACKEND).
const backend = process.env.BACKEND || 'http://127.0.0.1:8080'
const proxied = ['/api', '/t/', '/m/', '/d/', '/tt/', '/lock']

export default defineConfig({
  plugins: [svelte()],
  server: { host: true, proxy: Object.fromEntries(proxied.map((p) => [p, backend])) },
  build: { outDir: 'dist', emptyOutDir: true, target: 'es2020', chunkSizeWarningLimit: 300 },
})

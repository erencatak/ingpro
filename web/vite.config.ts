import fs from 'node:fs'
import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

const MIME: Record<string, string> = {
  '.mjs': 'text/javascript',
  '.js': 'text/javascript',
  '.wasm': 'application/wasm',
  '.onnx': 'application/octet-stream',
}

/**
 * onnxruntime-web dynamically import()s its .mjs loader from /vad/. In dev, Vite refuses to
 * transform files that live in public/ ("should only be referenced via HTML tags"), so serve
 * them raw, before Vite's own middleware runs. In production they are plain static files.
 */
function serveVadRaw(): Plugin {
  const dir = path.resolve(__dirname, 'public/vad')
  return {
    name: 'serve-vad-raw',
    configureServer(server) {
      server.middlewares.use('/vad', (req, res, next) => {
        const file = path.join(dir, decodeURIComponent((req.url ?? '').split('?')[0]))
        if (!file.startsWith(dir) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return next()
        res.setHeader('Content-Type', MIME[path.extname(file)] ?? 'application/octet-stream')
        res.setHeader('Cache-Control', 'no-cache')
        fs.createReadStream(file).pipe(res)
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), serveVadRaw()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8765',
      '/ws': { target: 'ws://127.0.0.1:8765', ws: true },
    },
  },
})

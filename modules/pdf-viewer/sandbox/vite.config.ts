import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '..', '..', '..', 'frontend', 'src'),
      '@modules': path.resolve(__dirname, '..', '..'),
      'pdfjs-dist': path.resolve(__dirname, 'node_modules', 'pdfjs-dist', 'build', 'pdf.mjs'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: Number(process.env.VITE_SANDBOX_PORT) || 5193,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:30004',
        changeOrigin: true,
      },
    },
  },
})

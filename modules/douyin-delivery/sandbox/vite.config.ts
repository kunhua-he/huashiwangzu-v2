import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

const sandboxNodeModules = path.resolve(__dirname, 'node_modules')

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@modules': path.resolve(__dirname, '..', '..'),
      'element-plus': path.resolve(sandboxNodeModules, 'element-plus'),
      'element-plus/es': path.resolve(sandboxNodeModules, 'element-plus/es'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: Number(process.env.VITE_SANDBOX_PORT) || 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:33000',
        changeOrigin: true,
      },
    },
  },
})

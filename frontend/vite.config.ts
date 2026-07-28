import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { cpSync, existsSync, mkdirSync } from 'fs'

// Vite plugin: copy Monaco Editor AMD files from node_modules to build output
// Monaco uses AMD format (require.js) - it cannot be bundled by Vite,
// so we copy the pre-built AMD files as static assets.
function monacoCopyPlugin(): Plugin {
  return {
    name: 'vite-plugin-monaco-copy',
    closeBundle() {
      const src = resolve(__dirname, 'node_modules/monaco-editor/min/vs')
      const dest = resolve(__dirname, 'dist/vs')
      if (!existsSync(src)) {
        console.warn('[monaco-copy] Source not found:', src)
        return
      }
      if (!existsSync(dest)) {
        mkdirSync(dest, { recursive: true })
      }
      cpSync(src, dest, { recursive: true, force: true })
      console.log('[monaco-copy] Copied Monaco AMD files to dist/vs/')
    }
  }
}

export default defineConfig({
  plugins: [vue(), monacoCopyPlugin()],
  test: {
    globals: true,
    environment: 'jsdom',
    coverage: {
      provider: 'v8'
    }
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    host: '0.0.0.0', // Listen on all network interfaces for LAN access
    port: 5173,
    allowedHosts: ['frp-oil.com', 'frp-few.com', 'frp-net.com'],
    proxy: {
      '/api': {
        target: 'http://localhost:8863',
        changeOrigin: true,
        configure: (proxy, options) => {
          proxy.on('proxyRes', (proxyRes, req, res) => {
            // Ensure binary responses are handled correctly
            if (proxyRes.headers['content-type'] && proxyRes.headers['content-type'].includes('application/pdf')) {
              // Don't modify response headers for PDF files
            }
          })
        }
      },
      '/ws': {
        target: 'ws://localhost:8863',
        ws: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true
      }
    },
    chunkSizeWarningLimit: 1000
  }
})

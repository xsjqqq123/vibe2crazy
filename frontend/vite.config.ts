import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// CDN package mapping: package name -> CDN URL
// IMPORTANT: Vue and its ecosystem libraries must NOT be externalized to CDN.
// The vue.esm-browser.prod.js CDN version is incompatible with Vite-bundled Vue components
// (like @guolao/vue-monaco-editor), causing DOM insertion errors (insertBefore null).
// Vue must be bundled by Vite to ensure proper reactivity and DOM lifecycle handling.
const CDN_PACKAGES: Record<string, string> = {
  // xterm (331KB) - Terminal rendering library, safe to externalize
  '@xterm/xterm': 'https://cdn.jsdelivr.net/npm/@xterm/xterm@6.0.0/+esm',
  '@xterm/addon-fit': 'https://cdn.jsdelivr.net/npm/@xterm/addon-fit@0.11.0/+esm',
  '@xterm/addon-webgl': 'https://cdn.jsdelivr.net/npm/@xterm/addon-webgl@0.19.0/+esm',
  // highlight.js (928KB) - Syntax highlighting, safe to externalize
  'highlight.js': 'https://cdn.jsdelivr.net/npm/highlight.js@11.11.1/+esm',
  // markdown (133KB) - Markdown parsing, safe to externalize
  'markdown-it': 'https://cdn.jsdelivr.net/npm/markdown-it@14.1.1/+esm',
  'marked': 'https://cdn.jsdelivr.net/npm/marked@17.0.5/+esm',
}

// CSS files to load from CDN (only in production)
const CDN_CSS = [
  'https://cdn.jsdelivr.net/npm/@xterm/xterm@6.0.0/css/xterm.css',
  'https://cdn.jsdelivr.net/npm/splitpanes@4.0.4/dist/splitpanes.css',
  'https://cdn.jsdelivr.net/npm/highlight.js@11.11.1/styles/atom-one-dark.min.css',
]

// Vite plugin: inject importmap + CSS links into HTML (production only)
function cdnPlugin(): Plugin {
  const externalIds = Object.keys(CDN_PACKAGES)

  return {
    name: 'vite-plugin-cdn',

    // Inject importmap and CSS links into index.html during production build
    transformIndexHtml(html: string, ctx: string) {
      // Only inject in production build (ctx is the bundle when building)
      // @ts-ignore - bundle exists during build
      if (!ctx?.bundle) return html

      const importMap: Record<string, string> = { ...CDN_PACKAGES }

      const importMapTag = `    <script>window.process = window.process || { env: { NODE_ENV: 'production' } };</script>
    <script type="importmap">${JSON.stringify({ imports: importMap }, null, 2)}</script>`
      const cssLinks = CDN_CSS.map(url => `    <link rel="stylesheet" href="${url}">`).join('\n')

      // Inject BEFORE closing head tag, but before Vite's module script
      // Insert right before </head> so process shim runs first
      return html.replace(
        '</head>',
        `${importMapTag}\n${cssLinks}\n  </head>`
      )
    },

    // Mark packages as external during build
    config(config, { command }) {
      if (command === 'build') {
        const rollupOptions = config.build?.rollupOptions || {}
        rollupOptions.external = (id: string) => {
          // Don't externalize CSS files - let Vite handle them
          if (id.endsWith('.css')) return false
          return externalIds.some(pkg => id === pkg || id.startsWith(pkg + '/'))
        }
        if (!config.build) config.build = {}
        config.build.rollupOptions = rollupOptions
      }
    }
  }
}

export default defineConfig({
  plugins: [vue(), cdnPlugin()],
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
    // manualChunks removed - major libs loaded from CDN
    chunkSizeWarningLimit: 1000
  }
})

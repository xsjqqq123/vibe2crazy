// frontend/src/main.ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import { initApiClient, startLanDetection } from './api/client'
import { loader } from '@guolao/vue-monaco-editor'
// wsNetworkManager auto-initializes when imported, listening to networkDetector
import './utils/wsNetworkManager'
import './assets/styles/main.css'
import 'splitpanes/dist/splitpanes.css'
import 'highlight.js/styles/atom-one-dark.css'

// Configure Monaco to load from local AMD files (served from public/vs/ in dev,
// copied to dist/vs/ during build by monacoCopyPlugin)
loader.config({
  paths: {
    vs: '/vs'
  }
})

async function bootstrap() {
  try {
    // Initialize API client with network detection
    await initApiClient()
    // Start periodic LAN detection (every 5 minutes)
    startLanDetection(5 * 60 * 1000)

    // wsNetworkManager is auto-initialized in its constructor
    console.log('[Bootstrap] wsNetworkManager initialized')
  } catch (error) {
    console.error('[Bootstrap] Initialization failed:', error)
    // Continue with app mount even if init fails
  }

  const app = createApp(App)
  app.use(createPinia())
  app.use(router)

  app.mount('#app')
}

bootstrap().catch(error => {
  console.error('[Bootstrap] Fatal error:', error)
})
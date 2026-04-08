// frontend/src/main.ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import { initApiClient, startLanDetection } from './api/client'
import './assets/styles/main.css'
import 'splitpanes/dist/splitpanes.css'
import 'highlight.js/styles/atom-one-dark.css'

async function bootstrap() {
  // Initialize API client with network detection
  await initApiClient()

  // Start periodic LAN detection (every 5 minutes)
  startLanDetection(5 * 60 * 1000)

  const app = createApp(App)
  app.use(createPinia())
  app.use(router)

  app.mount('#app')
}

bootstrap()
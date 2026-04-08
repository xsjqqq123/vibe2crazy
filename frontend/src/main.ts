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
  try {
    await initApiClient()
    startLanDetection(5 * 60 * 1000)
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
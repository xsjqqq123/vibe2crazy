import { ref, type Ref } from 'vue'
import { useRouter } from 'vue-router'

export interface ErrorHandlerOptions {
  on401?: () => void
  on403?: () => void
}

export interface ErrorHandlerReturn {
  error: Ref<string | null>
  handle401: () => void
  handle403: () => void
  clearError: () => void
}

export function useErrorHandler(options: ErrorHandlerOptions): ErrorHandlerReturn {
  const router = useRouter()
  const error = ref<string | null>(null)

  const handle401 = () => {
    console.log('[Auth Error] 401 Unauthorized - clearing token and redirecting to login')

    // Clear invalid token
    localStorage.removeItem('auth_token')

    // Trigger callback
    options.on401?.()

    // Or redirect manually
    router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
  }

  const handle403 = () => {
    console.log('[Auth Error] 403 Forbidden - triggering handler')
    options.on403?.()
  }

  // Expose error state and handlers
  return {
    error,
    handle401,
    handle403,
    clearError: () => { error.value = null }
  }
}

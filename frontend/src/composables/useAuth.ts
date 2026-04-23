import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import authApi from '@/api/auth'

const token = ref<string | null>(null)
const isAuthenticated = computed(() => !!token.value)

export function useAuth() {
  const router = useRouter()

  // Load token from localStorage on init
  if (!token.value && typeof localStorage !== 'undefined') {
    token.value = localStorage.getItem('auth_token')
  }

  const login = async (password: string) => {
    try {
      const response = await authApi.login(password)
      token.value = response.token
      localStorage.setItem('auth_token', response.token)

      // Redirect to projects or saved redirect
      const redirect = router.currentRoute.value.query.redirect as string
      router.push(redirect || '/projects')
      return { success: true }
    } catch (error: any) {
      return { success: false, error: error.message || 'Login failed' }
    }
  }

  const logout = async () => {
    try {
      await authApi.logout()
    } catch {
      // Ignore logout errors
    }
    token.value = null
    localStorage.removeItem('auth_token')
    router.push('/login')
  }

  const checkAuth = async () => {
    if (!token.value) return false
    try {
      const session = await authApi.getMe()
      return session.authenticated
    } catch {
      token.value = null
      localStorage.removeItem('auth_token')
      return false
    }
  }

  return {
    isAuthenticated,
    token,
    login,
    logout,
    checkAuth
  }
}

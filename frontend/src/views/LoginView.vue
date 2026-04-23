<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuth } from '@/composables/useAuth'
import authApi from '@/api/auth'

const { login } = useAuth()

const password = ref('')
const loading = ref(false)
const error = ref('')

const handleLogin = async () => {
  if (!password.value) {
    error.value = 'Please enter a password'
    return
  }

  loading.value = true
  error.value = ''

  const result = await login(password.value)

  if (!result.success) {
    error.value = result.error || 'Login failed'
    password.value = ''
  }

  loading.value = false
}

onMounted(async () => {
  try {
    const status = await authApi.getPasswordStatus()
    if (!status.is_set) {
      window.location.href = '/change-password'
    }
  } catch {
    // Ignore - proceed with login page
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-sub px-4">
    <div class="max-w-md w-full">
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-main mb-2">Vibe2Crazy</h1>
        <p class="text-sub">Remote Code Editing Tool</p>
      </div>

      <div class="card">
        <form @submit.prevent="handleLogin" class="space-y-4">
          <div>
            <label for="password" class="block text-sm font-medium text-sub mb-2">
              Password
            </label>
            <input
              id="password"
              v-model="password"
              type="password"
              class="input w-full"
              placeholder="Enter password"
              autofocus
              @keyup.enter="handleLogin"
            />
          </div>

          <div v-if="error" class="text-red-600 text-sm">
            {{ error }}
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="btn btn-primary w-full flex items-center justify-center"
          >
            <span v-if="loading" class="spinner mr-2"></span>
            {{ loading ? 'Logging in...' : 'Login' }}
          </button>
        </form>
      </div>

      <p class="text-center text-sm text-muted mt-4">
          <a href="/change-password" class="text-blue-500 hover:underline">Change Password</a>
        </p>
    </div>
  </div>
</template>

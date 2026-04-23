<script setup lang="ts">
import { ref, onMounted } from 'vue'
import authApi from '@/api/auth'

const newPassword = ref('')
const confirmPassword = ref('')
const oldPassword = ref('')
const loading = ref(false)
const error = ref('')
const success = ref(false)
const isInitialSetup = ref(false)

const handleChangePassword = async () => {
  if (!newPassword.value) {
    error.value = 'Please enter a new password'
    return
  }

  if (newPassword.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }

  if (newPassword.value.length < 4) {
    error.value = 'Password must be at least 4 characters'
    return
  }

  loading.value = true
  error.value = ''

  try {
    const result = await authApi.changePassword(
      newPassword.value,
      isInitialSetup.value ? undefined : oldPassword.value
    )
    if (result.success) {
      success.value = true
      setTimeout(() => {
        window.location.href = '/login'
      }, 2000)
    }
  } catch (err: any) {
    error.value = err.message || 'Failed to change password'
  }

  loading.value = false
}

onMounted(async () => {
  try {
    const status = await authApi.getPasswordStatus()
    isInitialSetup.value = !status.is_set
  } catch {
    // Continue anyway if check fails
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
        <!-- Warning banner -->
        <div class="mb-6 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
          <div class="flex items-start gap-2">
            <svg class="w-5 h-5 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
            <div>
              <p class="text-sm font-medium text-amber-800 dark:text-amber-300">
                {{ isInitialSetup ? 'Setup Required' : 'Change Password' }}
              </p>
              <p class="text-xs text-amber-700 dark:text-amber-400 mt-1">
                {{ isInitialSetup
                  ? 'No password is set. Please create your initial password to continue.'
                  : 'Please enter your current password and a new password.'
                }}
              </p>
            </div>
          </div>
        </div>

        <!-- Success message -->
        <div v-if="success" class="text-center py-4">
          <svg class="w-12 h-12 text-green-500 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
          <p class="text-main font-medium">Password changed successfully!</p>
          <p class="text-sub text-sm mt-1">Redirecting to login...</p>
        </div>

        <!-- Password form -->
        <form v-else @submit.prevent="handleChangePassword" class="space-y-4">
          <!-- Old password field (only shown when not initial setup) -->
          <div v-if="!isInitialSetup">
            <label for="old-password" class="block text-sm font-medium text-sub mb-2">
              Current Password
            </label>
            <input
              id="old-password"
              v-model="oldPassword"
              type="password"
              class="input w-full"
              placeholder="Enter current password"
              autofocus
            />
          </div>

          <div>
            <label for="new-password" class="block text-sm font-medium text-sub mb-2">
              New Password
            </label>
            <input
              id="new-password"
              v-model="newPassword"
              type="password"
              class="input w-full"
              :placeholder="isInitialSetup ? 'Create your password' : 'Enter new password'"
              :autofocus="isInitialSetup"
            />
          </div>

          <div>
            <label for="confirm-password" class="block text-sm font-medium text-sub mb-2">
              Confirm Password
            </label>
            <input
              id="confirm-password"
              v-model="confirmPassword"
              type="password"
              class="input w-full"
              placeholder="Confirm new password"
            />
          </div>

          <div v-if="error" class="text-red-600 dark:text-red-400 text-sm">
            {{ error }}
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="btn btn-primary w-full flex items-center justify-center"
          >
            <span v-if="loading" class="spinner mr-2"></span>
            {{ loading ? 'Processing...' : (isInitialSetup ? 'Set Password' : 'Change Password') }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>
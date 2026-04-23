<script setup lang="ts">
import { ref, computed } from 'vue'
import { useTunnel } from '@/composables/useTunnel'

const {
  status,
  remoteUrl,
  token,
  serverUrl,
  lastError,
  loading,
  saveToken,
  start,
  stop,
  copyRemoteUrl
} = useTunnel()

const newToken = ref('')
const showConfig = ref(false)
const saveSuccess = ref(false)

const isConnected = computed(() => status.value === 'connected')
const isConnecting = computed(() => status.value === 'connecting')

const statusColor = computed(() => {
  if (isConnected.value) return 'bg-green-500'
  if (isConnecting.value) return 'bg-yellow-500'
  return 'bg-red-500'
})

const statusText = computed(() => {
  if (isConnected.value) return 'Connected'
  if (isConnecting.value) return 'Connecting...'
  return 'Disconnected'
})

const openConfig = () => {
  newToken.value = token.value || ''
  showConfig.value = true
}

const handleSaveAndStart = async () => {
  const result = await saveToken(newToken.value.trim())
  if (result.success) {
    if (newToken.value.trim()) {
      await start()
    }
    newToken.value = ''
    showConfig.value = false
  }
}

const handleSaveToken = async () => {
  const result = await saveToken(newToken.value.trim())
  if (result.success) {
    if (newToken.value.trim()) {
      saveSuccess.value = true
      // Backend will auto-restart after 2 seconds
      // Close form after 5 seconds to allow restart to complete
      setTimeout(() => {
        saveSuccess.value = false
        showConfig.value = false
        newToken.value = ''
      }, 5000)
    } else {
      showConfig.value = false
    }
  }
}

const handleStop = async () => {
  await stop()
}

const handleCopyUrl = async () => {
  await copyRemoteUrl()
}
</script>

<template>
  <div class="tunnel-panel mb-4 p-4 border rounded-lg bg-main border-main">
    <!-- Header row -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2">
          <div :class="statusColor" class="w-3 h-3 rounded-full"></div>
          <span class="text-sm font-medium text-main">Remote Access</span>
          <span class="text-xs text-sub">({{ statusText }})</span>
        </div>
        <a
          v-if="serverUrl"
          :href="serverUrl"
          target="_blank"
          class="text-sm text-primary hover:underline"
        >
          Get token
        </a>
      </div>

      <!-- Remote URL when connected -->
      <div v-if="isConnected && remoteUrl" class="flex items-center gap-2 text-sm">
        <span class="text-muted">URL:</span>
        <a :href="remoteUrl" target="_blank" class="link text-primary">{{ remoteUrl }}</a>
        <button @click="handleCopyUrl" class="p-1 hover:bg-sub rounded" title="Copy URL">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
        </button>
        <button
          @click="openConfig"
          class="text-sm text-primary hover:underline"
        >
          Edit
        </button>
      </div>

      <!-- Configure button when disconnected -->
      <button
        v-if="!isConnected && !showConfig"
        @click="openConfig"
        class="text-sm text-primary hover:underline"
      >
        Configure
      </button>
    </div>

    <!-- Config form -->
    <div v-if="showConfig" class="mt-4 space-y-3">
      <!-- Success message -->
      <div v-if="saveSuccess" class="text-sm text-green-500 mb-2">
        ✓ Saved, reconnecting...
      </div>

      <div>
        <label class="block text-sm text-muted mb-1">Tunnel Token</label>
        <input
          v-model="newToken"
          type="text"
          placeholder="Enter token from server"
          class="input w-full text-sm"
          :disabled="loading"
        />
      </div>

      <div class="flex gap-2">
        <button
          v-if="!isConnected"
          @click="handleSaveAndStart"
          :disabled="loading"
          class="btn btn-primary text-sm"
        >
          <span v-if="loading" class="spinner mr-2"></span>
          Save
        </button>
        <button
          v-if="isConnected"
          @click="handleSaveToken"
          :disabled="loading || saveSuccess"
          class="btn btn-primary text-sm"
        >
          <span v-if="loading" class="spinner mr-2"></span>
          {{ saveSuccess ? 'Reconnecting...' : 'Save' }}
        </button>
        <button
          v-if="isConnected && !showConfig"
          @click="handleStop"
          :disabled="loading"
          class="btn btn-secondary text-sm"
        >
          Stop
        </button>
        <button
          v-if="showConfig && !saveSuccess"
          @click="showConfig = false"
          class="btn btn-secondary text-sm"
        >
          Cancel
        </button>
      </div>
    </div>

    <!-- Error message -->
    <div v-if="lastError" class="mt-3 text-sm text-red-500">
      {{ lastError }}
    </div>
  </div>
</template>
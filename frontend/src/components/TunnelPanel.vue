<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import QRCode from 'qrcode'
import { useTunnel } from '@/composables/useTunnel'

const {
  status,
  remoteUrl,
  token,
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
const qrCodeVisible = ref(false)
const qrDataUrl = ref('')

// Generate QR code when remoteUrl changes
watch(remoteUrl, async (url) => {
  console.log('[QR] remoteUrl changed:', url)
  if (url) {
    try {
      const dataUrl = await QRCode.toDataURL(url, {
        width: 150,
        margin: 2,
        color: {
          dark: '#000000',
          light: '#ffffff'
        }
      })
      qrDataUrl.value = dataUrl
      console.log('[QR] Generated QR dataUrl, length:', dataUrl.length)
    } catch (e) {
      console.error('[QR] QR code generation failed:', e)
    }
  } else {
    qrDataUrl.value = ''
    console.log('[QR] No URL, cleared qrDataUrl')
  }
}, { immediate: true })

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

const showQrCode = () => {
  console.log('[QR] showQrCode called, remoteUrl:', remoteUrl.value, 'qrDataUrl:', qrDataUrl.value?.length)
  if (remoteUrl.value && qrDataUrl.value) {
    qrCodeVisible.value = true
    console.log('[QR] qrCodeVisible set to true')
  } else {
    console.log('[QR] conditions not met, qrCodeVisible stays false')
  }
}

const hideQrCode = () => {
  qrCodeVisible.value = false
}
</script>

<template>
  <div class="tunnel-panel mb-4 p-4 border rounded-lg bg-main border-main">
    <!-- Header row: responsive layout -->
  <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
    <!-- Status info -->
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-2">
        <div :class="statusColor" class="w-3 h-3 rounded-full"></div>
        <span class="text-sm font-medium text-main">Remote Access</span>
        <span class="text-xs text-sub">({{ statusText }})</span>
      </div>
      <a
        href="https://vibe2crazy.com/login"
        target="_blank"
        class="text-sm text-primary hover:underline"
      >
        Get token
      </a>
    </div>

    <!-- Remote URL when connected -->
    <div v-if="isConnected && remoteUrl" class="flex items-center gap-2 text-sm relative">
      <span class="text-muted">URL:</span>
      <a
        :href="remoteUrl"
        target="_blank"
        class="link text-primary truncate max-w-[200px] sm:max-w-none"
        @mouseenter="showQrCode"
        @mouseleave="hideQrCode"
      >
        {{ remoteUrl }}
      </a>
      <!-- QR Code Tooltip (outside truncate element) -->
      <div
        v-if="qrCodeVisible && qrDataUrl"
        class="absolute top-full left-8 mt-2 p-3 rounded-lg shadow-lg z-50"
        style="background-color: var(--bg-primary); border: 1px solid var(--border-color);"
      >
        <img :src="qrDataUrl" class="w-[150px] h-[150px]" alt="QR Code" />
        <p class="text-xs text-muted mt-2 text-center">Scan to visit</p>
      </div>
      <button @click="handleCopyUrl" class="p-1 hover:bg-sub rounded shrink-0" title="Copy URL">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      </button>
      <button
        @click="openConfig"
        class="text-sm text-primary hover:underline shrink-0"
      >
        Edit
      </button>
    </div>

    <!-- Configure button when disconnected -->
    <button
      v-if="!isConnected && !showConfig"
      @click="openConfig"
      class="text-sm text-primary hover:underline sm:ml-auto"
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
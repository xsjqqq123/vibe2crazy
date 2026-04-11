import { ref, onMounted, onUnmounted } from 'vue'
import tunnelApi, { TunnelStatus } from '@/api/tunnel'
import { isLanMode } from '@/api/client'

export function useTunnel() {
  const status = ref<string>('disabled')
  const remoteUrl = ref<string | null>(null)
  const token = ref<string>('')
  const lastError = ref<string | null>(null)
  const serverUrl = ref<string | null>(null)
  const loading = ref(false)

  let pollInterval: ReturnType<typeof setInterval> | null = null

  const fetchStatus = async () => {
    if (!isLanMode()) return  // 非局域网跳过本次轮询
    try {
      const data: TunnelStatus = await tunnelApi.getStatus()
      status.value = data.status
      remoteUrl.value = data.remote_url
      token.value = data.token || ''
      lastError.value = data.last_error
      serverUrl.value = data.server_url
    } catch (err) {
      console.error('Failed to fetch tunnel status:', err)
    }
  }

  const startPolling = (intervalMs: number = 5000) => {
    if (pollInterval) return
    pollInterval = setInterval(fetchStatus, intervalMs)
  }

  const stopPolling = () => {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }

  const saveToken = async (newToken: string, useTls: boolean = true, verifyTls: boolean = false) => {
    loading.value = true
    try {
      await tunnelApi.saveConfig({
        token: newToken,
        use_tls: useTls,
        verify_tls: verifyTls
      })
      token.value = newToken
      await fetchStatus()
      return { success: true }
    } catch (err: any) {
      return { success: false, error: err.message || 'Failed to save token' }
    } finally {
      loading.value = false
    }
  }

  const start = async () => {
    loading.value = true
    try {
      await tunnelApi.start()
      await fetchStatus()
      return { success: true }
    } catch (err: any) {
      return { success: false, error: err.message || 'Failed to start tunnel' }
    } finally {
      loading.value = false
    }
  }

  const stop = async () => {
    loading.value = true
    try {
      await tunnelApi.stop()
      await fetchStatus()
      return { success: true }
    } catch (err: any) {
      return { success: false, error: err.message || 'Failed to stop tunnel' }
    } finally {
      loading.value = false
    }
  }

  const copyRemoteUrl = async () => {
    if (!remoteUrl.value) return { success: false }
    try {
      await navigator.clipboard.writeText(remoteUrl.value)
      return { success: true }
    } catch (err) {
      return { success: false }
    }
  }

  onMounted(() => {
    fetchStatus()
    startPolling()
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    status,
    remoteUrl,
    token,
    lastError,
    serverUrl,
    loading,
    fetchStatus,
    saveToken,
    start,
    stop,
    copyRemoteUrl
  }
}
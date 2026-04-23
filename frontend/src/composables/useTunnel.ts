import { ref, onMounted, onUnmounted } from 'vue'
import tunnelApi, { TunnelStatus } from '@/api/tunnel'

const POLL_DURATION = 30000 // 30秒后停止轮询

export function useTunnel() {
  const status = ref<string>('disabled')
  const remoteUrl = ref<string | null>(null)
  const token = ref<string>('')
  const lastError = ref<string | null>(null)
  const serverUrl = ref<string | null>(null)
  const loading = ref(false)

  let pollInterval: ReturnType<typeof setInterval> | null = null
  let stopTimer: ReturnType<typeof setTimeout> | null = null

  const fetchStatus = async () => {
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

  const clearTimers = () => {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
    if (stopTimer) {
      clearTimeout(stopTimer)
      stopTimer = null
    }
  }

  const startPolling = (intervalMs: number = 5000) => {
    clearTimers()
    fetchStatus() // 立即获取一次
    pollInterval = setInterval(fetchStatus, intervalMs)
    // 30秒后自动停止
    stopTimer = setTimeout(() => {
      if (pollInterval) {
        clearInterval(pollInterval)
        pollInterval = null
      }
    }, POLL_DURATION)
  }

  const stopPolling = () => {
    clearTimers()
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
      startPolling() // 保存后重新开始轮询
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
      startPolling() // 启动后重新开始轮询
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
      startPolling() // 停止后重新开始轮询以更新状态
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
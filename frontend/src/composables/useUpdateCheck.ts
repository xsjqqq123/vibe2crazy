// vibe2crazy/frontend/src/composables/useUpdateCheck.ts
import { ref, computed } from 'vue'

interface VersionInfo {
  version: string
  title: string
  description: string
  published_at: string
  downloads: DownloadInfo[]
}

interface DownloadInfo {
  id: string
  platform: string
  download_url: string
  file_size: number | null
  file_hash: string | null
}

interface AppConfig {
  current_version: string
  update_server_url: string
}

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000

// Global state (singleton pattern)
const latestVersionInfo = ref<VersionInfo | null>(null)
const currentVersion = ref<string>('1.0.0')
const updateServerUrl = ref<string>('')
const loading = ref(false)

export function useUpdateCheck() {
  const hasUpdate = computed(() => {
    if (!latestVersionInfo.value) return false
    return isNewerVersion(currentVersion.value, latestVersionInfo.value.version)
  })

  // Initialize: load config and cached data
  async function init() {
    try {
      // Load application config
      const configRes = await fetch('/api/config')
      if (configRes.ok) {
        const config: AppConfig = await configRes.json()
        currentVersion.value = config.current_version
        updateServerUrl.value = config.update_server_url
      }

      // Load cached version info
      const cached = localStorage.getItem('latestVersionInfo')
      if (cached) {
        latestVersionInfo.value = JSON.parse(cached)
      }
    } catch (e) {
      console.error('[UpdateCheck] Init failed:', e)
    }
  }

  // Check for updates
  async function checkForUpdates(force = false): Promise<VersionInfo | null> {
    if (!updateServerUrl.value) {
      console.log('[UpdateCheck] No update server URL configured')
      return null
    }

    const lastCheck = localStorage.getItem('lastUpdateCheck')
    const now = Date.now()

    // Non-force check: check if 7 days have passed
    if (!force && lastCheck && now - parseInt(lastCheck) < SEVEN_DAYS_MS) {
      console.log('[UpdateCheck] Not due for check yet')
      return null
    }

    if (loading.value) return null
    loading.value = true

    try {
      const response = await fetch(`${updateServerUrl.value}/api/versions/latest`, {
        signal: AbortSignal.timeout(5000) // 5 second timeout
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data: VersionInfo = await response.json()

      // Update cache
      localStorage.setItem('lastUpdateCheck', now.toString())
      localStorage.setItem('latestVersionInfo', JSON.stringify(data))
      latestVersionInfo.value = data

      return data
    } catch (e) {
      console.error('[UpdateCheck] Check failed:', e)
      return null
    } finally {
      loading.value = false
    }
  }

  // Semantic version comparison
  function isNewerVersion(local: string, remote: string): boolean {
    const localParts = local.split('.').map(Number)
    const remoteParts = remote.split('.').map(Number)

    for (let i = 0; i < 3; i++) {
      const localVal = localParts[i] || 0
      const remoteVal = remoteParts[i] || 0
      if (remoteVal > localVal) return true
      if (remoteVal < localVal) return false
    }
    return false
  }

  // Get current platform
  function getCurrentPlatform(): string {
    const platform = navigator.platform.toLowerCase()
    const isAppleSilicon = navigator.userAgent.includes('Mac') &&
      (navigator.userAgent.includes('ARM') || 'Apple' in navigator)

    if (platform.includes('win')) {
      return 'windows-x64'
    } else if (platform.includes('mac')) {
      return isAppleSilicon ? 'macos-arm64' : 'macos-x64'
    } else if (platform.includes('linux')) {
      // Detect architecture
      return 'linux-x64' // Default x64
    }
    return 'linux-x64' // Default
  }

  // Get download info for current platform
  function getCurrentPlatformDownload(): DownloadInfo | null {
    if (!latestVersionInfo.value) return null
    const platform = getCurrentPlatform()
    return latestVersionInfo.value.downloads.find(d => d.platform === platform) || null
  }

  return {
    latestVersionInfo,
    currentVersion,
    hasUpdate,
    loading,
    init,
    checkForUpdates,
    getCurrentPlatform,
    getCurrentPlatformDownload,
    isNewerVersion
  }
}
// frontend/src/api/client.ts
/**
 * Dynamic API client with LAN auto-switching support.
 *
 * This module provides:
 * - Dynamic API_BASE switching between LAN and public addresses
 * - Automatic fallback to public address when LAN fails
 * - NetworkDetector integration for seamless switching
 */

import { networkDetector, isNetworkError } from '../utils/networkDetector'
import type { AddressType } from '../types/network'

// Track initialization state
let initialized = false

// Error handlers that use window.location instead of router
const handle401 = () => {
  console.log('[HTTP Client] 401 Unauthorized - clearing token and redirecting to login')
  localStorage.removeItem('auth_token')
  const currentPath = window.location.pathname + window.location.search
  window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`
}

const handle403 = () => {
  console.log('[HTTP Client] 403 Forbidden')
}

/**
 * Get current API base URL from network detector
 */
function getApiBase(): string {
  return networkDetector.getCurrentBase()
}

/**
 * Initialize network detector
 */
export async function initApiClient(): Promise<void> {
  if (initialized) return

  // Set up callback for base URL changes
  networkDetector.setOnBaseChange((base: string, type: AddressType) => {
    console.log(`[HTTP Client] API base changed to ${type}: ${base}`)
  })

  // Initialize detector (may switch to LAN if available)
  await networkDetector.init()

  initialized = true
  console.log('[HTTP Client] Initialized, current base:', getApiBase())
}

/**
 * Start periodic LAN detection
 */
export function startLanDetection(intervalMs?: number): void {
  networkDetector.startPeriodicCheck(intervalMs)
}

/**
 * Stop periodic LAN detection
 */
export function stopLanDetection(): void {
  networkDetector.stopPeriodicCheck()
}

/**
 * Check if currently using LAN address
 */
export function isLanMode(): boolean {
  return networkDetector.getCurrentType() === 'lan'
}

/**
 * Force switch to public address
 */
export function forcePublicMode(): void {
  networkDetector.forcePublic()
}

/**
 * Core request function with automatic fallback
 */
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('auth_token')

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {})
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const base = getApiBase()
  const url = `${base}${endpoint}`

  try {
    const response = await fetch(url, {
      ...options,
      headers
    })

    // Check for auth errors before throwing
    if (response.status === 401) {
      handle401()
      throw new Error('Unauthorized')
    }

    if (response.status === 403) {
      handle403()
      throw new Error('Forbidden')
    }

    // Handle 204 No Content responses
    if (response.status === 204) {
      return undefined as T
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(error.detail || error.message || 'Request failed')
    }

    const data = await response.json()
    console.log('[API Client] Response from', endpoint, ':', data)
    return data
  } catch (error) {
    // Network error with LAN mode: fallback to public and retry
    if (isNetworkError(error) && isLanMode()) {
      console.log('[API Client] Network error in LAN mode, falling back to public')
      networkDetector.onRequestFailure()

      // Retry with public address
      const publicUrl = `${networkDetector.getPublicBase()}${endpoint}`
      const response = await fetch(publicUrl, {
        ...options,
        headers
      })

      if (response.status === 401) {
        handle401()
        throw new Error('Unauthorized')
      }

      if (response.status === 403) {
        handle403()
        throw new Error('Forbidden')
      }

      if (response.status === 204) {
        return undefined as T
      }

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }))
        throw new Error(error.detail || error.message || 'Request failed')
      }

      return await response.json()
    }

    throw error
  }
}

export default request

/**
 * Request blob data
 */
async function requestBlob(
  endpoint: string,
  options: RequestInit = {}
): Promise<Blob> {
  const token = localStorage.getItem('auth_token')

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {})
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const base = getApiBase()
  const response = await fetch(`${base}${endpoint}`, {
    ...options,
    headers
  })

  if (response.status === 401) {
    handle401()
    throw new Error('Unauthorized')
  }

  if (response.status === 403) {
    handle403()
    throw new Error('Forbidden')
  }

  if (response.status === 204) {
    return new Blob()
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || error.message || 'Request failed')
  }

  return await response.blob()
}

interface BlobProgress {
  loaded: number
  total: number
}

async function requestBlobWithProgress(
  endpoint: string,
  onProgress: (progress: BlobProgress) => void,
  options: RequestInit = {}
): Promise<Blob> {
  const token = localStorage.getItem('auth_token')

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {})
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const base = getApiBase()
  const response = await fetch(`${base}${endpoint}`, {
    ...options,
    headers
  })

  if (response.status === 401) {
    handle401()
    throw new Error('Unauthorized')
  }

  if (response.status === 403) {
    handle403()
    throw new Error('Forbidden')
  }

  if (response.status === 204) {
    return new Blob()
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || error.message || 'Request failed')
  }

  const contentLength = response.headers.get('content-length')
  const total = contentLength ? parseInt(contentLength, 10) : 0

  const contentType = response.headers.get('content-type') || 'application/octet-stream'

  const reader = response.body?.getReader()
  if (!reader) {
    return await response.blob()
  }

  const chunks: Uint8Array[] = []
  let loaded = 0

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      chunks.push(value)
      loaded += value.length
      onProgress({ loaded, total })
    }
  } finally {
    reader.releaseLock()
  }

  return new Blob(chunks, { type: contentType })
}

export { requestBlob, requestBlobWithProgress }
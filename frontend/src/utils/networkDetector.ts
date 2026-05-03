// frontend/src/utils/networkDetector.ts
/**
 * Network detector for LAN auto-switching.
 *
 * Detects if the backend is accessible via LAN and automatically switches
 * to use LAN connection to reduce server load and improve response time.
 */

import type {
  LocalInfoResponse,
  LanDetectorStorage,
  ProbeResult,
  NetworkDetectorConfig,
  AddressType
} from '../types/network'
import { DEFAULT_CONFIG } from '../types/network'

const STORAGE_KEY = 'lan_detector'

class NetworkDetector {
  private config: NetworkDetectorConfig
  private currentBase: string
  private currentType: AddressType
  private publicBase: string
  private checkTimer: ReturnType<typeof setInterval> | null = null
  private onBaseChange: ((base: string, type: AddressType) => void) | null = null

  constructor() {
    this.config = { ...DEFAULT_CONFIG }
    this.currentBase = this.getInitialApiBase()
    this.currentType = 'public'
    this.publicBase = this.currentBase
    this.loadStorage()
  }

  private getInitialApiBase(): string {
    // Same logic as original getApiBase() in client.ts
    if (import.meta.env.DEV) {
      return '/api'
    }

    const envApiBase = import.meta.env.VITE_API_BASE
    if (envApiBase && envApiBase !== '/api') {
      return envApiBase
    }

    const protocol = window.location.protocol
    const host = window.location.hostname
    const port = window.location.port

    if (port === '8864') {
      return `http://${host}:8863/api`
    }

    return `${protocol}//${host}${port ? ':' + port : ''}/api`
  }

  private loadStorage(): void {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const data: LanDetectorStorage = JSON.parse(stored)
        if (data.preferred_base && data.public_base) {
          this.publicBase = data.public_base
        }
      }
    } catch (e) {
      console.warn('[NetworkDetector] Failed to load storage:', e)
    }
  }

  private saveStorage(): void {
    const data: LanDetectorStorage = {
      preferred_base: this.currentType === 'lan' ? this.currentBase : null,
      public_base: this.publicBase,
      last_check: Date.now()
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  }

  /**
   * Set callback for base URL changes
   */
  setOnBaseChange(callback: (base: string, type: AddressType) => void): void {
    this.onBaseChange = callback
  }

  /**
   * Get current API base URL
   */
  getCurrentBase(): string {
    return this.currentBase
  }

  /**
   * Get current address type
   */
  getCurrentType(): AddressType {
    return this.currentType
  }

  /**
   * Get public base URL
   */
  getPublicBase(): string {
    return this.publicBase
  }

  /**
   * Initialize detector - check cached LAN address or use public
   */
  async init(): Promise<void> {
    if (!this.config.enabled) {
      console.log('[NetworkDetector] Disabled, using public base')
      return
    }

    // Try cached LAN address first
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      try {
        const data: LanDetectorStorage = JSON.parse(stored)
        if (data.preferred_base) {
          console.log('[NetworkDetector] Testing cached LAN address:', data.preferred_base)
          const valid = await this.verifyAddress(data.preferred_base)
          if (valid) {
            this.switchToLan(data.preferred_base)
            console.log('[NetworkDetector] Using cached LAN address')
            return
          } else {
            console.log('[NetworkDetector] Cached LAN address invalid, using public')
          }
        }
      } catch (e) {
        console.warn('[NetworkDetector] Failed to parse cached address:', e)
      }
    }

    // Use public base, then run background detection
    this.switchToPublic()

    // Run detection in background (don't await)
    this.detect().then(lanBase => {
      if (lanBase) {
        console.log('[NetworkDetector] Found LAN address in background:', lanBase)
        this.switchToLan(lanBase)
      }
    })
  }

  /**
   * Verify an address is reachable and has matching token_hash
   */
  private async verifyAddress(base: string): Promise<boolean> {
    try {
      // Get expected hash from public endpoint
      const expectedHash = await this.fetchTokenHash(this.publicBase)
      if (!expectedHash) return false

      // Get actual hash from target address
      const actualHash = await this.fetchTokenHash(base)
      return actualHash === expectedHash
    } catch {
      return false
    }
  }

  /**
   * Fetch token_hash from an endpoint
   */
  private async fetchTokenHash(base: string): Promise<string | null> {
    try {
      const url = `${base}/tunnel/token_hash`
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), this.config.probeTimeout)

      const response = await fetch(url, {
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json' }
      })
      clearTimeout(timeoutId)

      if (!response.ok) return null

      const data = await response.json()
      return data.token_hash
    } catch {
      return null
    }
  }

  /**
   * Probe a specific IP address
   */
  private async probeAddress(
    ip: string,
    port: number,
    expectedHash: string
  ): Promise<ProbeResult> {
    // Use the same protocol as the page.
    // Note: from an HTTPS page, the browser blocks HTTP (Mixed Content)
    // AND rejects untrusted certs (self-signed). Users must trust the
    // self-signed cert first by visiting https://ip:port directly.
    const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:'
    const url = `${protocol}//${ip}:${port}/api/tunnel/token_hash`

    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), this.config.probeTimeout)

      const response = await fetch(url, {
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json' }
      })
      clearTimeout(timeoutId)

      if (!response.ok) {
        return { ip, port, matched: false }
      }

      const data = await response.json()
      return { ip, port, matched: data.token_hash === expectedHash }
    } catch {
      return { ip, port, matched: false }
    }
  }

  /**
   * Detect available LAN addresses
   */
  async detect(): Promise<string | null> {
    if (!this.config.enabled) return null

    try {
      // Get local info from public endpoint
      const response = await fetch(`${this.publicBase}/tunnel/localinfo`, {
        headers: { 'Content-Type': 'application/json' }
      })

      if (!response.ok) {
        console.warn('[NetworkDetector] Failed to get local info')
        return null
      }

      const info: LocalInfoResponse = await response.json()

      if (!info.ips || info.ips.length === 0) {
        console.log('[NetworkDetector] No LAN IPs available')
        return null
      }

      console.log('[NetworkDetector] Probing IPs:', info.ips)

      // Probe all IPs in parallel
      const results = await Promise.all(
        info.ips.map(ip => this.probeAddress(ip, info.port, info.token_hash))
      )

      // Find first matching address
      const match = results.find(r => r.matched)
      if (match) {
        // If page is HTTPS, use HTTPS; otherwise use HTTP.
        // (probeAddress already tried HTTPS first when page is HTTPS,
        // so if match.matched is true, the connection succeeded.)
        const protocol = window.location.protocol
        return `${protocol}//${match.ip}:${match.port}/api`
      }

      return null
    } catch (e) {
      console.warn('[NetworkDetector] Detection failed:', e)
      return null
    }
  }

  /**
   * Switch to LAN address
   */
  switchToLan(base: string): void {
    this.currentBase = base
    this.currentType = 'lan'
    this.saveStorage()
    console.log('[NetworkDetector] Switched to LAN:', base)
    this.onBaseChange?.(base, 'lan')
  }

  /**
   * Switch to public address
   */
  switchToPublic(): void {
    this.currentBase = this.publicBase
    this.currentType = 'public'
    this.saveStorage()
    console.log('[NetworkDetector] Switched to public:', this.publicBase)
    this.onBaseChange?.(this.publicBase, 'public')
  }

  /**
   * Force use of public address
   */
  forcePublic(): void {
    this.switchToPublic()
  }

  /**
   * Handle request failure - auto fallback to public
   */
  onRequestFailure(): void {
    if (this.currentType === 'lan') {
      console.log('[NetworkDetector] LAN request failed, falling back to public')
      this.switchToPublic()
    }
  }

  /**
   * Start periodic LAN detection
   */
  startPeriodicCheck(intervalMs?: number): void {
    if (intervalMs) {
      this.config.checkInterval = intervalMs
    }

    if (this.checkTimer) {
      clearInterval(this.checkTimer)
    }

    this.checkTimer = setInterval(async () => {
      // Only detect if currently on public (already on LAN = optimal)
      if (this.currentType === 'public') {
        console.log('[NetworkDetector] Periodic check: detecting LAN...')
        const lanBase = await this.detect()
        if (lanBase) {
          console.log('[NetworkDetector] Periodic check: found LAN, switching')
          this.switchToLan(lanBase)
        }
      }
    }, this.config.checkInterval)

    console.log('[NetworkDetector] Started periodic check, interval:', this.config.checkInterval)
  }

  /**
   * Stop periodic detection
   */
  stopPeriodicCheck(): void {
    if (this.checkTimer) {
      clearInterval(this.checkTimer)
      this.checkTimer = null
      console.log('[NetworkDetector] Stopped periodic check')
    }
  }

  /**
   * Configure detector
   */
  configure(config: Partial<NetworkDetectorConfig>): void {
    this.config = { ...this.config, ...config }
  }
}

// Singleton instance
export const networkDetector = new NetworkDetector()

// Type guard for network errors (failed fetch, not HTTP errors)
export function isNetworkError(error: unknown): boolean {
  if (error instanceof TypeError) {
    // TypeError from fetch usually means network failure
    return error.message.includes('fetch') ||
           error.message.includes('network') ||
           error.message.includes('Failed to fetch') ||
           error.name === 'AbortError'
  }
  return false
}
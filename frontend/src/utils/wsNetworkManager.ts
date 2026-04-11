// frontend/src/utils/wsNetworkManager.ts
/**
 * WebSocket network manager for LAN auto-switching.
 *
 * Monitors network detector changes and notifies WebSocket connections
 * to reconnect when switching between LAN and public addresses.
 */

import { networkDetector } from './networkDetector'
import type { AddressType } from '../types/network'

class WsNetworkManager {
  private callbacks: Set<(base: string, type: AddressType) => void> = new Set()

  constructor() {
    // 监听networkDetector的变化
    networkDetector.setOnBaseChange((base: string, type: AddressType) => {
      this.handleBaseChange(base, type)
    })
  }

  private handleBaseChange(base: string, type: AddressType) {
    const wsBase = this.httpToWsBase(base)
    console.log(`[WsNetworkManager] Base changed to ${type}: ${wsBase}`)
    this.callbacks.forEach(cb => cb(wsBase, type))
  }

  /**
   * Convert HTTP base URL to WebSocket base URL
   * http://192.168.x.x:8863/api → ws://192.168.x.x:8863/ws
   * https://example.com/api → wss://example.com/ws
   */
  private httpToWsBase(httpBase: string): string {
    return httpBase
      .replace(/^http/, 'ws')
      .replace(/\/api$/, '/ws')
  }

  /**
   * Get current WebSocket base URL
   */
  getWsBase(): string {
    return this.httpToWsBase(networkDetector.getCurrentBase())
  }

  /**
   * Get complete WebSocket URL with endpoint
   */
  getWsUrl(endpoint: string): string {
    return `${this.getWsBase()}${endpoint}`
  }

  /**
   * Check if currently using LAN address
   */
  isLan(): boolean {
    return networkDetector.getCurrentType() === 'lan'
  }

  /**
   * Get current address type
   */
  getType(): AddressType {
    return networkDetector.getCurrentType()
  }

  /**
   * Register callback for WebSocket base URL changes
   * Returns unsubscribe function
   */
  onWsBaseChange(callback: (base: string, type: AddressType) => void): () => void {
    this.callbacks.add(callback)
    return () => this.callbacks.delete(callback)
  }
}

// Singleton instance
export const wsNetworkManager = new WsNetworkManager()
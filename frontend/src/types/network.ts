// frontend/src/types/network.ts
/** Network detection types for LAN auto-switching */

export interface LocalInfoResponse {
  ips: string[]
  port: number
  token_hash: string
}

export interface TokenHashResponse {
  token_hash: string
}

export interface LanDetectorStorage {
  preferred_base: string | null
  public_base: string
  last_check: number
}

export type AddressType = 'lan' | 'public'

export interface ProbeResult {
  ip: string
  port: number
  matched: boolean
}

export interface NetworkDetectorConfig {
  probeTimeout: number      // Default: 3000ms
  checkInterval: number     // Default: 5 minutes
  enabled: boolean          // Default: true
}

export const DEFAULT_CONFIG: NetworkDetectorConfig = {
  probeTimeout: 3000,
  checkInterval: 5 * 60 * 1000,  // 5 minutes
  enabled: true
}
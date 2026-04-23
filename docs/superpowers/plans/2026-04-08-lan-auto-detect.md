# 局域网自动检测与切换实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现前端自动检测局域网后端并切换连接，减轻公网服务器压力。

**Architecture:** 前端通过公网 API 获取局域网 IP 列表，并行探测可用地址，发现匹配后自动切换。请求失败时自动回退到公网地址。

**Tech Stack:** Python/FastAPI (后端), TypeScript/Vue 3 (前端)

---

## 文件结构

```
backend/app/
├── services/network_service.py    # 新增：网络信息获取服务
├── routers/tunnel.py              # 修改：添加 localinfo 和 token_hash 端点
└── schemas.py                     # 修改：添加新响应 schema

frontend/src/
├── types/network.ts               # 新增：网络检测类型定义
├── utils/networkDetector.ts       # 新增：核心检测模块
├── api/client.ts                  # 修改：添加回退逻辑
└── main.ts                        # 修改：初始化网络检测
```

---

## Task 1: 后端 - 网络信息服务

**Files:**
- Create: `backend/app/services/network_service.py`

- [ ] **Step 1: 创建网络服务模块**

```python
# backend/app/services/network_service.py
"""Network information service for LAN detection."""

import hashlib
import socket
import logging
from typing import List
from app.config import settings

logger = logging.getLogger(__name__)


class NetworkService:
    """Service for getting network information."""

    def __init__(self, port: int = None):
        self.port = port or settings.port

    def get_local_ips(self) -> List[str]:
        """Get all local network IP addresses.
        
        Returns:
            List of IPv4 addresses (excluding 127.0.0.1 and public IPs)
        """
        ips = []
        try:
            # Get hostname and all associated IPs
            hostname = socket.gethostname()
            all_ips = socket.gethostbyname_ex(hostname)[2]
            
            for ip in all_ips:
                # Filter: exclude loopback and keep only private IPs
                if ip == "127.0.0.1":
                    continue
                if self._is_private_ip(ip):
                    ips.append(ip)
                    
        except Exception as e:
            logger.error(f"Failed to get local IPs: {e}")
            
        return ips

    def _is_private_ip(self, ip: str) -> bool:
        """Check if IP is a private/local network address.
        
        Private IP ranges:
        - 10.0.0.0/8
        - 172.16.0.0/12
        - 192.168.0.0/16
        - 169.254.0.0/16 (link-local)
        """
        parts = [int(p) for p in ip.split(".")]
        
        # 10.0.0.0/8
        if parts[0] == 10:
            return True
        # 172.16.0.0/12
        if parts[0] == 172 and 16 <= parts[1] <= 31:
            return True
        # 192.168.0.0/16
        if parts[0] == 192 and parts[1] == 168:
            return True
        # 169.254.0.0/16 (link-local)
        if parts[0] == 169 and parts[1] == 254:
            return True
            
        return False

    def generate_token_hash(self) -> str:
        """Generate a hash for verifying backend identity.
        
        Uses a combination of:
        - Server port
        - First local IP (if available)
        - A random session identifier
        
        Returns:
            SHA256 hash string prefixed with 'sha256:'
        """
        # Create unique identifier for this backend instance
        identifier = f"{self.port}:{','.join(self.get_local_ips() or ['none'])}"
        hash_value = hashlib.sha256(identifier.encode()).hexdigest()[:16]
        return f"sha256:{hash_value}"


# Global instance
network_service = NetworkService()
```

- [ ] **Step 2: 验证服务可导入**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/backend && python -c "from app.services.network_service import network_service; print(network_service.get_local_ips())"`

Expected: 打印本机局域网 IP 列表（如 `['192.168.1.100']`）

- [ ] **Step 3: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add backend/app/services/network_service.py
git commit -m "feat(backend): add network service for LAN detection"
```

---

## Task 2: 后端 - Schema 定义

**Files:**
- Modify: `backend/app/schemas.py`

- [ ] **Step 1: 添加网络检测响应 Schema**

在 `backend/app/schemas.py` 文件末尾添加：

```python
# Network detection schemas
class LocalInfoResponse(BaseModel):
    """Response for /api/tunnel/localinfo endpoint."""
    ips: List[str]
    port: int
    token_hash: str


class TokenHashResponse(BaseModel):
    """Response for /api/tunnel/token_hash endpoint."""
    token_hash: str
```

- [ ] **Step 2: 验证 Schema 定义**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/backend && python -c "from app.schemas import LocalInfoResponse, TokenHashResponse; print('Schemas OK')"`

Expected: 输出 `Schemas OK`

- [ ] **Step 3: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add backend/app/schemas.py
git commit -m "feat(backend): add LocalInfoResponse and TokenHashResponse schemas"
```

---

## Task 3: 后端 - API 端点

**Files:**
- Modify: `backend/app/routers/tunnel.py`

- [ ] **Step 1: 导入新依赖并添加端点**

在 `backend/app/routers/tunnel.py` 中：

1. 在文件顶部添加导入：
```python
from app.services.network_service import network_service
from app.schemas import LocalInfoResponse, TokenHashResponse
```

2. 在文件末尾添加新端点：
```python
@router.get("/localinfo", response_model=LocalInfoResponse)
async def get_local_info():
    """Get local network information for LAN detection.
    
    This endpoint returns all local IPs and a token hash for verification.
    No authentication required - this is used by frontend to detect LAN availability.
    """
    return LocalInfoResponse(
        ips=network_service.get_local_ips(),
        port=network_service.port,
        token_hash=network_service.generate_token_hash()
    )


@router.get("/token_hash", response_model=TokenHashResponse)
async def get_token_hash():
    """Get token hash for backend identity verification.
    
    This endpoint is used to verify that the connected backend is the same instance.
    No authentication required - this is used for LAN detection probing.
    """
    return TokenHashResponse(
        token_hash=network_service.generate_token_hash()
    )
```

- [ ] **Step 2: 启动后端并测试端点**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy && ./deploy.sh restart`

等待服务启动后：

Run: `curl http://localhost:8863/api/tunnel/localinfo`

Expected: 返回 JSON `{"ips": ["192.168.x.x", ...], "port": 8863, "token_hash": "sha256:..."}`

Run: `curl http://localhost:8863/api/tunnel/token_hash`

Expected: 返回 JSON `{"token_hash": "sha256:..."}`

- [ ] **Step 3: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add backend/app/routers/tunnel.py
git commit -m "feat(backend): add /api/tunnel/localinfo and token_hash endpoints"
```

---

## Task 4: 前端 - 类型定义

**Files:**
- Create: `frontend/src/types/network.ts`

- [ ] **Step 1: 创建类型定义文件**

```typescript
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
```

- [ ] **Step 2: 验证类型定义**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/frontend && npx tsc --noEmit src/types/network.ts`

Expected: 无错误输出

- [ ] **Step 3: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add frontend/src/types/network.ts
git commit -m "feat(frontend): add network detection type definitions"
```

---

## Task 5: 前端 - 网络检测模块

**Files:**
- Create: `frontend/src/utils/networkDetector.ts`

- [ ] **Step 1: 创建网络检测模块**

```typescript
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
    const url = `http://${ip}:${port}/api/tunnel/token_hash`
    
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
        return `http://${match.ip}:${match.port}/api`
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
```

- [ ] **Step 2: 验证模块编译**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/frontend && npx tsc --noEmit src/utils/networkDetector.ts`

Expected: 无错误输出

- [ ] **Step 3: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add frontend/src/utils/networkDetector.ts
git commit -m "feat(frontend): add network detector module for LAN auto-switching"
```

---

## Task 6: 前端 - API 客户端集成

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: 重构 API 客户端以支持动态切换**

修改 `frontend/src/api/client.ts`，替换整个文件内容：

```typescript
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
```

- [ ] **Step 2: 验证客户端编译**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/frontend && npx tsc --noEmit src/api/client.ts`

Expected: 无错误输出

- [ ] **Step 3: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add frontend/src/api/client.ts
git commit -m "feat(frontend): integrate network detector into API client with fallback"
```

---

## Task 7: 前端 - 应用初始化

**Files:**
- Modify: `frontend/src/main.ts`

- [ ] **Step 1: 修改 main.ts 初始化网络检测**

```typescript
// frontend/src/main.ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import { initApiClient, startLanDetection } from './api/client'
import './assets/styles/main.css'
import 'splitpanes/dist/splitpanes.css'
import 'highlight.js/styles/atom-one-dark.css'

async function bootstrap() {
  // Initialize API client with network detection
  await initApiClient()
  
  // Start periodic LAN detection (every 5 minutes)
  startLanDetection(5 * 60 * 1000)

  const app = createApp(App)
  app.use(createPinia())
  app.use(router)
  
  app.mount('#app')
}

bootstrap()
```

- [ ] **Step 2: 验证应用启动**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/frontend && npm run build`

Expected: 构建成功无错误

- [ ] **Step 3: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add frontend/src/main.ts
git commit -m "feat(frontend): initialize network detector on app startup"
```

---

## Task 8: 集成测试

- [ ] **Step 1: 重启服务并测试**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy && ./deploy.sh restart`

等待服务启动后，在浏览器打开开发者工具控制台：

1. 打开页面，观察控制台日志：
   - 应看到 `[NetworkDetector]` 相关日志
   - 如果在局域网内，应看到 `Switched to LAN: http://192.168.x.x:8863/api`

2. 测试 localStorage：
   - 打开 Application → Local Storage
   - 应看到 `lan_detector` 键，包含 `preferred_base`、`public_base`、`last_check`

3. 测试回退：
   - 手动修改 localStorage 中的 `preferred_base` 为无效地址
   - 刷新页面，应看到先尝试 LAN 失败，然后切换到 public

- [ ] **Step 2: 验证控制台日志**

在浏览器控制台运行：
```javascript
localStorage.getItem('lan_detector')
```

Expected: 返回 JSON 字符串包含正确的配置信息

- [ ] **Step 3: Final Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add -A
git commit -m "feat: complete LAN auto-detection and switching feature"
```

---

## 验收清单

- [ ] 后端 `/api/tunnel/localinfo` 返回局域网 IP 列表和 token_hash
- [ ] 后端 `/api/tunnel/token_hash` 返回 token_hash（无需认证）
- [ ] 前端启动时自动检测局域网可用性
- [ ] 发现局域网地址时自动切换
- [ ] localStorage 正确保存检测状态
- [ ] 局域网请求失败时自动回退公网
- [ ] 定时检测正常工作（每 5 分钟）
- [ ] 控制台日志清晰显示切换过程
import { onUnmounted, shallowRef, type ShallowRef } from 'vue'
import { useAuth } from './useAuth'
import { wsNetworkManager } from '../utils/wsNetworkManager'
import type { AddressType } from '../types/network'

const WebSocketState = {
  CONNECTING: 0,
  OPEN: 1,
  CLOSING: 2,
  CLOSED: 3
}

// Simple debounce implementation
function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null

  return function(this: any, ...args: Parameters<T>) {
    if (timeout !== null) {
      clearTimeout(timeout)
    }
    timeout = setTimeout(() => func.apply(this, args), wait)
  }
}

// Global connection pool - persists across component mount/unmount cycles
interface PersistentConnection {
  ws: WebSocket | null
  connected: ShallowRef<boolean>
  connecting: ShallowRef<boolean>
  output: ShallowRef<string[]>
  error: ShallowRef<string | null>
  connectionType: ShallowRef<AddressType>
  isIntentionalClose: boolean
  reconnectTimeout: ReturnType<typeof setTimeout> | null
  onDataCallback: ((data: string) => void) | null
  messageHandlers: Map<string, (data: any) => void>
  unsubscribeNetwork: (() => void) | null
  pendingResize: { cols: number; rows: number } | null
  taskId: string
  refCount: number // Number of components using this connection
  unsubscribeVisibility: (() => void) | null
  unsubscribeOnline: (() => void) | null
}

// Global map of active connections keyed by taskId
const globalConnections = new Map<string, PersistentConnection>()

/**
 * Close a connection by taskId (used when task changes or page unloads)
 */
export function closePersistentConnection(taskId: string): void {
  const conn = globalConnections.get(taskId)
  if (!conn) return

  conn.refCount--
  if (conn.refCount > 0) return // Still in use

  console.log(`[useWebSocket] Closing persistent connection for task: ${taskId}`)
  conn.isIntentionalClose = true

  if (conn.reconnectTimeout) {
    clearTimeout(conn.reconnectTimeout)
    conn.reconnectTimeout = null
  }

  if (conn.ws) {
    conn.ws.close()
    conn.ws = null
  }

  conn.connected.value = false
  conn.connecting.value = false
  conn.onDataCallback = null
  conn.messageHandlers.clear()

  if (conn.unsubscribeNetwork) {
    conn.unsubscribeNetwork()
    conn.unsubscribeNetwork = null
  }

  if (conn.unsubscribeVisibility) {
    conn.unsubscribeVisibility()
    conn.unsubscribeVisibility = null
  }

  if (conn.unsubscribeOnline) {
    conn.unsubscribeOnline()
    conn.unsubscribeOnline = null
  }

  globalConnections.delete(taskId)
}

export interface UseWebSocketOptions {
  /** If true, disconnect will NOT be called automatically on unmount */
  persistOnUnmount?: boolean
}

export function useWebSocket(taskId: string, options?: UseWebSocketOptions) {
  const { token } = useAuth()

  // Guard against undefined taskId - happens when route.query.task is not yet resolved
  const isTaskIdValid = taskId && taskId !== 'undefined'

  // Check if a persistent connection already exists for this taskId
  let existing = isTaskIdValid ? globalConnections.get(taskId) : undefined

  if (existing) {
    existing.refCount++
    console.log(`[useWebSocket] Reusing existing connection for task: ${taskId} (refCount: ${existing.refCount})`)
  } else if (isTaskIdValid) {
    // Create new persistent connection only for valid taskIds
    existing = {
      ws: null,
      connected: shallowRef(false),
      connecting: shallowRef(false),
      output: shallowRef<string[]>([]),
      error: shallowRef<string | null>(null),
      connectionType: shallowRef<AddressType>('public'),
      isIntentionalClose: false,
      reconnectTimeout: null,
      onDataCallback: null,
      messageHandlers: new Map(),
      unsubscribeNetwork: null,
      pendingResize: null,
      taskId,
      refCount: 1,
      unsubscribeVisibility: null,
      unsubscribeOnline: null
    }
    globalConnections.set(taskId, existing)
    console.log(`[useWebSocket] Created new persistent connection for task: ${taskId}`)
  } else {
    console.warn(`[useWebSocket] Skipping connection for invalid taskId: ${taskId}`)
    existing = {
      ws: null,
      connected: shallowRef(false),
      connecting: shallowRef(false),
      output: shallowRef<string[]>([]),
      error: shallowRef<string | null>(null),
      connectionType: shallowRef<AddressType>('public'),
      isIntentionalClose: true,
      reconnectTimeout: null,
      onDataCallback: null,
      messageHandlers: new Map(),
      unsubscribeNetwork: null,
      pendingResize: null,
      taskId: taskId || '',
      refCount: 1,
      unsubscribeVisibility: null,
      unsubscribeOnline: null
    }
  }

  const conn = existing

  const connect = (onData?: (data: string) => void, initialSize?: { cols: number; rows: number }) => {
    // Skip connection if taskId is invalid
    if (!isTaskIdValid) {
      console.warn(`[useWebSocket] Cannot connect: invalid taskId`)
      return
    }

    // If already connected, just update callback
    if (conn.ws && conn.ws.readyState === WebSocketState.OPEN) {
      if (onData) conn.onDataCallback = onData
      return
    }

    // Close existing connection if any
    if (conn.ws) {
      conn.isIntentionalClose = true
      if (conn.ws.readyState === WebSocketState.CONNECTING || conn.ws.readyState === WebSocketState.OPEN) {
        conn.ws.close()
      }
      conn.ws = null
    }

    // Clear any pending reconnect
    if (conn.reconnectTimeout) {
      clearTimeout(conn.reconnectTimeout)
      conn.reconnectTimeout = null
    }

    if (!token.value) {
      conn.error.value = 'Not authenticated'
      return
    }

    // Register data callback
    if (onData) {
      conn.onDataCallback = onData
    }

    conn.connecting.value = true
    conn.error.value = null
    conn.isIntentionalClose = false
    conn.connectionType.value = wsNetworkManager.getType()

    // Build WebSocket URL with optional initial size params
    let path = `/terminal?token=${token.value}&task_id=${taskId}`
    if (initialSize) {
      path += `&cols=${initialSize.cols}&rows=${initialSize.rows}`
    }
    const wsUrl = wsNetworkManager.getWsUrl(path)

    try {
      conn.ws = new WebSocket(wsUrl)

      conn.ws.onopen = () => {
        conn.connected.value = true
        conn.connecting.value = false
        conn.error.value = null
        // Send any pending resize message
        if (conn.pendingResize) {
          console.log(`[WebSocket] Sending pending resize: ${conn.pendingResize.cols}x${conn.pendingResize.rows}`)
          conn.ws?.send(JSON.stringify({ type: 'resize', cols: conn.pendingResize.cols, rows: conn.pendingResize.rows }))
          conn.pendingResize = null
        }
      }

      conn.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          // Handle heartbeat ping from server
          if (msg.type === 'ping') {
            conn.ws?.send(JSON.stringify({ type: 'pong' }))
            return
          }
          if (msg.type === 'output') {
            conn.output.value.push(msg.data)
            // Call callback if registered
            if (conn.onDataCallback) {
              conn.onDataCallback(msg.data)
            }
          } else if (msg.type === 'error') {
            conn.error.value = msg.message
          } else {
            // Handle custom message types (e.g., queue_updated)
            const handler = conn.messageHandlers.get(msg.type)
            if (handler) {
              handler(msg)
            }
          }
        } catch {
          // Raw text output
          conn.output.value.push(event.data)
          if (conn.onDataCallback) {
            conn.onDataCallback(event.data)
          }
        }
      }

      conn.ws.onerror = () => {
        conn.error.value = 'WebSocket error'
        conn.connecting.value = false
      }

      conn.ws.onclose = () => {
        conn.connected.value = false
        conn.connecting.value = false
        conn.ws = null

        // Auto-reconnect after 10s on abnormal disconnect (non-mobile only)
        if (!conn.isIntentionalClose && window.innerWidth >= 768 && token.value) {
          if (conn.onDataCallback) {
            conn.onDataCallback('\r\n\x1b[33mConnection lost. Reconnecting in 10s...\x1b[0m')
          }
          conn.reconnectTimeout = setTimeout(() => {
            conn.reconnectTimeout = null
            if (token.value) {
              connect()
            }
          }, 10000)
        }
      }
    } catch (err: any) {
      conn.error.value = err.message
      conn.connecting.value = false
    }
  }

  const disconnect = () => {
    conn.isIntentionalClose = true

    if (conn.reconnectTimeout) {
      clearTimeout(conn.reconnectTimeout)
      conn.reconnectTimeout = null
    }

    if (conn.ws) {
      conn.ws.close()
      conn.ws = null
    }

    conn.connected.value = false
    conn.connecting.value = false
    conn.onDataCallback = null
    conn.messageHandlers.clear()

    // Unsubscribe from network changes
    if (conn.unsubscribeNetwork) {
      conn.unsubscribeNetwork()
      conn.unsubscribeNetwork = null
    }

    if (conn.unsubscribeVisibility) {
      conn.unsubscribeVisibility()
      conn.unsubscribeVisibility = null
    }

    if (conn.unsubscribeOnline) {
      conn.unsubscribeOnline()
      conn.unsubscribeOnline = null
    }

    // Remove from global pool
    globalConnections.delete(taskId)
  }

  /**
   * Delayed connect - wait before connecting to allow network detection to complete
   */
  const delayedConnect = (delayMs: number = 3000, onData?: (data: string) => void) => {
    setTimeout(() => {
      connect(onData)
    }, delayMs)
  }

  // Setup visibility/online listeners for mobile reconnection
  const handleVisibilityChange = () => {
    if (document.visibilityState === 'visible') {
      if (!conn.ws || conn.ws.readyState !== WebSocketState.OPEN) {
        console.log(`[useWebSocket] Visibility changed to visible, reconnecting...`)
        if (token.value) connect(conn.onDataCallback || undefined)
      }
    }
  }

  const handleOnline = () => {
    if (!conn.ws || conn.ws.readyState !== WebSocketState.OPEN) {
      console.log(`[useWebSocket] Network online, reconnecting...`)
      if (token.value) connect(conn.onDataCallback || undefined)
    }
  }

  conn.unsubscribeVisibility = () => {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  }
  conn.unsubscribeOnline = () => {
    window.removeEventListener('online', handleOnline)
  }

  document.addEventListener('visibilitychange', handleVisibilityChange)
  window.addEventListener('online', handleOnline)

  /**
   * Setup network change listener - reconnect when switching between LAN/public
   */
  const setupNetworkListener = () => {
    if (conn.unsubscribeNetwork) return // Already setup

    conn.unsubscribeNetwork = wsNetworkManager.onWsBaseChange((_base: string, type: AddressType) => {
      console.log(`[WebSocket] Network changed to ${type}, reconnecting...`)
      conn.connectionType.value = type

      // Immediately reconnect if connected
      if (conn.connected.value || conn.connecting.value) {
        // Close current connection
        if (conn.ws) {
          conn.ws.close()
          conn.ws = null
        }
        conn.connected.value = false
        conn.connecting.value = false

        // Reconnect with new address
        if (token.value) {
          setTimeout(() => connect(conn.onDataCallback || undefined), 100)
        }
      }
    })
  }

  const onMessage = (type: string, handler: (data: any) => void) => {
    conn.messageHandlers.set(type, handler)
  }

  const offMessage = (type: string) => {
    conn.messageHandlers.delete(type)
  }

  const send = (data: string) => {
    if (conn.ws && conn.ws.readyState === WebSocketState.OPEN) {
      conn.ws.send(JSON.stringify({ type: 'input', data }))
    }
  }

  const sendRaw = (message: object) => {
    if (conn.ws && conn.ws.readyState === WebSocketState.OPEN) {
      conn.ws.send(JSON.stringify(message))
    }
  }

  // Debounced resize to prevent flooding backend during window resize
  const debouncedResize = debounce((cols: number, rows: number) => {
    if (conn.ws && conn.ws.readyState === WebSocketState.OPEN) {
      conn.ws.send(JSON.stringify({ type: 'resize', cols, rows }))
      console.log(`[WebSocket] Sent resize: ${cols}x${rows}`)
    } else {
      // Store resize to send when connection opens
      conn.pendingResize = { cols, rows }
      console.log(`[WebSocket] Queued resize: ${cols}x${rows} (not connected)`)
    }
  }, 200) // 200ms debounce delay

  const resize = (cols: number, rows: number) => {
    debouncedResize(cols, rows)
  }

  const clearOutput = () => {
    conn.output.value = []
  }

  onUnmounted(() => {
    conn.refCount--

    if (options?.persistOnUnmount) {
      return
    }

    // Only truly disconnect if no other components are using this connection
    if (conn.refCount <= 0) {
      disconnect()
    }
  })

  return {
    connected: conn.connected,
    connecting: conn.connecting,
    output: conn.output,
    error: conn.error,
    connectionType: conn.connectionType,
    connect,
    delayedConnect,
    setupNetworkListener,
    disconnect,
    send,
    sendRaw,
    resize,
    clearOutput,
    onMessage,
    offMessage
  }
}

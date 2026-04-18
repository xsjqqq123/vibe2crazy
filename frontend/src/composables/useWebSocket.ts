import { ref, onUnmounted } from 'vue'
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

export function useWebSocket(taskId: string) {
  const { token } = useAuth()
  const ws = ref<WebSocket | null>(null)
  const connected = ref(false)
  const connecting = ref(false)
  const output = ref<string[]>([])
  const error = ref<string | null>(null)
  const connectionType = ref<AddressType>('public')
  let isIntentionalClose = false
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null

  // Callback for receiving data
  let onDataCallback: ((data: string) => void) | null = null
  // Custom message handlers for specific event types
  const messageHandlers: Map<string, (data: any) => void> = new Map()
  // Unsubscribe function for network changes
  let unsubscribeNetwork: (() => void) | null = null

  const connect = (onData?: (data: string) => void) => {
    // Close existing connection if any
    if (ws.value) {
      isIntentionalClose = true
      if (ws.value.readyState === WebSocketState.CONNECTING || ws.value.readyState === WebSocketState.OPEN) {
        ws.value.close()
      }
      ws.value = null
    }

    // Clear any pending reconnect
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }

    if (!token.value) {
      error.value = 'Not authenticated'
      return
    }

    // Register data callback
    if (onData) {
      onDataCallback = onData
    }

    connecting.value = true
    error.value = null
    isIntentionalClose = false
    connectionType.value = wsNetworkManager.getType()

    // Get WebSocket URL from network manager
    const wsUrl = wsNetworkManager.getWsUrl(`/terminal?token=${token.value}&task_id=${taskId}`)

    try {
      ws.value = new WebSocket(wsUrl)

      ws.value.onopen = () => {
        connected.value = true
        connecting.value = false
        error.value = null
        // Send any pending resize message
        if (pendingResize) {
          console.log(`[WebSocket] Sending pending resize: ${pendingResize.cols}x${pendingResize.rows}`)
          ws.value?.send(JSON.stringify({ type: 'resize', cols: pendingResize.cols, rows: pendingResize.rows }))
          pendingResize = null
        }
      }

      ws.value.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'output') {
            output.value.push(msg.data)
            // Call callback if registered
            if (onDataCallback) {
              onDataCallback(msg.data)
            }
          } else if (msg.type === 'error') {
            error.value = msg.message
          } else {
            // Handle custom message types (e.g., queue_updated)
            const handler = messageHandlers.get(msg.type)
            if (handler) {
              handler(msg)
            }
          }
        } catch {
          // Raw text output
          output.value.push(event.data)
          if (onDataCallback) {
            onDataCallback(event.data)
          }
        }
      }

      ws.value.onerror = () => {
        error.value = 'WebSocket error'
        connecting.value = false
      }

      ws.value.onclose = () => {
        connected.value = false
        connecting.value = false
        ws.value = null

        // Auto-reconnect after 10s on abnormal disconnect (non-mobile only)
        if (!isIntentionalClose && window.innerWidth >= 768 && token.value) {
          if (onDataCallback) {
            onDataCallback('\r\n\x1b[33mConnection lost. Reconnecting in 10s...\x1b[0m')
          }
          reconnectTimeout = setTimeout(() => {
            reconnectTimeout = null
            if (token.value) {
              connect()
            }
          }, 10000)
        }
      }
    } catch (err: any) {
      error.value = err.message
      connecting.value = false
    }
  }

  const disconnect = () => {
    isIntentionalClose = true

    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }

    if (ws.value) {
      ws.value.close()
      ws.value = null
    }

    connected.value = false
    connecting.value = false
    onDataCallback = null
    messageHandlers.clear()

    // Unsubscribe from network changes
    if (unsubscribeNetwork) {
      unsubscribeNetwork()
      unsubscribeNetwork = null
    }
  }

  /**
   * Delayed connect - wait before connecting to allow network detection to complete
   */
  const delayedConnect = (delayMs: number = 3000, onData?: (data: string) => void) => {
    setTimeout(() => {
      connect(onData)
    }, delayMs)
  }

  /**
   * Setup network change listener - reconnect when switching between LAN/public
   */
  const setupNetworkListener = () => {
    if (unsubscribeNetwork) return // Already setup

    unsubscribeNetwork = wsNetworkManager.onWsBaseChange((_base: string, type: AddressType) => {
      console.log(`[WebSocket] Network changed to ${type}, reconnecting...`)
      connectionType.value = type

      // Immediately reconnect if connected
      if (connected.value || connecting.value) {
        // Close current connection
        if (ws.value) {
          ws.value.close()
          ws.value = null
        }
        connected.value = false
        connecting.value = false

        // Reconnect with new address
        if (token.value) {
          setTimeout(() => connect(onDataCallback || undefined), 100)
        }
      }
    })
  }

  const onMessage = (type: string, handler: (data: any) => void) => {
    messageHandlers.set(type, handler)
  }

  const offMessage = (type: string) => {
    messageHandlers.delete(type)
  }

  const send = (data: string) => {
    if (ws.value && ws.value.readyState === WebSocketState.OPEN) {
      ws.value.send(JSON.stringify({ type: 'input', data }))
    }
  }

  const sendRaw = (message: object) => {
    if (ws.value && ws.value.readyState === WebSocketState.OPEN) {
      ws.value.send(JSON.stringify(message))
    }
  }

  // Queue for resize messages before connection is ready
  let pendingResize: { cols: number; rows: number } | null = null

  // Debounced resize to prevent flooding backend during window resize
  const debouncedResize = debounce((cols: number, rows: number) => {
    if (ws.value && ws.value.readyState === WebSocketState.OPEN) {
      ws.value.send(JSON.stringify({ type: 'resize', cols, rows }))
      console.log(`[WebSocket] Sent resize: ${cols}x${rows}`)
    } else {
      // Store resize to send when connection opens
      pendingResize = { cols, rows }
      console.log(`[WebSocket] Queued resize: ${cols}x${rows} (not connected)`)
    }
  }, 200) // 200ms debounce delay

  const resize = (cols: number, rows: number) => {
    debouncedResize(cols, rows)
  }

  const clearOutput = () => {
    output.value = []
  }

  onUnmounted(() => {
  try {
    disconnect()
  } catch (err: any) {
    console.error('[Terminal] Error during disconnect:', err)
  }
})

  return {
    connected,
    connecting,
    output,
    error,
    connectionType,
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

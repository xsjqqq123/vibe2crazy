<!-- frontend/src/components/GlobalTerminal.vue -->
<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Terminal as XTerminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { useGlobalTerminalStore } from '@/store/globalTerminal'
import { useMainStore, type ThemeName } from '@/store'
import { useAuth } from '@/composables/useAuth'
import { wsNetworkManager } from '@/utils/wsNetworkManager'
import type { AddressType } from '@/types/network'

const store = useGlobalTerminalStore()
const mainStore = useMainStore()
const { token } = useAuth()

const terminalRef = ref<HTMLElement | null>(null)
const containerRef = ref<HTMLElement | null>(null)
const xterm = ref<XTerminal | null>(null)
const fitAddon = ref<FitAddon | null>(null)
const resizeObserver = ref<ResizeObserver | null>(null)
let resizeTimeout: ReturnType<typeof setTimeout> | null = null
let wheelHandler: ((e: WheelEvent) => void) | null = null
let connectTimeout: ReturnType<typeof setTimeout> | null = null
let unsubscribeNetwork: (() => void) | null = null

const ws = ref<WebSocket | null>(null)
const connected = ref(false)
const connecting = ref(false)
const connectionType = ref<AddressType>('public')
let isIntentionalClose = false
let reconnectTimeout: ReturnType<typeof setTimeout> | null = null

// API Error auto-continue watcher
let apiErrorTimer: ReturnType<typeof setTimeout> | null = null

const checkApiError = () => {
  if (!xterm.value) return
  const buffer = xterm.value.buffer.active
  const visibleLines: string[] = []
  for (let i = 0; i < buffer.length; i++) {
    visibleLines.push(buffer.getLine(i)?.translateToString(true) ?? '')
  }
  const text = visibleLines.join(' ')
  const hasApiError = text.includes('API Error:')

  if (hasApiError && !apiErrorTimer) {
    apiErrorTimer = setTimeout(() => {
      apiErrorTimer = null
      if (!xterm.value) return
      const buf = xterm.value.buffer.active
      const lines: string[] = []
      for (let i = 0; i < buf.length; i++) {
        lines.push(buf.getLine(i)?.translateToString(true) ?? '')
      }
      if (lines.join(' ').includes('API Error:')) {
        send('continue')
        setTimeout(() => send('\r'), 500)
      }
    }, 20000)
  } else if (!hasApiError && apiErrorTimer) {
    clearTimeout(apiErrorTimer)
    apiErrorTimer = null
  }
}

// Drag state
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })

// Resize state
const isResizing = ref(false)
const resizeEdge = ref<string | null>(null)
const resizeStart = ref({ x: 0, y: 0, width: 0, height: 0, posX: 0, posY: 0 })

// Mobile detection
const isMobile = ref(window.innerWidth < 768)

// Theme configurations (same as Terminal.vue)
const DARK_THEME = {
  background: '#1e1e1e',
  foreground: '#d4d4d4',
  cursor: '#ffffff',
  selectionBackground: '#264f78',
  black: '#000000',
  red: '#cd3131',
  green: '#0dbc79',
  yellow: '#e5e510',
  blue: '#2472c8',
  magenta: '#bc3fbc',
  cyan: '#11a8cd',
  white: '#e5e5e5',
  brightBlack: '#666666',
  brightRed: '#f14c4c',
  brightGreen: '#23d18b',
  brightYellow: '#f5f543',
  brightBlue: '#3b8eea',
  brightMagenta: '#d670d6',
  brightCyan: '#29b8db',
  brightWhite: '#ffffff'
}

const LIGHT_THEME = {
  background: '#ffffff',
  foreground: '#333333',
  cursor: '#000000',
  selectionBackground: '#add6ff',
  black: '#000000',
  red: '#e14c4c',
  green: '#2da858',
  yellow: '#d4b418',
  blue: '#2c7bd6',
  magenta: '#c858c8',
  cyan: '#1fa8d4',
  white: '#333333',
  brightBlack: '#666666',
  brightRed: '#f14c4c',
  brightGreen: '#23d18b',
  brightYellow: '#e5c00e',
  brightBlue: '#3b8eea',
  brightMagenta: '#d670d6',
  brightCyan: '#29b8db',
  brightWhite: '#000000'
}

const GREEN_THEME = {
  background: '#c7edcc',
  foreground: '#2d5a3d',
  cursor: '#3b82f6',
  selectionBackground: 'rgba(59, 130, 246, 0.3)',
  black: '#2d5a3d',
  red: '#c75050',
  green: '#2d8b4e',
  yellow: '#8b6914',
  blue: '#2c7bd6',
  magenta: '#a858a8',
  cyan: '#1fa8d4',
  white: '#e8f5e9',
  brightBlack: '#4a7c5b',
  brightRed: '#e06060',
  brightGreen: '#3da85e',
  brightYellow: '#a08920',
  brightBlue: '#4a8eea',
  brightMagenta: '#b870b8',
  brightCyan: '#3ab8e4',
  brightWhite: '#ffffff'
}

const PARCHMENT_THEME = {
  background: '#f4ecd8',
  foreground: '#5c4d3a',
  cursor: '#b8860b',
  selectionBackground: 'rgba(184, 134, 11, 0.3)',
  black: '#5c4d3a',
  red: '#a04040',
  green: '#3d7a4a',
  yellow: '#7a6914',
  blue: '#2c5aa6',
  magenta: '#8a488a',
  cyan: '#1a8894',
  white: '#f4ecd8',
  brightBlack: '#7a6b55',
  brightRed: '#c05050',
  brightGreen: '#4d9a5a',
  brightYellow: '#9a8920',
  brightBlue: '#4a6ab6',
  brightMagenta: '#a858a8',
  brightCyan: '#2aa8b4',
  brightWhite: '#ffffff'
}

const getXtermTheme = (theme: ThemeName) => {
  const themes: Record<ThemeName, any> = {
    light: LIGHT_THEME,
    dark: DARK_THEME,
    green: GREEN_THEME,
    parchment: PARCHMENT_THEME
  }
  return themes[theme]
}

const getWsUrl = () => {
  // Get base URL from network manager
  let wsBase = wsNetworkManager.getWsBase()

  // Development mode: use Vite proxy
  if (import.meta.env.DEV) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.hostname
    const port = window.location.port
    wsBase = `${protocol}//${host}:${port}/ws`
  }

  return `${wsBase}/global-terminal`
}

const connect = () => {
  if (ws.value) {
    isIntentionalClose = true
    ws.value.close()
    ws.value = null
  }

  // Clear any pending reconnect
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout)
    reconnectTimeout = null
  }

  if (!token.value) return

  connecting.value = true
  isIntentionalClose = false
  connectionType.value = wsNetworkManager.getType()
  const wsUrl = `${getWsUrl()}?token=${token.value}`

  try {
    ws.value = new WebSocket(wsUrl)

    ws.value.onopen = () => {
      connected.value = true
      connecting.value = false
      if (xterm.value) {
        // Clear terminal and send reset command
        xterm.value.clear()
        // Send initial resize after connection is established
        resize(xterm.value.cols, xterm.value.rows)
      }
      // Reset API error watcher on reconnect
      if (apiErrorTimer) { clearTimeout(apiErrorTimer); apiErrorTimer = null }
    }

    ws.value.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'output') {
          xterm.value?.write(msg.data)
          checkApiError()
        } else if (msg.type === 'error') {
          xterm.value?.writeln(`\x1b[31mError: ${msg.message}\x1b[0m`)
        }
      } catch {
        xterm.value?.write(event.data)
        checkApiError()
      }
    }

    ws.value.onerror = () => {
      connecting.value = false
      xterm.value?.writeln('\x1b[31mConnection error\x1b[0m')
    }

    ws.value.onclose = () => {
      connected.value = false
      connecting.value = false
      ws.value = null

      // Auto-reconnect after 10s on abnormal disconnect (non-mobile only)
      if (!isIntentionalClose && window.innerWidth >= 768 && token.value) {
        xterm.value?.writeln('\r\n\x1b[33mConnection lost. Reconnecting in 10s...\x1b[0m')
        reconnectTimeout = setTimeout(() => {
          reconnectTimeout = null
          if (token.value) {
            connect()
          }
        }, 10000)
      }
    }
  } catch (err: any) {
    connecting.value = false
    xterm.value?.writeln(`\x1b[31mFailed to connect: ${err.message}\x1b[0m`)
  }
}

const disconnect = () => {
  isIntentionalClose = true

  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout)
    reconnectTimeout = null
  }

  if (apiErrorTimer) {
    clearTimeout(apiErrorTimer)
    apiErrorTimer = null
  }

  if (ws.value) {
    ws.value.close()
    ws.value = null
  }
  connected.value = false
  connecting.value = false

  // Clear pending connection timeout
  if (connectTimeout) {
    clearTimeout(connectTimeout)
    connectTimeout = null
  }

  // Unsubscribe from network changes
  if (unsubscribeNetwork) {
    unsubscribeNetwork()
    unsubscribeNetwork = null
  }
}

const send = (data: string) => {
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify({ type: 'input', data }))
  }
}

const sendRaw = (message: object) => {
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify(message))
  }
}

const resize = (cols: number, rows: number) => {
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify({ type: 'resize', cols, rows }))
  }
}

// Scroll mode functions
const enterScrollMode = () => {
  if (!connected.value) return
  sendRaw({ type: 'scroll_mode', action: 'enter' })
}

const sendScrollCommand = (direction: 'up' | 'down', page: boolean = false) => {
  if (!connected.value) return
  sendRaw({ type: 'scroll', direction, page })
}

// Handle wheel events for scroll mode
const handleWheel = (event: WheelEvent) => {
  if (!xterm.value) return

  const buffer = xterm.value.buffer.active

  // Check if we should enter scroll mode (scrolling up at buffer top)
  if (event.deltaY < 0 && buffer.viewportY === 0) {
    // Scrolling up at buffer top → enter scroll mode
    enterScrollMode()
    event.preventDefault()
    event.stopPropagation()
    event.stopImmediatePropagation()

    const direction = event.deltaY > 0 ? 'down' : 'up'
    sendScrollCommand(direction)
    return
  }

  // Normal scrolling within xterm buffer
  event.preventDefault()
  event.stopPropagation()
  event.stopImmediatePropagation()

  const scrollAmount = Math.sign(event.deltaY)
  xterm.value.scrollLines(scrollAmount)
}

const initTerminal = () => {
  if (!terminalRef.value) return

  if (xterm.value) {
    xterm.value.dispose()
    xterm.value = null
  }

  xterm.value = new XTerminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    scrollback: 1000,
    allowTransparency: false,
    convertEol: true,
    theme: getXtermTheme(mainStore.theme)
  })

  fitAddon.value = new FitAddon()
  xterm.value.loadAddon(fitAddon.value)
  xterm.value.open(terminalRef.value)

  // Register wheel event handler for local scrolling
  wheelHandler = handleWheel
  const viewportElement = terminalRef.value.querySelector('.xterm-viewport') as HTMLElement
  if (viewportElement) {
    viewportElement.addEventListener('wheel', wheelHandler, { passive: false, capture: true })
  }

  // Handle user input - filter out PageUp/PageDown
  xterm.value.onData((data: string) => {
    // PageUp: \x1b[5~ or \x1b[5;~ (with modifiers)
    // PageDown: \x1b[6~ or \x1b[6;~ (with modifiers)
    if (data === '\x1b[5~' || data === '\x1b[6~' ||
        data.startsWith('\x1b[5;') || data.startsWith('\x1b[6;')) {
      // Skip sending PageUp/PageDown to backend - handled by onKey
      return
    }
    send(data)
  })

  // Handle PageUp/PageDown keys for scroll mode
  xterm.value.onKey(({ key, domEvent }) => {
    const isPageUp = domEvent.code === 'PageUp' || key === '\x1b[5~'
    const isPageDown = domEvent.code === 'PageDown' || key === '\x1b[6~'

    if (isPageUp) {
      enterScrollMode()
      sendScrollCommand('up', true)
      domEvent.preventDefault()
    } else if (isPageDown) {
      sendScrollCommand('down', true)
      domEvent.preventDefault()
    }
  })

  // Send initial dimensions to backend
  fitAddon.value.fit()
  if (xterm.value) {
    resize(xterm.value.cols, xterm.value.rows)
  }

  // Handle terminal resize events
  xterm.value.onResize(({ cols, rows }) => {
    resize(cols, rows)
  })

  // Clear and show connecting message
  xterm.value.clear()
  xterm.value.writeln('\x1b[33mWaiting for network detection...\x1b[0m')

  // Setup network change listener
  unsubscribeNetwork = wsNetworkManager.onWsBaseChange((_base: string, type: AddressType) => {
    console.log(`[GlobalTerminal] Network changed to ${type}, reconnecting...`)
    connectionType.value = type

    // Immediately reconnect if connected or connecting
    if (connected.value || connecting.value) {
      if (ws.value) {
        ws.value.close()
        ws.value = null
      }
      connected.value = false
      connecting.value = false

      // Reconnect after short delay
      if (token.value) {
        setTimeout(() => {
          xterm.value?.writeln('\x1b[33mReconnecting...\x1b[0m')
          connect()
        }, 100)
      }
    }
  })

  // Delayed connection (3 seconds to allow network detection)
  connectTimeout = setTimeout(() => {
    if (xterm.value) {
      xterm.value.clear()
      xterm.value.writeln('\x1b[33mConnecting to global terminal...\x1b[0m')
    }
    connect()
  }, 3000)
}

const handleResize = () => {
  nextTick(() => {
    // Check if container has actual dimensions (works for fixed-positioned elements too)
    if (!containerRef.value || containerRef.value.offsetWidth === 0 || containerRef.value.offsetHeight === 0) return
    fitAddon.value?.fit()
    if (xterm.value) {
      const cols = xterm.value.cols
      const rows = xterm.value.rows
      resize(cols, rows)
    }
  })
}

// Drag handling (for title bar)
const startDrag = (e: MouseEvent) => {
  if ((e.target as HTMLElement).closest('.close-btn, .resize-handle')) return
  if (isMobile.value) return

  isDragging.value = true
  dragOffset.value = {
    x: e.clientX - store.position.x,
    y: e.clientY - store.position.y
  }
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', endDrag)
}

const onDrag = (e: MouseEvent) => {
  if (!isDragging.value) return

  let newX = e.clientX - dragOffset.value.x
  let newY = e.clientY - dragOffset.value.y

  // Boundary constraints - keep at least 50px visible
  const minX = 50 - store.size.width
  const maxX = window.innerWidth - 50
  const minY = 0
  const maxY = window.innerHeight - 50

  newX = Math.max(minX, Math.min(maxX, newX))
  newY = Math.max(minY, Math.min(maxY, newY))

  store.setPosition({ x: newX, y: newY })
}

const endDrag = () => {
  if (isDragging.value) {
    isDragging.value = false
    store.saveToStorage()
    handleResize()
  }
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', endDrag)
}

// Edge resize handling
const startResize = (e: MouseEvent, edge: string) => {
  if (isMobile.value) return

  e.preventDefault()
  e.stopPropagation()

  isResizing.value = true
  resizeEdge.value = edge
  resizeStart.value = {
    x: e.clientX,
    y: e.clientY,
    width: store.size.width,
    height: store.size.height,
    posX: store.position.x,
    posY: store.position.y
  }

  document.addEventListener('mousemove', onResize)
  document.addEventListener('mouseup', endResize)
}

const onResize = (e: MouseEvent) => {
  if (!isResizing.value || !resizeEdge.value) return

  const dx = e.clientX - resizeStart.value.x
  const dy = e.clientY - resizeStart.value.y
  const minSize = 300
  const maxWidth = window.innerWidth
  const maxHeight = window.innerHeight

  let newWidth = resizeStart.value.width
  let newHeight = resizeStart.value.height
  let newX = resizeStart.value.posX
  let newY = resizeStart.value.posY

  const edge = resizeEdge.value

  // Handle horizontal resize
  if (edge.includes('right')) {
    newWidth = Math.max(minSize, Math.min(maxWidth - newX, resizeStart.value.width + dx))
  }
  if (edge.includes('left')) {
    const potentialWidth = resizeStart.value.width - dx
    if (potentialWidth >= minSize) {
      newWidth = potentialWidth
      newX = resizeStart.value.posX + dx
    }
  }

  // Handle vertical resize
  if (edge.includes('bottom')) {
    newHeight = Math.max(minSize, Math.min(maxHeight - newY, resizeStart.value.height + dy))
  }
  if (edge.includes('top')) {
    const potentialHeight = resizeStart.value.height - dy
    if (potentialHeight >= minSize) {
      newHeight = potentialHeight
      newY = resizeStart.value.posY + dy
    }
  }

  store.setSize({ width: newWidth, height: newHeight })
  store.setPosition({ x: newX, y: newY })
}

const endResize = () => {
  if (isResizing.value) {
    isResizing.value = false
    resizeEdge.value = null
    store.saveToStorage()
    handleResize()
  }
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', endResize)
}

// Mobile detection
const checkMobile = () => {
  isMobile.value = window.innerWidth < 768
}

// Ensure terminal is within viewport, center if outside
const ensureInViewport = () => {
  if (isMobile.value) return

  const { position, size } = store
  const windowWidth = window.innerWidth
  const windowHeight = window.innerHeight

  // Check if terminal is outside viewport (extends beyond edges)
  const isOutside =
    position.x < 0 ||
    position.y < 0 ||
    position.x + size.width > windowWidth ||
    position.y + size.height > windowHeight

  // Check if terminal can fit in viewport and should be centered
  const canFitInViewport = size.width <= windowWidth && size.height <= windowHeight

  // If terminal is outside OR if it's at the edge (was pushed there by smaller window)
  // and now has room to be centered, re-center it
  const isAtEdge = position.x <= 0 || position.y <= 0

  if (isOutside || (canFitInViewport && isAtEdge)) {
    // Center the terminal, ensuring it stays within viewport
    const newX = Math.max(0, Math.min((windowWidth - size.width) / 2, windowWidth - size.width))
    const newY = Math.max(0, Math.min((windowHeight - size.height) / 2, windowHeight - size.height))
    store.setPosition({ x: newX, y: newY })
    store.saveToStorage()
    handleResize()
  }
}

// Watch visibility
watch(() => store.visible, (show) => {
  if (show) {
    store.loadFromStorage()
    nextTick(() => {
      initTerminal()
    })
  } else {
    disconnect()
    if (xterm.value) {
      try {
        xterm.value.dispose()
      } catch (error) {
        console.warn('[GlobalTerminal] Disposed with warnings:', error)
      }
      xterm.value = null
    }
  }
})

// Watch theme changes
watch(() => mainStore.theme, (newTheme) => {
  if (xterm.value) {
    try {
      xterm.value.options.theme = getXtermTheme(newTheme)
    } catch (error) {
      console.warn('[GlobalTerminal] Failed to update theme:', error)
    }
  }
})

onMounted(() => {
  store.loadFromStorage()
  window.addEventListener('resize', handleResize)
  window.addEventListener('resize', checkMobile)
  window.addEventListener('resize', ensureInViewport)

  // Use ResizeObserver to detect container size changes
  resizeObserver.value = new ResizeObserver(() => {
    if (containerRef.value && containerRef.value.offsetParent !== null) {
      if (resizeTimeout) clearTimeout(resizeTimeout)

      let retries = 0
      const maxRetries = 5
      const retryFit = () => {
        handleResize()
        retries++
        if (retries < maxRetries) {
          resizeTimeout = setTimeout(retryFit, 50 * retries)
        }
      }
      resizeTimeout = setTimeout(retryFit, 10)
    }
  })

  if (containerRef.value) {
    resizeObserver.value.observe(containerRef.value)
  }
})

onUnmounted(() => {
  if (resizeTimeout) clearTimeout(resizeTimeout)
  if (apiErrorTimer) clearTimeout(apiErrorTimer)

  // Clean up wheel event listener
  if (wheelHandler && terminalRef.value) {
    const viewportElement = terminalRef.value.querySelector('.xterm-viewport') as HTMLElement
    if (viewportElement) {
      viewportElement.removeEventListener('wheel', wheelHandler, { capture: true } as EventListenerOptions)
    }
  }

  disconnect()
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('resize', checkMobile)
  window.removeEventListener('resize', ensureInViewport)
  resizeObserver.value?.disconnect()

  if (xterm.value) {
    try {
      xterm.value.dispose()
    } catch (error) {
      // Ignore errors from disposing addons that weren't loaded
    }
    xterm.value = null
  }

  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', endDrag)
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', endResize)
})
</script>

<template>
  <div
    v-if="store.visible"
    ref="containerRef"
    :class="['fixed bg-main border border-main shadow-xl flex flex-col select-none', `theme-${mainStore.theme}`, { 'mobile-fullscreen': isMobile }]"
    :style="isMobile ? {} : {
      left: `${store.position.x}px`,
      top: `${store.position.y}px`,
      width: `${store.size.width}px`,
      height: `${store.size.height}px`,
      zIndex: 40
    }"
  >
    <!-- Title bar -->
    <div
      @mousedown="startDrag"
      class="flex items-center justify-between px-3 py-2 bg-sub border-b border-main cursor-move"
    >
      <div class="flex items-center gap-2">
        <span class="text-sm font-medium text-main">Global Terminal</span>
        <span
          :class="[
            'w-2 h-2 rounded-full',
            connected ? 'bg-green-500' : connecting ? 'bg-yellow-500 animate-pulse' : 'bg-gray-500'
          ]"
        ></span>
        <span class="text-xs text-sub">
          {{ connecting ? 'Connecting...' : connected ? 'Connected' : 'Disconnected' }}
        </span>

        <!-- LAN/Public indicator -->
        <span
          v-if="connected"
          :class="[
            'connection-type-badge text-xs px-1 rounded',
            connectionType === 'lan' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'
          ]"
        >
          {{ connectionType === 'lan' ? 'LAN' : 'WAN' }}
        </span>
      </div>
      <button
        @click="store.hide()"
        class="close-btn p-1 rounded hover:bg-tertiary text-sub hover:text-main"
        title="Close"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Terminal content -->
    <div ref="terminalRef" class="flex-1 overflow-hidden"></div>

    <!-- Resize handles (hidden on mobile) -->
    <template v-if="!isMobile">
      <!-- Edge handles -->
      <div class="resize-handle resize-top" @mousedown="startResize($event, 'top')"></div>
      <div class="resize-handle resize-bottom" @mousedown="startResize($event, 'bottom')"></div>
      <div class="resize-handle resize-left" @mousedown="startResize($event, 'left')"></div>
      <div class="resize-handle resize-right" @mousedown="startResize($event, 'right')"></div>
      <!-- Corner handles -->
      <div class="resize-handle resize-corner resize-tl" @mousedown="startResize($event, 'top-left')"></div>
      <div class="resize-handle resize-corner resize-tr" @mousedown="startResize($event, 'top-right')"></div>
      <div class="resize-handle resize-corner resize-bl" @mousedown="startResize($event, 'bottom-left')"></div>
      <div class="resize-handle resize-corner resize-br" @mousedown="startResize($event, 'bottom-right')"></div>
    </template>
  </div>
</template>

<style scoped>
/* Mobile fullscreen */
.mobile-fullscreen {
  inset: 0 !important;
  width: 100% !important;
  height: 100% !important;
}

/* Terminal styles */
:deep(.xterm) {
  height: 100%;
  padding: 0 !important;
}

:deep(.xterm-viewport) {
  background-color: #ffffff !important;
}

:deep(.xterm-screen) {
  background-color: #ffffff;
}

/* Theme-specific backgrounds */
.theme-dark :deep(.xterm-viewport) {
  background-color: #1e1e1e !important;
}
.theme-dark :deep(.xterm-screen) {
  background-color: #1e1e1e;
}

.theme-light :deep(.xterm-viewport) {
  background-color: #ffffff !important;
}
.theme-light :deep(.xterm-screen) {
  background-color: #ffffff;
}

.theme-green :deep(.xterm-viewport) {
  background-color: #c7edcc !important;
}
.theme-green :deep(.xterm-screen) {
  background-color: #c7edcc;
}

.theme-parchment :deep(.xterm-viewport) {
  background-color: #f4ecd8 !important;
}
.theme-parchment :deep(.xterm-screen) {
  background-color: #f4ecd8;
}

/* Hide xterm scrollbars */
:deep(.xterm-scrollbar-horizontal),
:deep(.xterm-scrollbar-vertical),
:deep(.xterm .scrollbar) {
  display: none !important;
}

/* Make xterm-screen fill the full width */
:deep(.xterm-screen) {
  width: 100% !important;
}

:deep(.xterm-rows > div) {
  width: 100% !important;
}

/* Hide cursor artifacts */
:deep(.xterm-cursor::after) {
  content: '';
}

/* Resize handles */
.resize-handle {
  position: absolute;
  z-index: 10;
}

.resize-top,
.resize-bottom {
  left: 8px;
  right: 8px;
  height: 6px;
  cursor: ns-resize;
}

.resize-top {
  top: -3px;
}

.resize-bottom {
  bottom: -3px;
}

.resize-left,
.resize-right {
  top: 8px;
  bottom: 8px;
  width: 6px;
  cursor: ew-resize;
}

.resize-left {
  left: -3px;
}

.resize-right {
  right: -3px;
}

.resize-corner {
  width: 12px;
  height: 12px;
}

.resize-tl {
  top: -6px;
  left: -6px;
  cursor: nwse-resize;
}

.resize-tr {
  top: -6px;
  right: -6px;
  cursor: nesw-resize;
}

.resize-bl {
  bottom: -6px;
  left: -6px;
  cursor: nesw-resize;
}

.resize-br {
  bottom: -6px;
  right: -6px;
  cursor: nwse-resize;
}
</style>
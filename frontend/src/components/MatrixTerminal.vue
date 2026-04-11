<!-- frontend/src/components/MatrixTerminal.vue -->
<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { Terminal as XTerminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { useMainStore, type ThemeName } from '@/store'
import { useAuth } from '@/composables/useAuth'
import { wsNetworkManager } from '@/utils/wsNetworkManager'
import type { AddressType } from '@/types/network'

interface Props {
  index: number
  title: string
  isSelected: boolean
  sessionName: string
  taskId?: string
  mode: 'tasks' | 'sessions'
}

const props = defineProps<Props>()
const emit = defineEmits<{
  select: [index: number]
}>()

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

// Scroll mode state
const scrollMode = ref(false)

// Theme configurations
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

// Compute display title
const displayTitle = computed(() => {
  if (props.title) return props.title
  return `Terminal ${props.index + 1}`
})

// Compute badge number (1-indexed)
const badgeNumber = computed(() => props.index + 1)

// Get WebSocket URL based on mode (using wsNetworkManager)
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

  // Add path based on mode
  if (props.mode === 'tasks' && props.taskId) {
    return `${wsBase}/terminal?token=${token.value}&task_id=${props.taskId}`
  } else if (props.mode === 'sessions') {
    return `${wsBase}/matrix-terminal?token=${token.value}&index=${props.index}&session=${props.sessionName}`
  }

  return ''
}

const connect = () => {
  if (ws.value) {
    ws.value.close()
    ws.value = null
  }

  if (!token.value) return

  const wsUrl = getWsUrl()
  if (!wsUrl) {
    xterm.value?.writeln('\x1b[31mError: Invalid terminal configuration\x1b[0m')
    return
  }

  connecting.value = true
  connectionType.value = wsNetworkManager.getType()

  try {
    ws.value = new WebSocket(wsUrl)

    ws.value.onopen = () => {
      connected.value = true
      connecting.value = false
      if (xterm.value) {
        xterm.value.clear()
        resize(xterm.value.cols, xterm.value.rows)
        xterm.value.writeln('\x1b[32m✓ Connected\x1b[0m')
      }
    }

    ws.value.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'output') {
          xterm.value?.write(msg.data)
        } else if (msg.type === 'error') {
          xterm.value?.writeln(`\x1b[31mError: ${msg.message}\x1b[0m`)
        } else if (msg.type === 'scroll_mode') {
          scrollMode.value = msg.active
        }
      } catch {
        xterm.value?.write(event.data)
      }
    }

    ws.value.onerror = () => {
      connecting.value = false
      xterm.value?.writeln('\x1b[31mConnection error\x1b[0m')
    }

    ws.value.onclose = () => {
      connected.value = false
      connecting.value = false
      scrollMode.value = false
      ws.value = null
    }
  } catch (err: any) {
    connecting.value = false
    xterm.value?.writeln(`\x1b[31mFailed to connect: ${err.message}\x1b[0m`)
  }
}

const disconnect = () => {
  if (ws.value) {
    ws.value.close()
    ws.value = null
  }
  connected.value = false
  connecting.value = false
  scrollMode.value = false

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
  // Only send input when this terminal is selected
  if (!props.isSelected) return
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify({ type: 'input', data }))
  }
}

const sendRaw = (message: object) => {
  // Only send when this terminal is selected
  if (!props.isSelected) return
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
  if (!connected.value || !props.isSelected) return
  sendRaw({ type: 'scroll_mode', action: 'enter' })
}

const sendScrollCommand = (direction: 'up' | 'down', page: boolean = false) => {
  if (!connected.value || !props.isSelected) return
  sendRaw({ type: 'scroll', direction, page })
}

// Handle wheel events for scroll mode
const handleWheel = (event: WheelEvent) => {
  if (!xterm.value || !props.isSelected) return

  const buffer = xterm.value.buffer.active

  // Check if we should enter scroll mode (scrolling up at buffer top)
  if (event.deltaY < 0 && buffer.viewportY === 0) {
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

// Handle click to select
const handleClick = () => {
  emit('select', props.index)
}

const initTerminal = () => {
  if (!terminalRef.value) return

  if (xterm.value) {
    xterm.value.dispose()
    xterm.value = null
  }

  xterm.value = new XTerminal({
    cursorBlink: true,
    fontSize: 12,
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

  // Handle user input - only when selected
  xterm.value.onData((data: string) => {
    // Filter out PageUp/PageDown
    if (data === '\x1b[5~' || data === '\x1b[6~' ||
        data.startsWith('\x1b[5;') || data.startsWith('\x1b[6;')) {
      return
    }
    send(data)
  })

  // Handle PageUp/PageDown keys for scroll mode
  xterm.value.onKey(({ key, domEvent }) => {
    if (!props.isSelected) return

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
    console.log(`[MatrixTerminal] Network changed to ${type}, reconnecting...`)
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
      xterm.value.writeln('\x1b[33mConnecting...\x1b[0m')
    }
    connect()
  }, 3000)
}

const handleResize = () => {
  nextTick(() => {
    if (!containerRef.value || containerRef.value.offsetWidth === 0 || containerRef.value.offsetHeight === 0) return
    fitAddon.value?.fit()
    if (xterm.value) {
      const cols = xterm.value.cols
      const rows = xterm.value.rows
      resize(cols, rows)
    }
  })
}

// Watch selection state - focus terminal when selected
watch(() => props.isSelected, (selected) => {
  if (selected && xterm.value) {
    xterm.value.focus()
  }
})

// Watch theme changes
watch(() => mainStore.theme, (newTheme) => {
  if (xterm.value) {
    try {
      xterm.value.options.theme = getXtermTheme(newTheme)
    } catch (error) {
      console.warn('[MatrixTerminal] Failed to update theme:', error)
    }
  }
})

onMounted(() => {
  initTerminal()
  window.addEventListener('resize', handleResize)

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

  // Clean up wheel event listener
  if (wheelHandler && terminalRef.value) {
    const viewportElement = terminalRef.value.querySelector('.xterm-viewport') as HTMLElement
    if (viewportElement) {
      viewportElement.removeEventListener('wheel', wheelHandler, { capture: true } as EventListenerOptions)
    }
  }

  disconnect()
  window.removeEventListener('resize', handleResize)
  resizeObserver.value?.disconnect()

  if (xterm.value) {
    try {
      xterm.value.dispose()
    } catch (error) {
      // Ignore errors from disposing addons that weren't loaded
    }
    xterm.value = null
  }
})
</script>

<template>
  <div
    ref="containerRef"
    :class="[
      'matrix-terminal flex flex-col bg-main border border-main overflow-hidden select-none cursor-pointer',
      `theme-${mainStore.theme}`,
      { 'selected': isSelected }
    ]"
    @click="handleClick"
  >
    <!-- Header with badge, title, and status -->
    <div class="terminal-header flex items-center gap-2 px-2 py-1 bg-sub border-b border-main">
      <!-- Number badge (1-indexed) -->
      <span
        :class="[
          'badge min-w-[20px] h-5 flex items-center justify-center rounded text-xs font-bold',
          isSelected ? 'bg-blue-500 text-white' : 'bg-gray-500 text-gray-200'
        ]"
      >
        {{ badgeNumber }}
      </span>

      <!-- Title -->
      <span class="title text-sm font-medium text-main truncate flex-1">
        {{ displayTitle }}
      </span>

      <!-- Scroll mode indicator -->
      <span
        v-if="scrollMode"
        class="scroll-mode-indicator text-xs text-amber-500 font-medium"
      >
        Scroll Mode
      </span>

      <!-- Connection status indicator -->
      <span
        :class="[
          'status-dot w-2 h-2 rounded-full',
          connected ? 'bg-green-500' : connecting ? 'bg-yellow-500 animate-pulse' : 'bg-gray-500'
        ]"
      ></span>

      <!-- LAN/Public indicator -->
      <span
        v-if="connected"
        :class="[
          'connection-type-badge text-xs px-1 rounded',
          connectionType === 'lan' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'
        ]"
      >
        {{ connectionType === 'lan' ? 'LAN' : '公网' }}
      </span>
    </div>

    <!-- Terminal content -->
    <div ref="terminalRef" class="terminal-content flex-1 overflow-hidden"></div>
  </div>
</template>

<style scoped>
.matrix-terminal {
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.matrix-terminal.selected {
  border-color: #3b82f6;
  box-shadow: 0 0 0 1px #3b82f6 inset;
}

.matrix-terminal:not(.selected) {
  opacity: 0.85;
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
</style>
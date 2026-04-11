<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Terminal as XTerminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { useWebSocket } from '@/composables/useWebSocket'
import { useMainStore, type ThemeName } from '@/store'
import terminalsApi from '@/api/terminals'
import HistoryViewer from './HistoryViewer.vue'
import QueueModal from './QueueModal.vue'
import CommandPresetsModal from './CommandPresetsModal.vue'
import QuickInputModal from './QuickInputModal.vue'
import MultiLineInputModal from './MultiLineInputModal.vue'
import UploadModal from './UploadModal.vue'

interface Props {
  taskId: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  connected: []
  disconnected: []
}>()

const store = useMainStore()

// View mode state
const viewMode = ref<'terminal' | 'history'>('terminal')
const historyContent = ref('')
const loadingHistory = ref(false)
const historyError = ref('')
const showQueueModal = ref(false)
const showCommandPresets = ref(false)
const showQuickInput = ref(false)
const showMultiLineInput = ref(false)
const showUploadModal = ref(false)

const terminalRef = ref<HTMLElement | null>(null)
const containerRef = ref<HTMLElement | null>(null)
const xterm = ref<XTerminal | null>(null)
const fitAddon = ref<FitAddon | null>(null)
const resizeObserver = ref<ResizeObserver | null>(null)
let resizeTimeout: ReturnType<typeof setTimeout> | null = null
let wheelHandler: ((e: WheelEvent) => void) | null = null

const { connected, connecting, connectionType, delayedConnect, setupNetworkListener, disconnect, send, sendRaw, resize } = useWebSocket(props.taskId)

// Theme configurations for xterm.js
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

// Control bar button handlers
const sendDirection = (direction: 'up' | 'down' | 'left' | 'right') => {
  if (!connected.value) return
  const escapeCodes: Record<string, string> = {
    up: '\x1b[A',
    down: '\x1b[B',
    left: '\x1b[D',
    right: '\x1b[C'
  }
  send(escapeCodes[direction])
}

// Scroll mode functions - just send commands to backend, no state tracking
const enterScrollMode = () => {
  if (!connected.value) return
  sendRaw({ type: 'scroll_mode', action: 'enter' })
}

const sendScrollCommand = (direction: 'up' | 'down', page: boolean = false) => {
  if (!connected.value) return
  // Send scroll command to backend which uses tmux send-keys
  sendRaw({ type: 'scroll', direction, page })
}

// Page Up/Down button handlers
const handlePageUp = () => {
  if (!connected.value) return
  // Enter scroll mode then scroll up one page
  enterScrollMode()
  sendScrollCommand('up', true)
}

const handlePageDown = () => {
  if (!connected.value) return
  sendScrollCommand('down', true)
}

// Handle wheel events for local scrolling and scroll mode
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

const handleQuickInputSend = async (content: string) => {
  if (!connected.value) return
  // Keep modal open for continuous input, then send with delay
  await nextTick()
  try {
    send(content)
    await new Promise(resolve => setTimeout(resolve, 500))
    send('\r')
  } catch (error) {
    console.error('Error sending quick input:', error)
  }
}

const handleMultiLineSend = (content: string) => {
  if (!connected.value) return
  send(content)
}

const handleInsertPath = (path: string) => {
  send(path)
}

const sendCommandWithDelay = async (command: string) => {
  if (!connected.value) return
  send(command)
  await new Promise(resolve => setTimeout(resolve, 500))
  send('\r')
}

const loadHistory = async () => {
  loadingHistory.value = true
  historyError.value = ''
  try {
    historyContent.value = await terminalsApi.getHistoryAsText(props.taskId)
  } catch (err: any) {
    historyError.value = err.message || 'Failed to load terminal history'
    console.error('Failed to load history:', err)
  }
  loadingHistory.value = false
}

const handleViewHistory = async () => {
  await loadHistory()
  if (!historyError.value) {
    viewMode.value = 'history'
  }
}

const handleBackToTerminal = () => {
  viewMode.value = 'terminal'
}

const initTerminal = () => {
  if (!terminalRef.value) return

  // Clean up existing terminal if any
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
    theme: getXtermTheme(store.theme)
  })

  fitAddon.value = new FitAddon()
  xterm.value.loadAddon(fitAddon.value)

  xterm.value.open(terminalRef.value)
  fitAddon.value.fit()

  // Register wheel event handler for local scrolling on the viewport element
  // Use capture phase to intercept before xterm.js internal handler
  wheelHandler = handleWheel
  const viewportElement = terminalRef.value.querySelector('.xterm-viewport') as HTMLElement
  if (viewportElement) {
    viewportElement.addEventListener('wheel', wheelHandler, { passive: false, capture: true })
  }

  // Handle user input
  // Filter out PageUp/PageDown keys - they are handled by onKey handler below
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

  // Handle special keys for scroll mode (Page Up/Down)
  // Use domEvent.code for reliable cross-browser detection
  xterm.value.onKey(({ key, domEvent }) => {
    const isPageUp = domEvent.code === 'PageUp' || key === '\x1b[5~'
    const isPageDown = domEvent.code === 'PageDown' || key === '\x1b[6~'

    if (isPageUp) {
      // Enter scroll mode then scroll up one page
      enterScrollMode()
      sendScrollCommand('up', true)
      domEvent.preventDefault()
    } else if (isPageDown) {
      // Scroll down one page
      sendScrollCommand('down', true)
      domEvent.preventDefault()
    }
  })

  // Send initial dimensions to backend
  const initialCols = xterm.value.cols
  const initialRows = xterm.value.rows
  resize(initialCols, initialRows)

  // Handle terminal resize events
  xterm.value.onResize(({ cols, rows }) => {
    resize(cols, rows)
  })

  // Setup network change listener for auto-reconnect
  setupNetworkListener()

  // Delayed connect (3 seconds to allow network detection to complete)
  xterm.value.writeln('\x1b[33mWaiting for network detection...\x1b[0m')
  delayedConnect(3000, (data: string) => {
    xterm.value?.write(data)
  })

  // Watch connection status
  watch(connected, (isConnected) => {
    if (isConnected) {
      emit('connected')
      // Clear terminal and send reset command to clean up any artifacts
      xterm.value?.clear()
      send('\x1bc') // Reset terminal (RIS - Reset to Initial State)
      setTimeout(() => {
        xterm.value?.writeln('\x1b[32m✓ Connected to terminal\x1b[0m')
      }, 100)
    }
  })

  watch(connecting, (isConnecting) => {
    if (isConnecting) {
      xterm.value?.writeln('\r\n\x1b[33mConnecting...\x1b[0m')
    }
  })

  // Watch theme changes and update xterm theme
  watch(() => store.theme, (newTheme) => {
    if (xterm.value) {
      try {
        xterm.value.options.theme = getXtermTheme(newTheme)
      } catch (error) {
        console.warn('[Terminal] Failed to update theme:', error)
      }
    }
  })
}

const handleResize = () => {
  nextTick(() => {
    // Only resize if the container has actual dimensions (not hidden with v-show)
    if (!containerRef.value || containerRef.value.offsetParent === null) {
      return
    }

    fitAddon.value?.fit()
    // Update backend with new dimensions
    if (xterm.value) {
      const cols = xterm.value.cols
      const rows = xterm.value.rows
      console.log(`[Terminal] FitAddon calculated size: ${cols}x${rows}, container offsetWidth: ${containerRef.value.offsetWidth}`)
      resize(cols, rows)
    }
  })
}

onMounted(() => {
  initTerminal()
  window.addEventListener('resize', handleResize)

  // Use ResizeObserver to detect when container becomes visible or changes size
  resizeObserver.value = new ResizeObserver(() => {
    // Check if container is visible
    if (containerRef.value && containerRef.value.offsetParent !== null) {
      // Debounce and retry fit to handle layout timing issues
      if (resizeTimeout) clearTimeout(resizeTimeout)

      // When container becomes visible or changes size, retry fit multiple times
      // with increasing delays to ensure the layout is complete
      let retries = 0
      const maxRetries = 5
      const retryFit = () => {
        handleResize()
        retries++
        if (retries < maxRetries) {
          resizeTimeout = setTimeout(retryFit, 50 * retries) // 50ms, 100ms, 150ms...
        }
      }
      resizeTimeout = setTimeout(retryFit, 10)
    }
  })

  // Observe the container to detect when it becomes visible (v-show changes)
  if (containerRef.value) {
    resizeObserver.value.observe(containerRef.value)
  }

  // Also observe window resize on the parent element (the v-show div)
  // We need to wait a bit and check parent since it might not be available yet
  nextTick(() => {
    const parentElement = containerRef.value?.parentElement as HTMLElement
    if (parentElement && resizeObserver.value) {
      resizeObserver.value.observe(parentElement)
    }
  })
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

  // Dispose xterm.js instance
  if (xterm.value) {
    try {
      xterm.value.dispose()
    } catch (error) {
      // Ignore errors from disposing addons that weren't loaded
      console.warn('[Terminal] Disposed with warnings:', error)
    }
    xterm.value = null
  }
})
</script>

<template>
  <div ref="containerRef" class="terminal-container h-full flex flex-col bg-main">
    <!-- Terminal view -->
    <div v-show="viewMode === 'terminal'" class="flex flex-col h-full">
      <div class="terminal-header flex items-center px-4 py-2 bg-sub border-b border-main">
        <div class="terminal-status flex items-center gap-2">
          <span
            :class="[
              'terminal-status-dot w-2 h-2 rounded-full',
              connected ? 'bg-green-500' : connecting ? 'bg-yellow-500 animate-pulse' : 'bg-gray-500'
            ]"
          ></span>
          <span class="text-sm text-sub">{{ connecting ? 'Connecting...' : connected ? 'Connected' : 'Disconnected' }}</span>

          <!-- LAN/Public indicator -->
          <span
            v-if="connected"
            :class="[
              'connection-type-badge text-xs px-1.5 py-0.5 rounded',
              connectionType === 'lan' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'
            ]"
          >
            {{ connectionType === 'lan' ? 'LAN' : '公网' }}
          </span>
        </div>
      </div>
      <div ref="terminalRef" class="flex-1 overflow-hidden"></div>

    <!-- Control bar - two rows layout -->
    <div class="terminal-controls flex flex-col gap-2 px-4 py-3 bg-sub border-t border-main">
      <!-- First row: PgUp, ↑, PgDn, A, B, C, D, Tab, ENTER, Go, ABC -->
      <div class="control-row flex flex-wrap items-center gap-2">
        <!-- Direction keys: PgUp, Up, PgDn -->
        <button
          @click="handlePageUp"
          :disabled="!connected"
          class="control-btn control-btn-direction"
          title="Page Up - Enter scroll mode or scroll up"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 9l7-7 7 7" />
          </svg>
        </button>
        <button
          @click="sendDirection('up')"
          :disabled="!connected"
          class="control-btn control-btn-direction"
          title="Up arrow"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
          </svg>
        </button>
        <button
          @click="handlePageDown"
          :disabled="!connected"
          class="control-btn control-btn-direction"
          title="Page Down - Scroll down"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 15l-7 7-7-7" />
          </svg>
        </button>

        <!-- Letters A-D -->
        <button
          v-for="letter in ['A', 'B', 'C', 'D']"
          :key="letter"
          @click="send(letter)"
          :disabled="!connected"
          class="control-btn control-btn-action"
          :title="`Send ${letter}`"
        >
          {{ letter }}
        </button>

        <!-- Tab (Shift+Tab) -->
        <button
          @click="send('\x1b[Z')"
          :disabled="!connected"
          class="control-btn control-btn-action"
          title="Send Shift+Tab"
        >
          TAB
        </button>

        <!-- ENTER -->
        <button
          @click="send('\r')"
          :disabled="!connected"
          class="control-btn control-btn-action"
          title="Send Enter key"
        >
          ENTER
        </button>

        <!-- Go button -->
        <button
          @click="send('Go')"
          :disabled="!connected"
          class="control-btn control-btn-action"
          title="Send 'Go'"
        >
          GO
        </button>

        <!-- ABC panel button (includes ESC, Ctrl+C, INPUT) -->
        <button
          @click="showQuickInput = true"
          :disabled="!connected"
          class="control-btn control-btn-action"
          title="Quick input - ESC, Ctrl+C, INPUT"
        >
          ABC
        </button>
      </div>

      <!-- Second row: ←, ↓, →, 1, 2, 3, 4, UPLOAD, LOG, CMD, TODO -->
      <div class="control-row flex flex-wrap items-center gap-2">
        <!-- Direction keys: Left, Down, Right -->
        <button
          @click="sendDirection('left')"
          :disabled="!connected"
          class="control-btn control-btn-direction"
          title="Left arrow"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <button
          @click="sendDirection('down')"
          :disabled="!connected"
          class="control-btn control-btn-direction"
          title="Down arrow"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        <button
          @click="sendDirection('right')"
          :disabled="!connected"
          class="control-btn control-btn-direction"
          title="Right arrow"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </button>

        <!-- Numbers 1-4 -->
        <button
          v-for="num in ['1', '2', '3', '4']"
          :key="num"
          @click="send(num)"
          :disabled="!connected"
          class="control-btn control-btn-action"
          :title="`Send ${num}`"
        >
          {{ num }}
        </button>

        <!-- UPLOAD -->
        <button
          @click="showUploadModal = true"
          :disabled="!connected"
          class="control-btn control-btn-action"
          title="Upload files to temp directory"
        >
          UPLOAD
        </button>

        <!-- LOG -->
        <button
          @click="handleViewHistory"
          :disabled="loadingHistory || !connected"
          class="control-btn control-btn-action"
          title="View terminal history"
        >
          <span v-if="loadingHistory" class="spinner-small"></span>
          <span v-else>LOG</span>
        </button>

        <!-- CMD -->
        <button
          @click="showCommandPresets = true"
          :disabled="!connected"
          class="control-btn control-btn-action"
          title="Command presets"
        >
          CMD
        </button>

        <!-- TODO -->
        <button
          @click="showQueueModal = true"
          :disabled="!connected"
          class="control-btn control-btn-action"
          title="Manage message queue"
        >
          TODO
        </button>
      </div>
    </div>
    </div>

    <!-- History viewer -->
    <div v-show="viewMode === 'history'" class="h-full">
      <HistoryViewer
        v-if="!historyError"
        :content="historyContent"
        @close="handleBackToTerminal"
      />
      <div v-else class="flex-1 flex flex-col items-center justify-center text-gray-500 dark:text-gray-300">
        <div class="text-xl mb-4">Failed to load history</div>
        <div class="text-sm text-red-600 dark:text-red-400 mb-4">{{ historyError }}</div>
        <button @click="handleBackToTerminal" class="control-btn control-btn-action">
          Back to Terminal
        </button>
      </div>
    </div>
    <QueueModal
      v-if="showQueueModal"
      :task-id="taskId"
      @close="showQueueModal = false"
    />
    <CommandPresetsModal
      v-if="showCommandPresets"
      :connected="connected"
      @close="showCommandPresets = false"
      @execute="sendCommandWithDelay"
    />
    <QuickInputModal
      v-if="showQuickInput"
      :connected="connected"
      @close="showQuickInput = false"
      @send="handleQuickInputSend"
      @open-input="showQuickInput = false; showMultiLineInput = true"
    />
    <MultiLineInputModal
      v-if="showMultiLineInput"
      :connected="connected"
      @close="showMultiLineInput = false"
      @send="handleMultiLineSend"
    />
    <UploadModal
      v-if="showUploadModal"
      :task-id="taskId"
      @close="showUploadModal = false"
      @insert="handleInsertPath"
    />
  </div>
</template>

<style scoped>
.terminal-container :deep(.xterm) {
  height: 100%;
  padding: 0 !important;
}

.terminal-container :deep(.xterm .xterm-viewport) {
  background-color: #ffffff !important;
}
.dark .terminal-container :deep(.xterm .xterm-viewport) {
  background-color: #1e1e1e !important;
}

/* Hide cursor dots in empty areas */
.terminal-container :deep(.xterm-rows span:not(.xterm-cursor)):empty {
  display: none;
}

/* Ensure proper background */
.terminal-container :deep(.xterm-screen) {
  background-color: #ffffff;
}
.theme-dark .terminal-container :deep(.xterm-screen) {
  background-color: #1e1e1e;
}

/* Theme-specific xterm backgrounds */
.theme-light .terminal-container :deep(.xterm-viewport) {
  background-color: #ffffff !important;
}
.theme-light .terminal-container :deep(.xterm-screen) {
  background-color: #ffffff;
}
.theme-green .terminal-container :deep(.xterm-viewport) {
  background-color: #c7edcc !important;
}
.theme-green .terminal-container :deep(.xterm-screen) {
  background-color: #c7edcc;
}
.theme-parchment .terminal-container :deep(.xterm-viewport) {
  background-color: #f4ecd8 !important;
}
.theme-parchment .terminal-container :deep(.xterm-screen) {
  background-color: #f4ecd8;
}

/* Hide decoration layer dots */
.terminal-container :deep(.xterm-decoration-container) {
  display: none;
}

/* Hide xterm scrollbars */
.terminal-container :deep(.xterm-scrollbar-horizontal),
.terminal-container :deep(.xterm-scrollbar-vertical),
.terminal-container :deep(.xterm .scrollbar) {
  display: none !important;
}

/* Make xterm-screen fill the full width (compensate for hidden scrollbar space) */
.terminal-container :deep(.xterm-screen) {
  width: 100% !important;
}

/* Make row children fill the full width of xterm-rows */
.terminal-container :deep(.xterm-rows > div) {
  width: 100% !important;
}

/* Hide any remaining cursor artifacts */
.terminal-container :deep(.xterm-cursor::after) {
  content: '';
}

/* Control bar button styles */
.control-btn {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--bg-primary);
  color: var(--text-primary);
}

.control-btn-direction {
  width: 28px;
  height: 28px;
}

.control-btn-direction:hover:not(:disabled) {
  background-color: var(--bg-tertiary);
}
.control-btn-direction:active:not(:disabled) {
  background-color: var(--border-secondary);
}

.control-btn-action {
  min-width: 48px;
  height: 28px;
  padding: 0 8px;
  font-weight: 500;
}

.control-btn-action:hover:not(:disabled) {
  background-color: var(--bg-tertiary);
}
.control-btn-action:active:not(:disabled) {
  background-color: var(--border-secondary);
}

.control-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: var(--bg-tertiary);
  color: var(--text-muted);
}

/* Small spinner for button */
.spinner-small {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid #4a4a4e;
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin-small 0.6s linear infinite;
}

@keyframes spin-small {
  to {
    transform: rotate(360deg);
  }
}

/* Control row styles */
.control-row {
  flex-wrap: wrap;
}
</style>

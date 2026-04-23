# Global Terminal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent global terminal accessible from all pages with draggable panel UI.

**Architecture:** Backend adds a new router and WebSocket endpoint for a dedicated `v2d-global` tmux session. Frontend creates a Pinia store for panel state, a GlobalTerminal component with drag support, and icon buttons in each page's header.

**Tech Stack:** FastAPI WebSocket, tmux, Vue 3, Pinia, xterm.js

---

## File Structure

### Backend (new files)
- `backend/app/routers/global_terminal.py` - REST endpoint for session creation
- `backend/app/websocket/global_terminal.py` - WebSocket handler (no task dependency)

### Backend (modified files)
- `backend/app/main.py` - Register router and WebSocket endpoint

### Frontend (new files)
- `frontend/src/store/globalTerminal.ts` - Pinia store for panel state
- `frontend/src/components/GlobalTerminal.vue` - Draggable terminal panel
- `frontend/src/components/GlobalTerminalIcon.vue` - Header icon button

### Frontend (modified files)
- `frontend/src/App.vue` - Add GlobalTerminal component
- `frontend/src/views/ProjectsView.vue` - Add icon to header
- `frontend/src/views/TasksView.vue` - Add icon to header
- `frontend/src/views/CodeReviewView.vue` - Add icon to header

---

## Task 1: Backend - Global Terminal Router

**Files:**
- Create: `backend/app/routers/global_terminal.py`

- [ ] **Step 1: Create the global terminal router**

```python
# backend/app/routers/global_terminal.py
from fastapi import APIRouter, Depends
from app.services.tmux_service import TmuxService
from app.auth import require_auth

router = APIRouter(prefix="/api/global-terminal", tags=["global-terminal"])

GLOBAL_SESSION_NAME = "v2d-global"


@router.post("/session")
async def get_or_create_session(session = Depends(require_auth)):
    """Create or retrieve the global terminal tmux session."""
    tmux = TmuxService()
    exists = tmux.session_exists(GLOBAL_SESSION_NAME)

    if not exists:
        success, msg = tmux.create_session(GLOBAL_SESSION_NAME, "~")
        if not success:
            return {"session_name": GLOBAL_SESSION_NAME, "created": False, "error": msg}

    return {"session_name": GLOBAL_SESSION_NAME, "created": not exists}
```

- [ ] **Step 2: Register the router in main.py**

Add to `backend/app/main.py` after line 12 (after other router imports):

```python
from app.routers import auth, projects, tasks, files, git, terminals, queues, command_presets, filesystem, symbols, global_terminal
```

Add after line 69 (after symbols router):

```python
app.include_router(global_terminal.router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/global_terminal.py backend/app/main.py
git commit -m "feat(backend): add global terminal session endpoint

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Backend - Global Terminal WebSocket Handler

**Files:**
- Create: `backend/app/websocket/global_terminal.py`

- [ ] **Step 1: Create the global terminal WebSocket handler**

```python
# backend/app/websocket/global_terminal.py
import asyncio
import json
import pty
import os
import select
import subprocess
import fcntl
import struct
import logging
from typing import Optional
from fastapi import WebSocket, Query
from app.auth import verify_token
from app.services.tmux_service import TmuxService

logger = logging.getLogger(__name__)

SIZE_COLS = 80
SIZE_ROWS = 24
GLOBAL_SESSION_NAME = "v2d-global"


class GlobalWebSocketTerminal:
    """WebSocket terminal handler for the global tmux session"""

    def __init__(self, websocket: WebSocket, session_name: str = GLOBAL_SESSION_NAME):
        self.websocket = websocket
        self.session_name = session_name
        self.fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.running = False
        self.cols = SIZE_COLS
        self.rows = SIZE_ROWS

    async def start(self):
        """Start terminal session"""
        try:
            # Ensure tmux session exists
            if not TmuxService.session_exists(self.session_name):
                logger.info(f"Creating global tmux session: {self.session_name}")
                success, msg = TmuxService.create_session(self.session_name, "~")
                if not success:
                    logger.error(f"Failed to create global tmux session: {msg}")
                    await self.send_error(f"Failed to create tmux session: {msg}")
                    await self.close()
                    return

            # Create pseudoterminal
            self.fd, slave_fd = pty.openpty()
            self._set_pty_size(self.fd, SIZE_ROWS, SIZE_COLS)
            logger.info(f"Global terminal PTY created: {SIZE_COLS}x{SIZE_ROWS}")

            # Attach to tmux session
            cmd = ["tmux", "attach", "-t", self.session_name]
            self.pid = subprocess.Popen(
                cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True
            ).pid

            os.close(slave_fd)
            self.running = True
            logger.info(f"Global terminal started: fd={self.fd}, pid={self.pid}")

            asyncio.create_task(self._read_from_pty())

        except Exception as e:
            logger.error(f"Failed to start global terminal: {e}")
            await self.send_error(f"Failed to start terminal: {str(e)}")
            await self.close()

    def _set_pty_size(self, fd, rows, cols):
        try:
            import termios
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        except Exception as e:
            logger.warning(f"Failed to set PTY size: {e}")

    async def _read_from_pty(self):
        loop = asyncio.get_event_loop()
        max_read_bytes = 1024 * 1024

        try:
            while self.running and self.fd is not None:
                try:
                    data = await loop.run_in_executor(
                        None,
                        lambda: os.read(self.fd, max_read_bytes) if self._select() else b""
                    )

                    if data:
                        decoded = data.decode("utf-8", errors="replace")
                        await self.send_output(decoded)
                    else:
                        await asyncio.sleep(0.05)

                except OSError:
                    logger.info("Global terminal PTY closed (OSError)")
                    break

        except Exception as e:
            logger.error(f"Error reading from global PTY: {e}")
        finally:
            self.running = False

    def _select(self) -> bool:
        try:
            return select.select([self.fd], [], [], 0.1)[0] != []
        except:
            return False

    async def handle_input(self, data: str):
        try:
            if self.fd is not None:
                os.write(self.fd, data.encode("utf-8"))
        except Exception as e:
            await self.send_error(f"Write error: {str(e)}")

    async def handle_resize(self, cols: int, rows: int):
        try:
            if not (10 <= cols <= 500 and 5 <= rows <= 200):
                return

            if self.fd is not None:
                self._set_pty_size(self.fd, rows, cols)
                self.cols = cols
                self.rows = rows

                try:
                    subprocess.run(
                        ["tmux", "resize-pane", "-t", self.session_name, "-x", str(cols), "-y", str(rows)],
                        capture_output=True,
                        timeout=1
                    )
                except:
                    pass

                if self.pid is not None:
                    try:
                        import signal
                        os.killpg(os.getpgid(self.pid), signal.SIGWINCH)
                    except:
                        pass

        except Exception as e:
            logger.warning(f"Error during global terminal resize: {e}")

    async def handle_scroll_mode(self, action: str):
        try:
            if action == 'enter':
                subprocess.run(
                    ['tmux', 'copy-mode', '-e', '-t', self.session_name],
                    capture_output=True, text=True, timeout=2
                )
            elif action == 'exit':
                subprocess.run(
                    ['tmux', 'send-keys', '-t', self.session_name, 'Escape'],
                    capture_output=True, text=True, timeout=2
                )
        except Exception as e:
            logger.error(f"Error during scroll mode {action}: {e}")

    async def handle_scroll(self, direction: str, page: bool = False):
        try:
            if page:
                cmd = 'page-up' if direction == 'up' else 'page-down'
            else:
                cmd = 'cursor-up' if direction == 'up' else 'cursor-down'

            subprocess.run(
                ['tmux', 'send-keys', '-t', self.session_name, '-X', cmd],
                capture_output=True, text=True, timeout=2
            )
        except Exception as e:
            logger.error(f"Error during scroll {direction}: {e}")

    async def send_output(self, data: str):
        try:
            await self.websocket.send_json({"type": "output", "data": data})
        except Exception as e:
            logger.warning(f"Failed to send output: {e}")
            self.running = False

    async def send_error(self, message: str):
        try:
            await self.websocket.send_json({"type": "error", "message": message})
        except:
            pass

    async def close(self):
        self.running = False
        if self.fd is not None:
            try:
                os.close(self.fd)
            except:
                pass
            self.fd = None
        if self.pid is not None:
            try:
                os.killpg(os.getpgid(self.pid), 9)
            except:
                pass
            self.pid = None
```

- [ ] **Step 2: Add WebSocket endpoint to main.py**

Add to `backend/app/main.py` after the existing websocket_terminal function (around line 214):

```python
@app.websocket("/ws/global-terminal")
async def websocket_global_terminal(
    websocket: WebSocket,
    token: str = Query(...)
):
    """WebSocket endpoint for global terminal access"""
    logger.info("Global terminal WebSocket connection request")
    await websocket.accept()

    # Verify token
    if not verify_token(token):
        logger.warning("Global terminal connection rejected - invalid token")
        await websocket.close(code=1008, reason="Unauthorized")
        return

    from app.websocket.global_terminal import GlobalWebSocketTerminal
    terminal = GlobalWebSocketTerminal(websocket)

    try:
        logger.info("Global terminal started")
        await terminal.start()

        while True:
            try:
                data = await websocket.receive()

                if "text" in data:
                    message = data["text"]
                    try:
                        msg = json.loads(message)

                        if msg.get("type") == "input":
                            await terminal.handle_input(msg.get("data", ""))
                        elif msg.get("type") == "resize":
                            await terminal.handle_resize(
                                msg.get("cols", 80),
                                msg.get("rows", 24)
                            )
                        elif msg.get("type") == "scroll_mode":
                            action = msg.get("action")
                            if action in ("enter", "exit"):
                                await terminal.handle_scroll_mode(action)
                        elif msg.get("type") == "scroll":
                            direction = msg.get("direction")
                            page = msg.get("page", False)
                            if direction in ("up", "down"):
                                await terminal.handle_scroll(direction, page)

                    except json.JSONDecodeError:
                        pass
                elif "bytes" in data:
                    await terminal.handle_input(data["bytes"].decode("utf-8"))

            except WebSocketDisconnect as e:
                logger.info(f"Global terminal WebSocket disconnected: {str(e)}")
                break
            except RuntimeError as e:
                if "Cannot call receive once disconnected" in str(e):
                    logger.info("Global terminal WebSocket already disconnected")
                else:
                    logger.error(f"Global terminal WebSocket error: {str(e)}")
                break
            except Exception as e:
                logger.error(f"Global terminal WebSocket error: {str(e)}")
                break

    except Exception as e:
        logger.error(f"Global terminal WebSocket setup failed: {str(e)}")
    finally:
        await terminal.close()
        logger.info("Global terminal WebSocket connection closed")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/websocket/global_terminal.py backend/app/main.py
git commit -m "feat(backend): add global terminal WebSocket endpoint

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Frontend - Pinia Store for Global Terminal

**Files:**
- Create: `frontend/src/store/globalTerminal.ts`

- [ ] **Step 1: Create the Pinia store**

```typescript
// frontend/src/store/globalTerminal.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'v2c-global-terminal'

interface Position {
  x: number
  y: number
}

interface Size {
  width: number
  height: number
}

export const useGlobalTerminalStore = defineStore('globalTerminal', () => {
  const visible = ref(false)
  const position = ref<Position>({ x: 0, y: 0 })
  const size = ref<Size>({ width: 0, height: 0 })

  // Calculate initial centered position
  const getInitialPosition = (): Position => {
    const width = window.innerWidth * 0.6
    const height = window.innerHeight * 0.4
    return {
      x: (window.innerWidth - width) / 2,
      y: window.innerHeight * 0.2
    }
  }

  const getInitialSize = (): Size => ({
    width: window.innerWidth * 0.6,
    height: window.innerHeight * 0.4
  })

  const toggle = () => {
    visible.value = !visible.value
  }

  const show = () => {
    visible.value = true
  }

  const hide = () => {
    visible.value = false
  }

  const setPosition = (pos: Position) => {
    position.value = pos
  }

  const setSize = (s: Size) => {
    size.value = s
  }

  const loadFromStorage = () => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (parsed.position) position.value = parsed.position
        if (parsed.size) size.value = parsed.size
      }
    } catch {
      // Ignore parse errors
    }

    // Set defaults if not loaded
    if (position.value.x === 0 && position.value.y === 0) {
      position.value = getInitialPosition()
    }
    if (size.value.width === 0 && size.value.height === 0) {
      size.value = getInitialSize()
    }
  }

  const saveToStorage = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        position: position.value,
        size: size.value
      }))
    } catch {
      // Ignore storage errors
    }
  }

  return {
    visible,
    position,
    size,
    toggle,
    show,
    hide,
    setPosition,
    setSize,
    loadFromStorage,
    saveToStorage
  }
})
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/store/globalTerminal.ts
git commit -m "feat(frontend): add global terminal Pinia store

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Frontend - Global Terminal Icon Component

**Files:**
- Create: `frontend/src/components/GlobalTerminalIcon.vue`

- [ ] **Step 1: Create the icon component**

```vue
<!-- frontend/src/components/GlobalTerminalIcon.vue -->
<script setup lang="ts">
import { useGlobalTerminalStore } from '@/store/globalTerminal'

const store = useGlobalTerminalStore()
</script>

<template>
  <button
    @click="store.toggle()"
    class="p-1.5 rounded-lg hover:bg-sub"
    title="Global Terminal"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      class="h-5 w-5 text-sub"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
      />
    </svg>
  </button>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/GlobalTerminalIcon.vue
git commit -m "feat(frontend): add GlobalTerminalIcon component

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Frontend - Global Terminal Panel Component

**Files:**
- Create: `frontend/src/components/GlobalTerminal.vue`

- [ ] **Step 1: Create the GlobalTerminal component**

```vue
<!-- frontend/src/components/GlobalTerminal.vue -->
<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Terminal as XTerminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { useGlobalTerminalStore } from '@/store/globalTerminal'
import { useMainStore, type ThemeName } from '@/store'
import { useAuth } from '@/composables/useAuth'

const store = useGlobalTerminalStore()
const mainStore = useMainStore()
const { token } = useAuth()

const terminalRef = ref<HTMLElement | null>(null)
const containerRef = ref<HTMLElement | null>(null)
const xterm = ref<XTerminal | null>(null)
const fitAddon = ref<FitAddon | null>(null)
const ws = ref<WebSocket | null>(null)
const connected = ref(false)
const connecting = ref(false)
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })

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
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname
  const port = window.location.port

  if (import.meta.env.DEV) {
    return `${protocol}//${host}:${port}/ws/global-terminal`
  }

  if (port === '8864') {
    return `ws://${host}:8863/ws/global-terminal`
  }

  return `${protocol}//${host}${port ? ':' + port : ''}/ws/global-terminal`
}

const connect = () => {
  if (ws.value) {
    ws.value.close()
    ws.value = null
  }

  if (!token.value) return

  connecting.value = true
  const wsUrl = `${getWsUrl()}?token=${token.value}`

  try {
    ws.value = new WebSocket(wsUrl)

    ws.value.onopen = () => {
      connected.value = true
      connecting.value = false
      if (xterm.value) {
        xterm.value.writeln('\x1b[32m✓ Connected to global terminal\x1b[0m')
      }
    }

    ws.value.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'output') {
          xterm.value?.write(msg.data)
        } else if (msg.type === 'error') {
          xterm.value?.writeln(`\x1b[31mError: ${msg.message}\x1b[0m`)
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
    convertEol: true,
    theme: getXtermTheme(mainStore.theme)
  })

  fitAddon.value = new FitAddon()
  xterm.value.loadAddon(fitAddon.value)
  xterm.value.open(terminalRef.value)

  nextTick(() => {
    fitAddon.value?.fit()
    if (xterm.value) {
      resize(xterm.value.cols, xterm.value.rows)
    }
  })

  xterm.value.onData((data: string) => {
    send(data)
  })

  xterm.value.onResize(({ cols, rows }) => {
    resize(cols, rows)
  })

  // Clear and show connecting message
  xterm.value.clear()
  xterm.value.writeln('\x1b[33mConnecting to global terminal...\x1b[0m')

  // Connect WebSocket
  connect()
}

const handleResize = () => {
  nextTick(() => {
    if (!containerRef.value || containerRef.value.offsetParent === null) return
    fitAddon.value?.fit()
    if (xterm.value) {
      resize(xterm.value.cols, xterm.value.rows)
    }
  })
}

// Drag handling
const startDrag = (e: MouseEvent) => {
  if ((e.target as HTMLElement).closest('.close-btn')) return
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
      xterm.value.dispose()
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
})

onUnmounted(() => {
  disconnect()
  window.removeEventListener('resize', handleResize)
  if (xterm.value) {
    xterm.value.dispose()
    xterm.value = null
  }
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', endDrag)
})
</script>

<template>
  <div
    v-if="store.visible"
    ref="containerRef"
    class="fixed bg-main border border-main shadow-xl flex flex-col"
    :style="{
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
      class="flex items-center justify-between px-3 py-2 bg-sub border-b border-main cursor-move select-none"
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
  </div>
</template>

<style scoped>
:deep(.xterm) {
  height: 100%;
  padding: 0 !important;
}

:deep(.xterm-viewport) {
  background-color: var(--bg-primary) !important;
}

:deep(.xterm-screen) {
  background-color: var(--bg-primary);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/GlobalTerminal.vue
git commit -m "feat(frontend): add GlobalTerminal panel component with drag support

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Frontend - Integrate with App.vue

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Add GlobalTerminal to App.vue**

Update `frontend/src/App.vue`:

```vue
<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useTheme } from './composables/useTheme'
import GlobalTerminal from '@/components/GlobalTerminal.vue'

const { theme } = useTheme()
</script>

<template>
  <div :class="`theme-${theme}`" class="min-h-screen bg-main text-main">
    <RouterView />
    <GlobalTerminal />
  </div>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat(frontend): integrate GlobalTerminal into App.vue

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Frontend - Add Icon to ProjectsView

**Files:**
- Modify: `frontend/src/views/ProjectsView.vue`

- [ ] **Step 1: Import and add GlobalTerminalIcon**

Add import at the top of the script section (after line 9):

```typescript
import GlobalTerminalIcon from '@/components/GlobalTerminalIcon.vue'
```

Add the icon in the header actions section (after the theme button, before the logout button, around line 166):

```vue
<GlobalTerminalIcon />
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/ProjectsView.vue
git commit -m "feat(frontend): add global terminal icon to ProjectsView header

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Frontend - Add Icon to TasksView

**Files:**
- Modify: `frontend/src/views/TasksView.vue`

- [ ] **Step 1: Import and add GlobalTerminalIcon**

Add import at the top of the script section (after line 10):

```typescript
import GlobalTerminalIcon from '@/components/GlobalTerminalIcon.vue'
```

Add the icon in the header actions section (after the theme button, before the logout button, around line 213):

```vue
<GlobalTerminalIcon />
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/TasksView.vue
git commit -m "feat(frontend): add global terminal icon to TasksView header

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: Frontend - Add Icon to CodeReviewView

**Files:**
- Modify: `frontend/src/views/CodeReviewView.vue`

- [ ] **Step 1: Import and add GlobalTerminalIcon**

Add import at the top of the script section (after line 23, after the languageDetection import):

```typescript
import GlobalTerminalIcon from '@/components/GlobalTerminalIcon.vue'
```

Add the icon in the header actions section (after the theme button, before the settings button, around line 1735):

```vue
<GlobalTerminalIcon />
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/CodeReviewView.vue
git commit -m "feat(frontend): add global terminal icon to CodeReviewView header

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Testing and Verification

- [ ] **Step 1: Start the development servers**

```bash
./deploy.sh restart
```

- [ ] **Step 2: Test global terminal functionality**

1. Open the app in browser (http://localhost:8864)
2. Login
3. Click the terminal icon in the header - panel should appear centered
4. Verify terminal shows "Connected to global terminal"
5. Run a command like `ls -la` and verify output
6. Drag the panel by the title bar - position should update
7. Click close button - panel should hide
8. Click terminal icon again - panel should reappear
9. Verify terminal session persisted (previous output still visible)
10. Navigate to different pages - icon should be present on all
11. Reload page - panel should be hidden by default
12. Open terminal - verify previous session content preserved

- [ ] **Step 3: Test boundary constraints**

1. Open the global terminal
2. Try dragging it off-screen (left, right, top, bottom)
3. Verify at least 50px of the panel stays visible

- [ ] **Step 4: Test position persistence**

1. Drag the terminal to a specific position
2. Close the terminal
3. Open it again
4. Verify it opens at the saved position

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address global terminal issues from testing

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```
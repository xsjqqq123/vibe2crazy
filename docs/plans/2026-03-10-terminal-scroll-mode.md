# Terminal Scroll Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a scroll mode to the terminal that allows users to view tmux history (up to 50,000 lines) using mouse wheel and keyboard navigation.

**Architecture:** Frontend detects scroll-up-at-top or PageUp key, sends scroll_mode message to backend, backend enters tmux copy-mode. ESC exits. UI shows "Scroll Mode" in header.

**Tech Stack:** Vue 3, TypeScript, WebSocket, tmux, FastAPI

---

## Task 1: Add Backend scroll_mode Message Handler

**Files:**
- Modify: `backend/app/websocket/terminal.py`

**Step 1: Add handle_scroll_mode method**

Add the following method to the `WebSocketTerminal` class:

```python
async def handle_scroll_mode(self, action: str):
    """Handle scroll mode enter/exit commands"""
    session_name = self.task.tmux_session

    try:
        if action == 'enter':
            # Enter tmux copy-mode for scrolling history
            result = subprocess.run(
                ['tmux', 'send-keys', '-t', session_name, 'copy-mode'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode != 0:
                logger.warning(f"Failed to enter copy-mode: {result.stderr}")
            else:
                logger.info(f"Entered copy-mode for session {session_name}")

        elif action == 'exit':
            # Exit tmux copy-mode by sending Escape
            result = subprocess.run(
                ['tmux', 'send-keys', '-t', session_name, 'Escape'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode != 0:
                logger.warning(f"Failed to exit copy-mode: {result.stderr}")
            else:
                logger.info(f"Exited copy-mode for session {session_name}")

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout during scroll mode {action}")
    except Exception as e:
        logger.error(f"Error during scroll mode {action}: {e}")
```

**Step 2: Add import if not present**

Ensure `subprocess` is imported at the top of the file (it should already be there).

**Step 3: Modify the main WebSocket handler**

Find where WebSocket messages are processed (likely in the `start` method or a dedicated message handler). Add handling for `scroll_mode` type:

```python
# In the message handling section, add:
elif msg_type == 'scroll_mode':
    action = message.get('action')
    if action in ('enter', 'exit'):
        await self.handle_scroll_mode(action)
```

**Step 4: Test backend manually**

Start the backend server and verify no syntax errors:

```bash
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8863
```

Expected: Server starts without errors

**Step 5: Commit backend changes**

```bash
git add backend/app/websocket/terminal.py
git commit -m "feat(backend): add scroll_mode WebSocket message handler

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Add scrollMode State and Logic to Terminal.vue

**Files:**
- Modify: `frontend/src/components/Terminal/Terminal.vue`

**Step 1: Add scrollMode state variable**

After the other `ref` declarations around line 34, add:

```typescript
// Scroll mode state
const scrollMode = ref(false)
```

**Step 2: Add enterScrollMode function**

Add after the `sendEsc` function (around line 108):

```typescript
// Scroll mode functions
const enterScrollMode = () => {
  if (scrollMode.value) return
  scrollMode.value = true
  send(JSON.stringify({ type: 'scroll_mode', action: 'enter' }))
}

const exitScrollMode = () => {
  if (!scrollMode.value) return
  scrollMode.value = false
  send(JSON.stringify({ type: 'scroll_mode', action: 'exit' }))
}

const sendScrollCommand = (direction: 'up' | 'down', page: boolean = false) => {
  if (page) {
    // Page Up: \x1b[5~  Page Down: \x1b[6~
    const key = direction === 'up' ? '\x1b[5~' : '\x1b[6~'
    send(key)
  } else {
    // Up arrow: \x1b[A  Down arrow: \x1b[B
    const key = direction === 'up' ? '\x1b[A' : '\x1b[B'
    send(key)
  }
}
```

**Step 3: Modify handleWheel function**

Replace the existing `handleWheel` function (lines 111-144) with:

```typescript
// Handle wheel events for local scrolling and scroll mode
const handleWheel = (event: WheelEvent) => {
  if (!xterm.value) return

  const buffer = xterm.value.buffer.active

  if (scrollMode.value) {
    // In scroll mode: send scroll commands to tmux
    event.preventDefault()
    event.stopPropagation()
    event.stopImmediatePropagation()

    const direction = event.deltaY > 0 ? 'down' : 'up'
    sendScrollCommand(direction)
    return
  }

  // Normal mode: check if we should enter scroll mode
  if (event.deltaY < 0 && buffer.viewportY === 0) {
    // Scrolling up at buffer top → enter scroll mode
    enterScrollMode()
    event.preventDefault()
    event.stopPropagation()
    event.stopImmediatePropagation()
    return
  }

  // Normal scrolling within xterm buffer
  event.preventDefault()
  event.stopPropagation()
  event.stopImmediatePropagation()

  const scrollAmount = Math.sign(event.deltaY)
  xterm.value.scrollLines(scrollAmount)
}
```

**Step 4: Add Page Up key handler**

Add a keydown handler after the wheel handler setup. Find where xterm events are registered (around line 232) and add:

```typescript
// Handle Page Up key for entering scroll mode
const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'PageUp' && !scrollMode.value && connected.value) {
    enterScrollMode()
    event.preventDefault()
  } else if (event.key === 'PageDown' && scrollMode.value) {
    sendScrollCommand('down', true)
    event.preventDefault()
  } else if (event.key === 'PageUp' && scrollMode.value) {
    sendScrollCommand('up', true)
    event.preventDefault()
  }
}

// Register keydown handler on the terminal element
if (terminalRef.value) {
  terminalRef.value.addEventListener('keydown', handleKeyDown)
}
```

**Step 5: Modify onData handler to handle ESC in scroll mode**

Find the `xterm.value.onData` callback (around line 232) and modify it:

```typescript
// Handle user input
xterm.value.onData((data: string) => {
  if (scrollMode.value) {
    // In scroll mode, only ESC is handled (to exit)
    if (data === '\x1b') {
      exitScrollMode()
    }
    return // Ignore other keys in scroll mode
  }
  send(data)
})
```

**Step 6: Clean up event listener in onUnmounted**

In the `onUnmounted` hook (around line 336), add cleanup for the keydown handler:

```typescript
// Clean up keydown handler
if (terminalRef.value) {
  terminalRef.value.removeEventListener('keydown', handleKeyDown)
}
```

**Step 7: Test frontend compiles**

```bash
cd frontend && npm run build
```

Expected: Build succeeds without errors

**Step 8: Commit frontend logic changes**

```bash
git add frontend/src/components/Terminal/Terminal.vue
git commit -m "feat(frontend): add scroll mode state and logic

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Add Scroll Mode UI Display

**Files:**
- Modify: `frontend/src/components/Terminal/Terminal.vue`

**Step 1: Update template to show Scroll Mode status**

Find the `terminal-header` div (around line 368) and modify the status display section:

Replace:
```vue
<div class="terminal-status flex items-center gap-2">
  <span
    :class="[
      'terminal-status-dot w-2 h-2 rounded-full',
      connected ? 'bg-green-500' : connecting ? 'bg-yellow-500 animate-pulse' : 'bg-gray-500'
    ]"
  ></span>
  <span class="text-sm text-gray-700 dark:text-gray-300">{{ connecting ? 'Connecting...' : connected ? 'Connected' : 'Disconnected' }}</span>
</div>
```

With:
```vue
<div class="terminal-status flex items-center gap-2">
  <template v-if="scrollMode">
    <span class="text-sm font-medium text-amber-600 dark:text-amber-400">
      Scroll Mode
    </span>
  </template>
  <template v-else>
    <span
      :class="[
        'terminal-status-dot w-2 h-2 rounded-full',
        connected ? 'bg-green-500' : connecting ? 'bg-yellow-500 animate-pulse' : 'bg-gray-500'
      ]"
    ></span>
    <span class="text-sm text-gray-700 dark:text-gray-300">{{ connecting ? 'Connecting...' : connected ? 'Connected' : 'Disconnected' }}</span>
  </template>
</div>
```

**Step 2: Test UI display**

```bash
cd frontend && npm run build
```

Expected: Build succeeds

**Step 3: Commit UI changes**

```bash
git add frontend/src/components/Terminal/Terminal.vue
git commit -m "feat(frontend): show Scroll Mode status in header

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Manual Integration Testing

**Step 1: Start both frontend and backend**

```bash
./deploy.sh restart
```

**Step 2: Test scroll mode trigger**

1. Open a task with terminal
2. Generate some output (run a few commands)
3. Scroll to top of terminal buffer
4. Scroll mouse wheel up → should enter scroll mode and show "Scroll Mode" in header

**Step 3: Test Page Up trigger**

1. Press Page Up key → should enter scroll mode

**Step 4: Test scrolling in scroll mode**

1. Use mouse wheel to scroll up/down in tmux history
2. Use Page Up/Down to scroll by page

**Step 5: Test exit scroll mode**

1. Press ESC key → should exit scroll mode and restore connection status

**Step 6: Document any issues**

If issues found, create a new task to fix them.

---

## Task 5: Final Commit and Documentation

**Step 1: Update CLAUDE.md if needed**

Check if the terminal scroll mode feature should be documented in CLAUDE.md.

**Step 2: Final commit**

```bash
git add -A
git commit -m "feat: implement terminal scroll mode for tmux history viewing

- Add scroll_mode WebSocket message handler in backend
- Add scrollMode state and enter/exit logic in frontend
- Show Scroll Mode status in terminal header
- Support mouse wheel and Page Up/Down for navigation
- ESC key exits scroll mode

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Acceptance Criteria

- [ ] Mouse wheel up at buffer top triggers scroll mode
- [ ] Page Up key triggers scroll mode
- [ ] "Scroll Mode" displays in header bar during scroll mode
- [ ] Mouse wheel scrolls tmux history in scroll mode
- [ ] Page Up/Down scrolls by page in scroll mode
- [ ] ESC key exits scroll mode
- [ ] Connection status restored after exit
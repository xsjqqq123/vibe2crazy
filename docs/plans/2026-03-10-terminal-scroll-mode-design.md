# Terminal Scroll Mode Design

## Overview

Add a scroll mode to the terminal component that allows users to view tmux history (up to 50,000 lines) using mouse wheel and keyboard navigation.

## Requirements

- **Trigger**: Mouse wheel scroll up (when at buffer top) or Page Up key
- **History Range**: Full tmux history (up to 50,000 lines)
- **UI Display**: Show "Scroll Mode" in header bar, replacing connection status
- **Scroll Methods**: Mouse wheel + Page Up/Down
- **Exit**: ESC key only

## Architecture

### State Management

```typescript
// Terminal.vue
const scrollMode = ref(false)
```

### Message Flow

```
Frontend                          Backend (tmux)
   │                                  │
   │  wheel up / PageUp               │
   │─────────────────────────────────>│
   │  { type: 'scroll_mode',          │
   │    action: 'enter' }             │
   │                                  │
   │                       tmux copy-mode
   │                                  │
   │  wheel / PageUp/PageDown         │
   │─────────────────────────────────>│
   │  (scroll commands)               │
   │                                  │
   │  ESC key                         │
   │─────────────────────────────────>│
   │  { type: 'scroll_mode',          │
   │    action: 'exit' }              │
   │                                  │
   │                       tmux send Escape
   │                                  │
```

## Implementation Details

### 1. Enter Scroll Mode

**Trigger Conditions**:
- Mouse wheel up (deltaY < 0) when viewport is at buffer top
- Page Up key pressed

**Logic**:
```typescript
const enterScrollMode = () => {
  if (scrollMode.value) return
  scrollMode.value = true
  send({ type: 'scroll_mode', action: 'enter' })
}

const handleWheel = (event: WheelEvent) => {
  if (scrollMode.value) {
    event.preventDefault()
    const direction = event.deltaY > 0 ? 'down' : 'up'
    sendScrollCommand(direction)
    return
  }

  const buffer = xterm.value.buffer.active
  if (event.deltaY < 0 && buffer.viewportY === 0) {
    enterScrollMode()
    event.preventDefault()
  }
}
```

### 2. Exit Scroll Mode

**Trigger**: ESC key

**Logic**:
```typescript
const exitScrollMode = () => {
  if (!scrollMode.value) return
  scrollMode.value = false
  send({ type: 'scroll_mode', action: 'exit' })
}

xterm.value.onData((data: string) => {
  if (scrollMode.value) {
    if (data === '\x1b') {
      exitScrollMode()
    }
    return
  }
  send(data)
})
```

### 3. Scroll Commands in Scroll Mode

```typescript
const sendScrollCommand = (direction: 'up' | 'down', page: boolean = false) => {
  if (page) {
    const key = direction === 'up' ? '\x1b[5~' : '\x1b[6~'
    send(key)
  } else {
    const key = direction === 'up' ? '\x1b[A' : '\x1b[B'
    send(key)
  }
}
```

### 4. UI Display

```vue
<div class="terminal-header ...">
  <div class="terminal-status flex items-center gap-2">
    <template v-if="scrollMode">
      <span class="text-sm font-medium text-yellow-600 dark:text-yellow-400">
        Scroll Mode
      </span>
    </template>
    <template v-else>
      <!-- normal connection status -->
    </template>
  </div>
</div>
```

### 5. Backend Handler

```python
# backend/app/websocket/terminal.py

async def handle_scroll_mode(self, action: str):
    session_name = self.task.tmux_session
    if action == 'enter':
        subprocess.run(
            ['tmux', 'send-keys', '-t', session_name, 'copy-mode'],
            capture_output=True
        )
    elif action == 'exit':
        subprocess.run(
            ['tmux', 'send-keys', '-t', session_name, 'Escape'],
            capture_output=True
        )
```

## Files to Modify

| File | Changes |
|------|---------|
| `frontend/src/components/Terminal/Terminal.vue` | Add scrollMode state, enter/exit logic, UI display |
| `frontend/src/composables/useWebSocket.ts` | Add sendScrollMode method |
| `backend/app/websocket/terminal.py` | Add handle_scroll_mode handler |

## Acceptance Criteria

1. Mouse wheel up at buffer top triggers scroll mode
2. Page Up key triggers scroll mode
3. "Scroll Mode" displays in header bar during scroll mode
4. Mouse wheel scrolls tmux history
5. Page Up/Down scrolls by page
6. ESC key exits scroll mode
7. Connection status restored after exit
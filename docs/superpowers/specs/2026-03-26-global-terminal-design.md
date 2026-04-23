# Global Terminal Design

Date: 2026-03-26

## Overview

Add a global terminal (command line) accessible from all pages (Projects, Tasks list, Code Review). The terminal appears as a draggable panel overlaying the page content.

## Requirements

### Functional
- Terminal icon in header on all pages (ProjectsView, TasksView, CodeReviewView)
- Click icon to show/hide global terminal panel
- Panel is draggable via title bar
- Terminal connects to a persistent tmux session
- Working directory: user's home directory (`~`)
- Session persists across page navigation, refresh, and re-login

### Non-functional
- No new npm dependencies for drag functionality
- Reuse existing terminal infrastructure (xterm.js, WebSocket protocol)
- Shared singleton - one terminal instance across all pages

## Backend Design

### New Endpoints

#### 1. Create/Get Global Terminal Session
```
POST /api/global-terminal/session
Response: { session_name: "v2d-global", created: boolean }
```

Creates or retrieves the global tmux session named `v2d-global`.

#### 2. WebSocket Endpoint
```
/ws/global-terminal?token={session_token}
```

WebSocket connection for terminal I/O. Reuses existing message protocol from task terminal:
- `type: "input"` - user input
- `type: "resize"` - terminal resize
- `type: "scroll_mode"` - scroll mode commands

### Implementation

New file: `backend/app/routers/global_terminal.py`

```python
from fastapi import APIRouter, Depends
from app.services.tmux_service import TmuxService
from app.auth import get_current_user

router = APIRouter(prefix="/api/global-terminal", tags=["global-terminal"])

GLOBAL_SESSION_NAME = "v2d-global"

@router.post("/session")
async def get_or_create_session(user = Depends(get_current_user)):
    tmux = TmuxService()
    created = not tmux.session_exists(GLOBAL_SESSION_NAME)
    if created:
        tmux.create_session(GLOBAL_SESSION_NAME, working_dir="~")
    return {"session_name": GLOBAL_SESSION_NAME, "created": created}
```

#### WebSocket Handler Implementation

The WebSocket handler in `backend/app/websocket/global_terminal.py` reuses core logic from the task terminal handler:

1. Extract common handling into `backend/app/websocket/base_terminal.py`:
   - Message parsing and validation
   - Terminal input processing
   - Resize handling
   - Scroll mode commands

2. Task terminal (`terminal.py`) and global terminal (`global_terminal.py`) both use the base handler:
   - Task terminal passes `task_id` and uses task's tmux session
   - Global terminal uses fixed session name `v2d-global`

## Frontend Design

### Component Structure

```
frontend/src/
├── composables/
│   └── useTerminal.ts          # NEW: Extracted terminal logic
├── components/
│   └── Terminal/
│       ├── Terminal.vue        # Modified: Uses useTerminal composable
│       └── GlobalTerminal.vue  # NEW: Global terminal panel
├── components/
│   └── GlobalTerminalIcon.vue  # NEW: Header icon button
└── store/
    └── globalTerminal.ts       # NEW: Pinia store for state
```

### useTerminal Composable

Extracts core terminal logic from `Terminal.vue`:

```typescript
// composables/useTerminal.ts
export function useTerminal(options: {
  wsEndpoint: string,        // WebSocket endpoint URL
  sessionId?: string         // Optional session identifier
}) {
  const xterm = ref<XTerminal | null>(null)
  const connected = ref(false)
  const connecting = ref(false)

  // ... terminal initialization, WebSocket handling, theme support

  return {
    xterm,
    connected,
    connecting,
    initTerminal,
    disconnect,
    send,
    // ... other methods
  }
}
```

### GlobalTerminal.vue

```vue
<script setup lang="ts">
import { useGlobalTerminalStore } from '@/store/globalTerminal'
import { useTerminal } from '@/composables/useTerminal'

const store = useGlobalTerminalStore()
const { visible, position, size } = storeToRefs(store)

// Initialize terminal with global endpoint
const { connected, initTerminal, disconnect } = useTerminal({
  wsEndpoint: '/ws/global-terminal'
})

// Drag handling
const isDragging = ref(false)
const dragStart = { x: 0, y: 0 }

const startDrag = (e: MouseEvent) => { /* ... */ }
const onDrag = (e: MouseEvent) => { /* ... */ }
const endDrag = () => { /* ... */ }

// Connect on show, disconnect on hide
watch(visible, (show) => {
  if (show) initTerminal()
  else disconnect()
})
</script>
```

### GlobalTerminalIcon.vue

```vue
<template>
  <button @click="store.toggle()" class="p-1.5 rounded-lg hover:bg-sub" title="Global Terminal">
    <svg class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <!-- Terminal icon -->
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  </button>
</template>
```

### Pinia Store

```typescript
// store/globalTerminal.ts
export const useGlobalTerminalStore = defineStore('globalTerminal', {
  state: () => ({
    visible: false,
    position: { x: 0, y: 0 },
    size: { width: 0, height: 0 }
  }),
  actions: {
    toggle() { this.visible = !this.visible },
    show() { this.visible = true },
    hide() { this.visible = false },
    setPosition(pos: { x: number; y: number }) { this.position = pos },
    setSize(size: { width: number; height: number }) { this.size = size },
    loadFromStorage() { /* Load position/size from localStorage */ },
    saveToStorage() { /* Save position/size to localStorage */ }
  }
})
```

### Session Behavior
- tmux session persists across page navigation, refresh, and re-login
- Panel visibility state: hidden by default on page load (does not auto-reopen)
- Position and size saved to localStorage when user drags/resizes

### Placement

- Icon button added to each page's header action bar (alongside theme toggle and logout button):
  - `ProjectsView.vue` - in the header actions section
  - `TasksView.vue` - in the header actions section
  - `CodeReviewView.vue` - in the header actions section

- `GlobalTerminal.vue` component placed in `App.vue`

```vue
<!-- App.vue -->
<template>
  <div :class="`theme-${theme}`" class="min-h-screen bg-main text-main">
    <RouterView />
    <GlobalTerminal />
  </div>
</template>
```

## UI/UX Specifications

### Initial Position and Size
- Width: 60% of viewport
- Height: 40% of viewport
- Horizontally centered
- Positioned in upper portion of screen (20% from top)

### Drag Behavior
- Drag handle: Title bar at top of panel
- Boundary constraint: At least 50px of panel must remain visible on screen
- Position saved to localStorage after drag ends

### Visual Design
- Semi-transparent backdrop (optional, `bg-black/20`)
- Panel with border and shadow (`border border-main shadow-xl`)
- Title bar with close button
- z-index: 40 (below modals at z-50)

### Connection Behavior
- Connect WebSocket when panel becomes visible
- Disconnect WebSocket when panel is hidden
- Show connection status indicator (connected/connecting/disconnected)

## Implementation Steps

1. **Backend**
   - Create `backend/app/routers/global_terminal.py`
   - Add WebSocket handler in `main.py`
   - Register router in `main.py`

2. **Frontend - Composable**
   - Extract `useTerminal` from `Terminal.vue`
   - Refactor `Terminal.vue` to use composable

3. **Frontend - Components**
   - Create `GlobalTerminalIcon.vue`
   - Create `GlobalTerminal.vue`
   - Add icon to each page header

4. **Frontend - State Management**
   - Create `store/globalTerminal.ts`
   - Add to `App.vue`

5. **Testing**
   - Verify terminal creation and persistence
   - Test drag functionality and boundary constraints
   - Verify connection/disconnection on show/hide
   - Test position persistence across sessions

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| WebSocket authentication | Reuse existing token-based auth from task terminal |
| tmux session cleanup | Add cleanup on user logout (optional) |
| Multiple browser tabs | Shared tmux session handles this gracefully |
| Mobile responsiveness | Consider hiding on mobile or showing fullscreen |
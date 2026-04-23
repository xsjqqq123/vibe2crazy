---
name: Terminal Matrix Feature
description: Multi-terminal grid view for vibe2crazy with waterfall layout, task monitoring, and independent sessions
type: project
---

# Terminal Matrix Feature Design

## Overview

Add a terminal matrix view to vibe2crazy that displays multiple terminals in a configurable grid layout. Users can monitor all tasks across projects or create independent terminal sessions, with flexible layout controls and keyboard input targeting.

## Entry Point

### Location
- **Page**: ProjectsView.vue header, right side
- **Position**: Next to GlobalTerminalIcon button
- **Visibility**: Desktop only (hidden on mobile, `hidden md:flex` or similar)

### Button Design
- **Icon**: Grid/matrix SVG icon (4x4 grid pattern)
- **Style**: Same as GlobalTerminalIcon - `p-1.5 rounded-lg hover:bg-sub`
- **Tooltip**: "Terminal Matrix"

### Navigation
- **Action**: `window.open('/matrix', '_blank')` - opens in new browser tab
- **Route**: `/matrix` - requires authentication

## Header Controls

Top fixed header bar with layout controls:

| Control | Type | Options | Description |
|---------|------|---------|-------------|
| Columns | Dropdown | 2, 4, 6, 8, 10 | Grid column count |
| Rows | Dropdown | Dynamic | Max = 64/columns (e.g., columns=4 → max rows=16) |
| Height Ratio | Dropdown | 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5 | Terminal height = width × ratio |
| Connection Mode | Dropdown | "All Tasks" / "New Sessions" | Terminal source mode |
| Pagination | Buttons + Label | "第 X/Y 页" + Prev/Next | Navigate between pages |

### Dynamic Row Calculation
- Column selection determines max rows: `maxRows = Math.floor(64 / columns)`
- Row dropdown dynamically populates: 1, 2, 3, ..., maxRows

### Layout Persistence
- All settings saved to localStorage
- Restored on page load
- Key: `vibe2crazy-matrix-settings`

## Terminal Grid Layout

### CSS Grid Implementation
- Container uses CSS Grid: `grid-template-columns: repeat(columns, 1fr)`
- Each terminal width: calculated from container width / columns
- Each terminal height: width × heightRatio

### Terminal Sizing
- Width auto-calculated to fill column space evenly
- Height determined by ratio dropdown (relative to width)
- xterm.js FitAddon adapts terminal content to container

## Terminal Component

### Header Design
```
[① Proj/Task]  ← Circle number + compact project/task name
```

- **Number badge**: Circle background, selected state highlights (blue bg, white number)
- **Title text**: Truncated format `{project}/{task}` or `Terminal {index}`
- **Tooltip**: Full project and task name on hover
- **No close button**: Unlike GlobalTerminal, no close/drag handles

### Terminal Features
- Full xterm.js functionality (cursor, scrollback, theme)
- WebSocket connection for I/O
- Theme adaptation (light/dark/green/parchment)
- Scroll mode via PageUp/PageDown

### Selection Mechanism
- Click terminal area or header to select
- Selected terminal: blue circle background, receives keyboard input
- Unselected terminals: ignore keyboard input, still receive output
- Selection state stored in matrix store

## Connection Modes

### Mode A: All Tasks
Connect each terminal to existing task tmux sessions.

**Data Source**:
- Fetch all projects with their tasks
- Display all tasks (running/idle status)
- Sorted by project then task creation time

**Session Mapping**:
- Terminal connects to `v2d-{task_id}` tmux session
- Each task's existing terminal session reused

**Title Display**:
- Format: `① {project}/{task}` (truncated)
- Example: `① vibe/TestTask` → hover shows "vibe2crazy project / Test task"

**Pagination**:
- When task count > grid capacity (rows × columns)
- Split into pages, navigate with Prev/Next buttons
- Page capacity = rows × columns

### Mode B: New Sessions
Create independent tmux sessions for each terminal.

**Session Management**:
- Naming: `v2d-matrix-{index}` (index 1, 2, 3, ...)
- Backend tmux sessions persist (not destroyed on disconnect)
- Frontend WebSocket disconnects on mode switch or page close
- Reconnect to existing session on next visit

**Title Display**:
- Format: `① Terminal {index}`
- Example: `① Terminal 5`

**No Pagination**:
- Grid always shows exactly rows × columns terminals
- Unused positions show empty/placeholder state

### Mode Switching Behavior
When switching between modes:

| Action | Frontend WebSocket | Backend tmux Session |
|--------|-------------------|---------------------|
| Switch mode | Disconnect all | Keep alive (preserve content) |
| Return to mode | Reconnect | Connect to same session |
| Close page | Disconnect all | Keep alive |

This preserves terminal content state across mode switches and page refreshes.

## Pagination Logic

### Applicable Scenarios
- Only in "All Tasks" mode (task count may exceed grid capacity)
- "New Sessions" mode always shows fixed rows × columns

### Navigation
- Display: "第 X / Y 页" (Chinese format)
- Prev button: disabled on first page
- Next button: disabled on last page
- Per-page capacity: rows × columns

### State Preservation
- Current page stored in localStorage
- Reset to page 1 when row/column settings change

## Keyboard Input Routing

### Input Targeting
- Only selected terminal receives keyboard input
- Other terminals ignore input events
- WebSocket `send()` only called for selected terminal

### Scroll Mode
- PageUp: Enter scroll mode on selected terminal
- PageDown: Scroll down in scroll mode
- Escape: Exit scroll mode (handled by backend tmux)

### Implementation
```typescript
// In MatrixTerminal.vue
xterm.onData((data) => {
  if (isSelected && connected) {
    send(data)
  }
})

xterm.onKey(({ key, domEvent }) => {
  if (isSelected) {
    if (domEvent.code === 'PageUp') {
      enterScrollMode()
      sendScrollCommand('up', true)
    } else if (domEvent.code === 'PageDown') {
      sendScrollCommand('down', true)
    }
  }
})
```

## Frontend Architecture

### Component Structure
```
views/
  MatrixView.vue              # Page container, header controls

components/
  TerminalMatrix.vue          # Grid container, layout management
  MatrixTerminal.vue          # Single terminal instance

composables/
  useMatrixStore.ts           # State: rows, cols, ratio, mode, selectedIdx, page
  useMatrixWebSocket.ts       # WebSocket management for multiple terminals

store/
  matrixStore.ts              # Pinia store for matrix state
```

### State Management
```typescript
interface MatrixState {
  columns: number       // 2, 4, 6, 8, 10
  rows: number          // 1 to maxRows
  heightRatio: number   // 0.8, 1.0, ..., 2.5
  mode: 'tasks' | 'sessions'
  selectedIndex: number // 0 to (rows*cols - 1)
  currentPage: number
  tasks: Task[]         // All tasks for 'tasks' mode
}
```

## Backend API

### New Endpoints

**GET /api/tasks/all**
```typescript
Response: {
  tasks: Array<{
    id: string
    name: string
    project_id: string
    project_name: string
    status: 'running' | 'idle'
  }>
}
```

Returns all tasks across all projects for "All Tasks" mode.

**POST /api/matrix/sessions**
```typescript
Request: { count: number }
Response: {
  sessions: Array<{
    index: number
    session_name: string  // "v2d-matrix-{index}"
    exists: boolean       // Whether session already exists
  }>
}
```

Create or verify matrix sessions for "New Sessions" mode.

### WebSocket Endpoint
Reuse existing `/ws/terminal?task_id={id}` for task sessions.
New endpoint `/ws/matrix-terminal?index={index}` for matrix sessions.

## Data Flow

### Page Load Sequence
1. Read localStorage for saved settings (columns, rows, ratio, mode)
2. If "All Tasks" mode: fetch `/api/tasks/all`
3. If "New Sessions" mode: call `/api/matrix/sessions` with count = rows × cols
4. Render grid with terminals
5. Each terminal establishes WebSocket connection

### Setting Change Sequence
1. User changes column/row/ratio/mode dropdown
2. Update state, save to localStorage
3. Disconnect current WebSocket connections
4. Re-render grid with new layout
5. Reconnect WebSocket connections (same sessions if mode unchanged)

### Mode Switch Sequence
1. User switches mode dropdown
2. Disconnect all current WebSocket connections
3. Backend tmux sessions remain alive
4. Fetch new data source (tasks or create sessions)
5. Render grid with new terminals
6. Establish new WebSocket connections

## Styling Considerations

### Theme Support
- Matrix page respects global theme (light/dark/green/parchment)
- Each terminal inherits theme from mainStore
- Header controls use consistent button/input styles

### Responsive Behavior
- Desktop only (hidden on mobile viewport)
- Grid auto-adjusts to container width
- Minimum terminal size enforced to prevent unusable tiny terminals

### Selected Terminal Highlight
- Circle number badge: blue background (`bg-blue-500`)
- Number text: white (`text-white`)
- Optional: subtle border around selected terminal

## Implementation Checklist

### Frontend Tasks
- [ ] Create MatrixView.vue with header controls
- [ ] Create MatrixTerminal.vue component
- [ ] Create matrixStore.ts for state management
- [ ] Add /matrix route to router
- [ ] Add matrix button to ProjectsView header
- [ ] Implement localStorage persistence
- [ ] Implement keyboard input routing to selected terminal
- [ ] Implement pagination for All Tasks mode

### Backend Tasks
- [ ] Add GET /api/tasks/all endpoint
- [ ] Add POST /api/matrix/sessions endpoint
- [ ] Add /ws/matrix-terminal WebSocket endpoint
- [ ] Update tmux_service for matrix session management

### Testing
- [ ] Test grid layout with various column/row combinations
- [ ] Test mode switching preserves tmux content
- [ ] Test pagination navigation
- [ ] Test keyboard input only goes to selected terminal
- [ ] Test scroll mode on selected terminal
- [ ] Test localStorage persistence across sessions
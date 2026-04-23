# Terminal Scrollback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix mouse wheel scrolling to scroll terminal content locally instead of sending arrow keys to backend.

**Architecture:** The issue is that wheel events are being converted to arrow key sequences and sent to the backend shell. We need to intercept wheel events and use xterm.js's built-in scroll functionality for local scrolling of the scrollback buffer.

**Tech Stack:** Vue 3, xterm.js v6, TypeScript

---

### Task 1: Add Wheel Event Handler Variable

**Files:**
- Modify: `frontend/src/components/Terminal/Terminal.vue:41`

**Step 1: Add wheel handler reference variable**

Add a variable to store the wheel event handler reference for cleanup:

```typescript
let resizeTimeout: ReturnType<typeof setTimeout> | null = null
let wheelHandler: ((e: WheelEvent) => void) | null = null
```

**Step 2: Verify the file was modified correctly**

Run: `cd frontend && npm run build`
Expected: No TypeScript errors

---

### Task 2: Implement Wheel Event Handler Function

**Files:**
- Modify: `frontend/src/components/Terminal/Terminal.vue` (after line 100)

**Step 1: Add handleWheel function**

Add the wheel event handler function after the `sendEsc` function:

```typescript
const sendEsc = () => {
  if (!connected.value) return
  send('\x1b')
}

// Handle wheel events for local scrolling
const handleWheel = (event: WheelEvent) => {
  if (!xterm.value) return

  // Prevent default to stop event from being forwarded to backend
  event.preventDefault()

  // Calculate scroll amount (3 lines per wheel tick)
  const delta = Math.sign(event.deltaY) * 3
  xterm.value.scrollLines(delta)
}
```

**Step 2: Verify no TypeScript errors**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

---

### Task 3: Register Wheel Event Listener

**Files:**
- Modify: `frontend/src/components/Terminal/Terminal.vue` (in initTerminal function, after xterm.value.open)

**Step 1: Add wheel event listener after terminal opens**

Add the event listener registration after `xterm.value.open(terminalRef.value)`:

```typescript
xterm.value.open(terminalRef.value)
fitAddon.value.fit()

// Register wheel event handler for local scrolling
wheelHandler = handleWheel
terminalRef.value.addEventListener('wheel', wheelHandler, { passive: false })
```

**Step 2: Verify the change**

Run: `cd frontend && npm run build`
Expected: Build succeeds

---

### Task 4: Clean Up Wheel Event Listener on Unmount

**Files:**
- Modify: `frontend/src/components/Terminal/Terminal.vue` (in onUnmounted)

**Step 1: Add cleanup code in onUnmounted**

Add wheel handler cleanup in the onUnmounted function:

```typescript
onUnmounted(() => {
  if (resizeTimeout) clearTimeout(resizeTimeout)

  // Clean up wheel event listener
  if (wheelHandler && terminalRef.value) {
    terminalRef.value.removeEventListener('wheel', wheelHandler)
  }

  disconnect()
  // ... rest of cleanup
})
```

**Step 2: Verify the complete onUnmounted**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

---

### Task 5: Test the Implementation

**Files:**
- None (testing only)

**Step 1: Start development server**

Run: `cd frontend && npm run dev`
Expected: Dev server starts on http://localhost:5173

**Step 2: Test scrolling behavior**

1. Open browser to the application
2. Login and navigate to a task with terminal
3. Run a command that produces multiple lines of output (e.g., `ls -la /usr/bin`)
4. Use mouse wheel to scroll up - should scroll terminal content
5. Verify it does NOT show previous command history

**Step 3: Test scrollback buffer**

1. Generate more output than fits on screen
2. Scroll up to view older content
3. Scroll down to return to current position
4. Verify all content is accessible

---

### Task 6: Commit Changes

**Files:**
- Commit: `frontend/src/components/Terminal/Terminal.vue`

**Step 1: Stage and commit**

```bash
git add frontend/src/components/Terminal/Terminal.vue
git commit -m "$(cat <<'EOF'
fix: terminal wheel scroll for local scrollback buffer

Mouse wheel events were being converted to arrow keys and sent
to the backend shell, causing command history navigation instead
of scrolling the terminal content.

- Add wheel event interceptor with passive: false
- Use xterm.js scrollLines() for local scrolling
- Clean up event listener on component unmount

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

**Step 2: Verify commit**

Run: `git log -1 --oneline`
Expected: Shows the new commit

---

## Acceptance Criteria

- Mouse wheel up/down scrolls terminal content locally
- Does not send arrow keys to backend shell
- Scrolling through scrollback buffer (up to 1000 lines) works correctly
- No console errors
- Works in both light and dark themes
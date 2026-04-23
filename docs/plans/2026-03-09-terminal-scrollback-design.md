# Terminal Scrollback Design

## Problem

When scrolling the terminal with mouse wheel, the wheel events are converted to arrow keys and sent to the backend shell (bash/zsh), causing it to navigate to previous commands instead of scrolling the terminal content.

## Root Cause

The wheel events are either:
1. Being forwarded to the backend instead of being captured by xterm.js for local scrolling
2. CSS styles preventing `.xterm-viewport` from scrolling properly

## Solution

Fix xterm.js configuration and CSS to ensure wheel events are used for local scrolling of the scrollback buffer.

## Implementation

### File: `frontend/src/components/Terminal/Terminal.vue`

1. Check CSS styles for `.xterm-viewport` - ensure `overflow-y` allows scrolling
2. Verify xterm.js configuration supports local scrolling
3. May need to add wheel event handler to intercept and handle locally if default behavior is broken

### Changes

1. Review CSS in `Terminal.vue` and `main.css` for `.xterm-viewport` overflow settings
2. Adjust styles if needed to enable scrolling
3. Test wheel scrolling behavior

## Acceptance Criteria

- Mouse wheel scroll up/down scrolls the terminal content locally
- Does not send arrow keys to backend shell
- Scrolling through scrollback buffer (up to 1000 lines) works correctly
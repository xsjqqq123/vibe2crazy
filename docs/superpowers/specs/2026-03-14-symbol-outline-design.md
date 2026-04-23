# Symbol Outline Feature Design

**Date**: 2026-03-14
**Status**: Approved

## Overview

Add a collapsible symbol outline panel below the Monaco editor that displays code symbols (functions, classes, variables, etc.) in a tag-based waterfall layout. Clicking a symbol jumps to its location in the editor.

## User Requirements

- Display functions, variables, classes, methods, imports, and constants
- Click to jump to symbol location in editor
- Waterfall (tag-based) layout below the editor
- Collapsible panel

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Symbol Types | Full outline (functions, classes, variables, imports, constants) | Maximum navigation utility |
| Visual Style | Tag-based waterfall | Compact, clean, matches user request |
| Panel Behavior | Collapsible | User control over screen space |
| Display Scope | Editor mode only | Diff mode is read-only, focused on changes |
| Symbol Extraction | Regex-based parsing | Monaco doesn't have a synchronous symbol API; regex is reliable for common patterns |

## UI Design

### Layout

The outline panel is a **sibling of MonacoEditor** in CodeReviewView.vue, not inside MonacoEditor.vue. They share a flex column container.

```
┌─────────────────────────────────────────┐
│ 📝 src/services/UserService.ts          │  ← Editor header (in CodeReviewView)
├─────────────────────────────────────────┤
│                                         │
│  Monaco Editor Content                  │  ← MonacoEditor (flexible height)
│                                         │
├─────────────────────────────────────────┤
│ ▼ 📋 SYMBOLS (5)              [Collapse]│  ← Outline header
├─────────────────────────────────────────┤
│ [Injectable] [UserService] [apiUrl]     │  ← Symbol tags (waterfall)
│ [getUsers] [getUser]                    │
└─────────────────────────────────────────┘
```

### Symbol Tag Styling

Each symbol type has a distinct color matching Monaco's syntax highlighting:

| Symbol Type | Color | Icon |
|-------------|-------|------|
| Function/Method | Yellow (#dcdcaa) | ƒ |
| Class/Interface | Cyan (#4ec9b0) | ◼ |
| Variable | Blue (#9cdcfe) | v |
| Import | Purple (#c586c0) | 📥 |
| Constant | Orange (#ce9178) | C |

### Collapsed State

When collapsed, show only the header with symbol count:
```
┌─────────────────────────────────────────┐
│ ▶ 📋 SYMBOLS (5)              [Expand]  │
└─────────────────────────────────────────┘
```

## Components

### 1. SymbolOutline.vue

New component placed in `frontend/src/components/Monaco/SymbolOutline.vue`.

**Props**:
- `symbols: SymbolInfo[]` - Array of symbols to display
- `collapsed: boolean` - Panel collapse state

**Events**:
- `select(symbol: SymbolInfo)` - Emitted when user clicks a symbol
- `toggle` - Emitted when user toggles collapse state

**Template**:
- Header with toggle button, title, symbol count
- Tag container with waterfall layout (flex-wrap)
- Each tag is clickable with hover state

### 2. useSymbolOutline.ts

Composable for regex-based symbol extraction. Does NOT take editor as parameter.

```typescript
interface SymbolInfo {
  name: string
  kind: 'function' | 'class' | 'variable' | 'import' | 'constant'
  lineNumber: number
}

// Language-specific regex patterns
const PATTERNS: Record<string, RegExp[]> = {
  typescript: [
    /^(?:export\s+)?(?:async\s+)?function\s+(\w+)/gm,           // functions
    /^(?:export\s+)?class\s+(\w+)/gm,                            // classes
    /^(?:export\s+)?(?:const|let|var)\s+(\w+)/gm,                // variables
    /^import\s+.*from\s+['"](.+)['"]/gm,                         // imports
    /^(?:export\s+)?const\s+([A-Z_]+)\s*=/gm,                    // constants (UPPERCASE)
  ],
  python: [
    /^def\s+(\w+)/gm,                                             // functions
    /^class\s+(\w+)/gm,                                           // classes
    /^(\w+)\s*=/gm,                                               // variables
    /^import\s+(\w+)/gm,                                          // imports
    /^from\s+(\w+)\s+import/gm,                                   // from imports
  ],
  // Add more languages as needed
}

function useSymbolOutline() {
  const symbols = ref<SymbolInfo[]>([])

  // Extract symbols from code content
  function extractSymbols(code: string, language: string) {
    symbols.value = []
    const patterns = PATTERNS[language] || PATTERNS.typescript
    // ... regex matching logic
  }

  return { symbols, extractSymbols }
}
```

### 3. MonacoEditor.vue Changes

**New Exposed Method** (via defineExpose):
```typescript
defineExpose({
  goToLine: (lineNumber: number) => {
    if (editor) {
      editor.revealLineInCenter(lineNumber)
      editor.setSelection({
        startLineNumber: lineNumber,
        startColumn: 1,
        endLineNumber: lineNumber,
        endColumn: 1
      })
      editor.focus()
    }
  },
  getModel: () => editor?.getModel()
})
```

**Content Change Event**:
- Emit `content-change` event when editor content changes (for parent to re-extract symbols)

### 4. CodeReviewView.vue Changes

The outline panel is integrated here as a sibling to MonacoEditor:

```vue
<div class="flex flex-col flex-1 min-h-0">
  <!-- Monaco Editor -->
  <MonacoEditor
    ref="editorRef"
    v-model="fileContent"
    :path="currentFile"
    @content-change="handleContentChange"
  />

  <!-- Symbol Outline (sibling, not inside MonacoEditor) -->
  <SymbolOutline
    v-if="editorMode === 'editor' && currentFile"
    :symbols="symbols"
    :collapsed="outlineCollapsed"
    @select="handleSymbolSelect"
    @toggle="outlineCollapsed = !outlineCollapsed"
  />
</div>
```

**New State**:
- `symbols: SymbolInfo[]` - Current file's symbols
- `outlineCollapsed: boolean` - Collapse state (persisted to localStorage)

**New Methods**:
- `handleSymbolSelect(symbol)` - Call `editorRef.goToLine(symbol.lineNumber)`
- `handleContentChange()` - Re-extract symbols with debouncing

## Data Flow

1. User opens a file in editor mode
2. MonacoEditor creates editor with model, emits `content-change`
3. CodeReviewView calls `useSymbolOutline.extractSymbols(code, language)`
4. Regex patterns match symbols, stored in `symbols` ref
5. SymbolOutline component renders tags
6. User clicks tag → `handleSymbolSelect()` → `editorRef.goToLine()` → editor reveals line
7. User toggles collapse → state persisted to localStorage

## Performance Considerations

- **Debounce content changes**: Use 300ms debounce before re-extracting symbols
- **Limit symbol count**: Show max 100 symbols, add "+N more" indicator if exceeded
- **Cleanup**: Clear symbols array when file changes or component unmounts
- **Lazy extraction**: Only extract symbols when outline panel is expanded

## Error Handling

- If no symbols found, show "No symbols found" message in the panel
- For unsupported file types (images, PDFs, binary files), hide the outline panel entirely
- Gracefully handle regex errors (should not crash the editor)

## Persistence

- Collapse state: `localStorage.getItem('v2c-outline-collapsed')`
- Persists across sessions and files

## Testing Considerations

- Test with various file types (TS, JS, Python, Vue, etc.)
- Test with empty files
- Test with large files (many symbols)
- Test collapse/expand state persistence
- Test symbol click navigation
- Test that outline only shows in editor mode (not diff mode)

## Implementation Order

1. Create `useSymbolOutline.ts` composable with regex patterns
2. Create `SymbolOutline.vue` component
3. Add `defineExpose` to `MonacoEditor.vue` with `goToLine()` method
4. Integrate outline into `CodeReviewView.vue` as sibling of MonacoEditor
5. Add localStorage persistence for collapse state
6. Add debouncing for content changes
7. Test across file types and edge cases
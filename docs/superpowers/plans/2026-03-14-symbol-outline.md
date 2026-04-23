# Symbol Outline Feature Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collapsible symbol outline panel below the Monaco editor that displays code symbols in a waterfall tag layout with click-to-navigate functionality.

**Architecture:** The outline panel is a sibling of MonacoEditor in CodeReviewView.vue. Symbol extraction uses regex-based parsing in a composable. MonacoEditor exposes a goToLine method for navigation.

**Tech Stack:** Vue 3, TypeScript, Monaco Editor, Vitest

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/composables/useSymbolOutline.ts` | Create | Regex-based symbol extraction logic |
| `frontend/src/components/Monaco/SymbolOutline.vue` | Create | Outline panel UI component |
| `frontend/src/components/Monaco/MonacoEditor.vue` | Modify | Add goToLine expose, content-change emit |
| `frontend/src/views/CodeReviewView.vue` | Modify | Integrate outline panel |
| `frontend/src/components/__tests__/SymbolOutline.spec.ts` | Create | Unit tests for SymbolOutline |

---

## Chunk 1: Composable and Component

### Task 1: Create useSymbolOutline Composable

**Files:**
- Create: `frontend/src/composables/useSymbolOutline.ts`
- Test: `frontend/src/composables/__tests__/useSymbolOutline.spec.ts`

- [ ] **Step 1: Create the test file**

```typescript
// frontend/src/composables/__tests__/useSymbolOutline.spec.ts
import { describe, it, expect } from 'vitest'
import { useSymbolOutline } from '../useSymbolOutline'

describe('useSymbolOutline', () => {
  describe('extractSymbols', () => {
    it('extracts functions from TypeScript code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `function hello() {}
function world() {}`

      const symbols = extractSymbols(code, 'typescript')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'hello', kind: 'function', lineNumber: 1 })
      expect(symbols[1]).toMatchObject({ name: 'world', kind: 'function', lineNumber: 2 })
    })

    it('extracts classes from TypeScript code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `class UserService {}
class ProductService {}`

      const symbols = extractSymbols(code, 'typescript')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'UserService', kind: 'class', lineNumber: 1 })
    })

    it('extracts variables from TypeScript code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `const config = {}
let isLoading = false`

      const symbols = extractSymbols(code, 'typescript')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'config', kind: 'variable', lineNumber: 1 })
    })

    it('extracts imports from TypeScript code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `import { ref } from 'vue'
import axios from 'axios'`

      const symbols = extractSymbols(code, 'typescript')

      expect(symbols.length).toBeGreaterThanOrEqual(2)
      expect(symbols.some(s => s.kind === 'import')).toBe(true)
    })

    it('extracts constants (uppercase variables) from TypeScript code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `const API_URL = 'https://api.example.com'
const MAX_RETRIES = 3`

      const symbols = extractSymbols(code, 'typescript')

      expect(symbols.some(s => s.kind === 'constant')).toBe(true)
    })

    it('extracts functions from Python code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `def hello():
    pass

def world():
    pass`

      const symbols = extractSymbols(code, 'python')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'hello', kind: 'function', lineNumber: 1 })
    })

    it('extracts classes from Python code', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `class User:
    pass

class Product:
    pass`

      const symbols = extractSymbols(code, 'python')

      expect(symbols).toHaveLength(2)
      expect(symbols[0]).toMatchObject({ name: 'User', kind: 'class', lineNumber: 1 })
    })

    it('returns empty array for unsupported language', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `some random text`

      const symbols = extractSymbols(code, 'unknown-lang')

      expect(symbols).toEqual([])
    })

    it('returns empty array for empty code', () => {
      const { extractSymbols } = useSymbolOutline()

      const symbols = extractSymbols('', 'typescript')

      expect(symbols).toEqual([])
    })

    it('sorts symbols by line number', () => {
      const { extractSymbols } = useSymbolOutline()
      const code = `const a = 1
function b() {}
class C {}`

      const symbols = extractSymbols(code, 'typescript')

      const lineNumbers = symbols.map(s => s.lineNumber)
      expect(lineNumbers).toEqual([...lineNumbers].sort((a, b) => a - b))
    })

    it('limits symbols to 100 entries', () => {
      const { extractSymbols } = useSymbolOutline()
      // Generate code with 150 functions
      const code = Array.from({ length: 150 }, (_, i) => `function f${i}() {}`).join('\n')

      const symbols = extractSymbols(code, 'typescript')

      expect(symbols.length).toBeLessThanOrEqual(100)
    })
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- src/composables/__tests__/useSymbolOutline.spec.ts`
Expected: FAIL - module not found

- [ ] **Step 3: Create the composable implementation**

```typescript
// frontend/src/composables/useSymbolOutline.ts
import { ref, type Ref } from 'vue'

export interface SymbolInfo {
  name: string
  kind: 'function' | 'class' | 'variable' | 'import' | 'constant'
  lineNumber: number
}

interface SymbolPattern {
  pattern: RegExp
  kind: SymbolInfo['kind']
  matchIndex: number // Which capture group contains the symbol name
}

// Language-specific patterns
const LANGUAGE_PATTERNS: Record<string, SymbolPattern[]> = {
  typescript: [
    { pattern: /^(?:export\s+)?(?:async\s+)?function\s+(\w+)/gm, kind: 'function', matchIndex: 1 },
    { pattern: /^(?:export\s+)?class\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:export\s+)?interface\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:export\s+)?type\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:export\s+)?const\s+([A-Z_][A-Z0-9_]*)\s*=/gm, kind: 'constant', matchIndex: 1 },
    { pattern: /^(?:export\s+)?(?:const|let|var)\s+(\w+)/gm, kind: 'variable', matchIndex: 1 },
    { pattern: /^import\s+.*?from\s+['"]([^'"]+)['"]/gm, kind: 'import', matchIndex: 1 },
  ],
  javascript: [
    { pattern: /^(?:export\s+)?(?:async\s+)?function\s+(\w+)/gm, kind: 'function', matchIndex: 1 },
    { pattern: /^(?:export\s+)?class\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:export\s+)?const\s+([A-Z_][A-Z0-9_]*)\s*=/gm, kind: 'constant', matchIndex: 1 },
    { pattern: /^(?:export\s+)?(?:const|let|var)\s+(\w+)/gm, kind: 'variable', matchIndex: 1 },
    { pattern: /^import\s+.*?from\s+['"]([^'"]+)['"]/gm, kind: 'import', matchIndex: 1 },
  ],
  python: [
    { pattern: /^def\s+(\w+)/gm, kind: 'function', matchIndex: 1 },
    { pattern: /^(?:async\s+)?def\s+(\w+)/gm, kind: 'function', matchIndex: 1 },
    { pattern: /^class\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^import\s+(\w+)/gm, kind: 'import', matchIndex: 1 },
    { pattern: /^from\s+(\w+)/gm, kind: 'import', matchIndex: 1 },
    { pattern: /^(\w+)\s*=\s*(?!.*def|.*class)/gm, kind: 'variable', matchIndex: 1 },
  ],
  vue: [
    // Use TypeScript patterns for Vue (script section typically uses TS/JS)
    { pattern: /^(?:export\s+)?(?:async\s+)?function\s+(\w+)/gm, kind: 'function', matchIndex: 1 },
    { pattern: /^(?:export\s+)?class\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:export\s+)?interface\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:export\s+)?const\s+([A-Z_][A-Z0-9_]*)\s*=/gm, kind: 'constant', matchIndex: 1 },
    { pattern: /^(?:export\s+)?(?:const|let|var)\s+(\w+)/gm, kind: 'variable', matchIndex: 1 },
  ],
  go: [
    { pattern: /^func\s+(?:\([^)]+\)\s+)?(\w+)/gm, kind: 'function', matchIndex: 1 },
    { pattern: /^type\s+(\w+)\s+struct/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^type\s+(\w+)\s+interface/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^import\s+["']([^"']+)["']/gm, kind: 'import', matchIndex: 1 },
    { pattern: /^(\w+)\s*:=/gm, kind: 'variable', matchIndex: 1 },
  ],
  rust: [
    { pattern: /^(?:pub\s+)?fn\s+(\w+)/gm, kind: 'function', matchIndex: 1 },
    { pattern: /^(?:pub\s+)?struct\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:pub\s+)?enum\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:pub\s+)?trait\s+(\w+)/gm, kind: 'class', matchIndex: 1 },
    { pattern: /^(?:pub\s+)?const\s+(\w+)/gm, kind: 'constant', matchIndex: 1 },
    { pattern: /^use\s+([^;]+)/gm, kind: 'import', matchIndex: 1 },
  ],
}

const MAX_SYMBOLS = 100

export function useSymbolOutline() {
  const symbols: Ref<SymbolInfo[]> = ref([])

  function extractSymbols(code: string, language: string): SymbolInfo[] {
    const patterns = LANGUAGE_PATTERNS[language] || LANGUAGE_PATTERNS.typescript
    const found: SymbolInfo[] = []
    const lines = code.split('\n')

    for (const { pattern, kind, matchIndex } of patterns) {
      // Reset regex state
      pattern.lastIndex = 0
      let match
      while ((match = pattern.exec(code)) !== null) {
        if (found.length >= MAX_SYMBOLS) break

        // Calculate line number from character index
        const charIndex = match.index
        const lineNumber = code.substring(0, charIndex).split('\n').length
        const name = match[matchIndex]

        // Avoid duplicates (same name, same line)
        if (!found.some(s => s.name === name && s.lineNumber === lineNumber)) {
          found.push({ name, kind, lineNumber })
        }
      }
      if (found.length >= MAX_SYMBOLS) break
    }

    // Sort by line number
    found.sort((a, b) => a.lineNumber - b.lineNumber)
    symbols.value = found
    return found
  }

  return {
    symbols,
    extractSymbols
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- src/composables/__tests__/useSymbolOutline.spec.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useSymbolOutline.ts frontend/src/composables/__tests__/useSymbolOutline.spec.ts
git commit -m "feat: add useSymbolOutline composable for regex-based symbol extraction

- Supports TypeScript, JavaScript, Python, Vue, Go, Rust
- Extracts functions, classes, variables, imports, constants
- Limits output to 100 symbols for performance

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Create SymbolOutline Component

**Files:**
- Create: `frontend/src/components/Monaco/SymbolOutline.vue`
- Test: `frontend/src/components/__tests__/SymbolOutline.spec.ts`

- [ ] **Step 1: Create the test file**

```typescript
// frontend/src/components/__tests__/SymbolOutline.spec.ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SymbolOutline from '../Monaco/SymbolOutline.vue'
import type { SymbolInfo } from '@/composables/useSymbolOutline'

describe('SymbolOutline', () => {
  const mockSymbols: SymbolInfo[] = [
    { name: 'hello', kind: 'function', lineNumber: 1 },
    { name: 'UserService', kind: 'class', lineNumber: 5 },
    { name: 'config', kind: 'variable', lineNumber: 10 },
    { name: 'API_URL', kind: 'constant', lineNumber: 15 },
    { name: 'vue', kind: 'import', lineNumber: 1 },
  ]

  it('renders all symbols when not collapsed', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: mockSymbols, collapsed: false }
    })

    expect(wrapper.text()).toContain('hello')
    expect(wrapper.text()).toContain('UserService')
    expect(wrapper.text()).toContain('config')
    expect(wrapper.text()).toContain('API_URL')
  })

  it('shows symbol count in header', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: mockSymbols, collapsed: false }
    })

    expect(wrapper.text()).toContain('5')
  })

  it('hides symbols when collapsed', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: mockSymbols, collapsed: true }
    })

    // Symbols should not be visible in collapsed state
    const tags = wrapper.findAll('.symbol-tag')
    expect(tags.length).toBe(0)
  })

  it('emits select event when symbol is clicked', async () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: mockSymbols, collapsed: false }
    })

    const firstTag = wrapper.find('.symbol-tag')
    await firstTag.trigger('click')

    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')![0][0]).toEqual(mockSymbols[0])
  })

  it('emits toggle event when collapse button is clicked', async () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: mockSymbols, collapsed: false }
    })

    const toggleBtn = wrapper.find('.outline-toggle')
    await toggleBtn.trigger('click')

    expect(wrapper.emitted('toggle')).toBeTruthy()
  })

  it('shows "No symbols found" message when empty', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: [], collapsed: false }
    })

    expect(wrapper.text()).toContain('No symbols')
  })

  it('applies correct color class for function symbols', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: [{ name: 'test', kind: 'function', lineNumber: 1 }], collapsed: false }
    })

    const tag = wrapper.find('.symbol-tag')
    expect(tag.classes()).toContain('symbol-function')
  })

  it('applies correct color class for class symbols', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: [{ name: 'Test', kind: 'class', lineNumber: 1 }], collapsed: false }
    })

    const tag = wrapper.find('.symbol-tag')
    expect(tag.classes()).toContain('symbol-class')
  })

  it('shows expand icon when collapsed', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: mockSymbols, collapsed: true }
    })

    expect(wrapper.find('.outline-toggle').text()).toContain('▶')
  })

  it('shows collapse icon when expanded', () => {
    const wrapper = mount(SymbolOutline, {
      props: { symbols: mockSymbols, collapsed: false }
    })

    expect(wrapper.find('.outline-toggle').text()).toContain('▼')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- src/components/__tests__/SymbolOutline.spec.ts`
Expected: FAIL - module not found

- [ ] **Step 3: Create the component implementation**

```vue
<!-- frontend/src/components/Monaco/SymbolOutline.vue -->
<script setup lang="ts">
import type { SymbolInfo } from '@/composables/useSymbolOutline'

interface Props {
  symbols: SymbolInfo[]
  collapsed: boolean
}

interface Emits {
  (e: 'select', symbol: SymbolInfo): void
  (e: 'toggle'): void
}

defineProps<Props>()
const emit = defineEmits<Emits>()

function handleSymbolClick(symbol: SymbolInfo) {
  emit('select', symbol)
}

function handleToggle() {
  emit('toggle')
}

function getSymbolClass(kind: SymbolInfo['kind']): string {
  return `symbol-${kind}`
}

function getSymbolIcon(kind: SymbolInfo['kind']): string {
  switch (kind) {
    case 'function': return 'ƒ'
    case 'class': return '◼'
    case 'variable': return 'v'
    case 'import': return '📥'
    case 'constant': return 'C'
    default: return '•'
  }
}
</script>

<template>
  <div class="symbol-outline" :class="{ 'is-collapsed': collapsed }">
    <!-- Header -->
    <div class="outline-header">
      <button class="outline-toggle" @click="handleToggle" :title="collapsed ? 'Expand' : 'Collapse'">
        <span v-if="collapsed">▶</span>
        <span v-else>▼</span>
      </button>
      <span class="outline-title">📋 SYMBOLS</span>
      <span v-if="symbols.length > 0" class="outline-count">({{ symbols.length }})</span>
    </div>

    <!-- Content -->
    <div v-if="!collapsed" class="outline-content">
      <div v-if="symbols.length === 0" class="no-symbols">
        No symbols found
      </div>
      <div v-else class="symbol-tags">
        <button
          v-for="(symbol, index) in symbols"
          :key="`${symbol.kind}-${symbol.name}-${index}`"
          class="symbol-tag"
          :class="getSymbolClass(symbol.kind)"
          @click="handleSymbolClick(symbol)"
          :title="`${symbol.name} (line ${symbol.lineNumber})`"
        >
          <span class="symbol-icon">{{ getSymbolIcon(symbol.kind) }}</span>
          <span class="symbol-name">{{ symbol.name }}</span>
          <span class="symbol-line">{{ symbol.lineNumber }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.symbol-outline {
  background: var(--color-bg-sub, #252526);
  border-top: 1px solid var(--color-border, #333);
  font-size: 12px;
}

.outline-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-bottom: 1px solid var(--color-border, #333);
}

.outline-toggle {
  background: none;
  border: none;
  color: var(--color-text-sub, #808080);
  cursor: pointer;
  padding: 0;
  font-size: 10px;
  line-height: 1;
  width: 16px;
}

.outline-toggle:hover {
  color: var(--color-text-main, #ccc);
}

.outline-title {
  color: var(--color-text-main, #ccc);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.outline-count {
  color: var(--color-text-muted, #808080);
  font-size: 11px;
}

.outline-content {
  padding: 8px 12px;
}

.no-symbols {
  color: var(--color-text-muted, #808080);
  font-style: italic;
  font-size: 11px;
}

.symbol-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.symbol-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--color-bg-tertiary, #37373d);
  border: none;
  border-radius: 4px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 11px;
  transition: background 0.15s ease;
}

.symbol-tag:hover {
  background: var(--color-bg-hover, #094771);
}

.symbol-icon {
  font-size: 10px;
  opacity: 0.8;
}

.symbol-name {
  font-family: monospace;
}

.symbol-line {
  color: var(--color-text-muted, #808080);
  font-size: 10px;
  margin-left: 2px;
}

/* Symbol type colors */
.symbol-function {
  color: #dcdcaa;
}

.symbol-class {
  color: #4ec9b0;
}

.symbol-variable {
  color: #9cdcfe;
}

.symbol-import {
  color: #c586c0;
}

.symbol-constant {
  color: #ce9178;
}

/* Dark mode adjustments */
:global(.dark) .symbol-outline {
  background: #252526;
  border-top-color: #333;
}

:global(.dark) .outline-header {
  border-bottom-color: #333;
}
</style>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- src/components/__tests__/SymbolOutline.spec.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Monaco/SymbolOutline.vue frontend/src/components/__tests__/SymbolOutline.spec.ts
git commit -m "feat: add SymbolOutline component for displaying code symbols

- Waterfall tag layout with symbol type colors
- Collapsible panel with toggle button
- Click-to-navigate functionality via select event
- Empty state handling

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Chunk 2: MonacoEditor and CodeReviewView Integration

### Task 3: Add goToLine to MonacoEditor

**Files:**
- Modify: `frontend/src/components/Monaco/MonacoEditor.vue`

- [ ] **Step 1: Add defineExpose and content-change emit**

Modify `frontend/src/components/Monaco/MonacoEditor.vue`:

1. Add `content-change` emit to the interface:
```typescript
interface Emits {
  (e: 'update:modelValue', value: string): void
  (e: 'save'): void
  (e: 'previewMarkdown'): void
  (e: 'content-change'): void  // Add this
}
```

2. Emit content-change in the onDidChangeModelContent listener:
```typescript
// Listen for content changes
editor.onDidChangeModelContent(() => {
  if (editor) {
    emit('update:modelValue', editor.getValue())
    emit('content-change')  // Add this
  }
})
```

3. Add defineExpose at the end of the script section (before `</script>`):
```typescript
// Expose methods for parent components
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
  getModel: () => editor?.getModel() || null,
  getValue: () => editor?.getValue() || ''
})
```

- [ ] **Step 2: Verify changes are correct**

Read the file to verify:
```bash
head -n 250 frontend/src/components/Monaco/MonacoEditor.vue
```

Expected: File contains defineExpose with goToLine, getModel, getValue methods

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Monaco/MonacoEditor.vue
git commit -m "feat: add goToLine method and content-change emit to MonacoEditor

- Expose goToLine for symbol navigation
- Expose getModel and getValue utilities
- Emit content-change for symbol re-extraction

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Integrate SymbolOutline into CodeReviewView

**Files:**
- Modify: `frontend/src/views/CodeReviewView.vue`

- [ ] **Step 1: Add imports and composable**

At the top of the script section, add imports:
```typescript
import SymbolOutline from '@/components/Monaco/SymbolOutline.vue'
import { useSymbolOutline, type SymbolInfo } from '@/composables/useSymbolOutline'
```

- [ ] **Step 2: Add state variables and helpers**

Add after the existing refs (around line 100):
```typescript
// Symbol outline
const { symbols, extractSymbols } = useSymbolOutline()
const outlineCollapsed = ref(localStorage.getItem('v2c-outline-collapsed') === 'true')
const editorRef = ref<InstanceType<typeof MonacoEditor> | null>(null)

// File type support check for symbol outline
const isSupportedFileType = computed(() => {
  if (!currentFile.value) return false
  const ext = currentFile.value.split('.').pop()?.toLowerCase() || ''
  const supportedExtensions = [
    'ts', 'tsx', 'js', 'jsx', 'py', 'vue', 'go', 'rs',
    'java', 'c', 'cpp', 'h', 'hpp', 'cs', 'rb', 'php',
    'css', 'scss', 'sass', 'less', 'json', 'yaml', 'yml', 'md'
  ]
  return supportedExtensions.includes(ext)
})

// Language detection for symbol extraction (comprehensive, matches MonacoEditor)
const detectLanguage = (path: string): string => {
  const ext = path.split('.').pop()?.toLowerCase() || ''
  const languageMap: Record<string, string> = {
    'js': 'javascript', 'jsx': 'javascript',
    'ts': 'typescript', 'tsx': 'typescript',
    'py': 'python',
    'java': 'java',
    'cpp': 'cpp', 'c': 'c', 'h': 'cpp', 'hpp': 'cpp',
    'cs': 'csharp',
    'go': 'go',
    'rs': 'rust',
    'rb': 'ruby',
    'php': 'php',
    'vue': 'vue',
    'css': 'css', 'scss': 'scss', 'sass': 'sass', 'less': 'less',
    'json': 'json',
    'yaml': 'yaml', 'yml': 'yaml',
    'md': 'markdown',
  }
  return languageMap[ext] || 'typescript'
}

// Simple debounce utility (no VueUse dependency needed)
function debounce<T extends (...args: any[]) => any>(fn: T, delay: number): T {
  let timeoutId: ReturnType<typeof setTimeout> | null = null
  return ((...args: Parameters<T>) => {
    if (timeoutId) clearTimeout(timeoutId)
    timeoutId = setTimeout(() => fn(...args), delay)
  }) as T
}

// Debounced symbol extraction (300ms)
const debouncedExtractSymbols = debounce((content: string, path: string) => {
  if (outlineCollapsed.value) return // Lazy extraction - only when expanded
  extractSymbols(content, detectLanguage(path))
}, 300)
```

- [ ] **Step 3: Add event handlers**

Add handler functions:
```typescript
// Symbol outline handlers
function handleSymbolSelect(symbol: SymbolInfo) {
  if (editorRef.value) {
    editorRef.value.goToLine(symbol.lineNumber)
  }
}

function handleOutlineToggle() {
  outlineCollapsed.value = !outlineCollapsed.value
  localStorage.setItem('v2c-outline-collapsed', String(outlineCollapsed.value))
  // Extract symbols when expanding if not already done
  if (!outlineCollapsed.value && currentFile.value && fileContent.value && isSupportedFileType.value) {
    extractSymbols(fileContent.value, detectLanguage(currentFile.value))
  }
}

function handleContentChange() {
  if (currentFile.value && fileContent.value && isSupportedFileType.value) {
    debouncedExtractSymbols(fileContent.value, currentFile.value)
  }
}
```

- [ ] **Step 4: Modify template to add SymbolOutline**

Find the MonacoEditor in the template (around line 1800) and wrap it with SymbolOutline:

Before:
```vue
<MonacoEditor
  v-else-if="editorMode === 'editor' && currentFile"
  v-model="fileContent"
  :path="currentFile"
  :enable-save-shortcut="fileContent !== originalContent && !savingContent"
  :is-mobile="isMobile"
  @save="saveFile"
  @preview-markdown="openMarkdownPreview"
/>
```

After:
```vue
<div v-else-if="editorMode === 'editor' && currentFile" class="flex flex-col flex-1 min-h-0">
  <MonacoEditor
    ref="editorRef"
    v-model="fileContent"
    :path="currentFile"
    :enable-save-shortcut="fileContent !== originalContent && !savingContent"
    :is-mobile="isMobile"
    @save="saveFile"
    @preview-markdown="openMarkdownPreview"
    @content-change="handleContentChange"
  />
  <SymbolOutline
    v-if="isSupportedFileType"
    :symbols="symbols"
    :collapsed="outlineCollapsed"
    @select="handleSymbolSelect"
    @toggle="handleOutlineToggle"
  />
</div>
```

Note: The `v-if="isSupportedFileType"` on SymbolOutline ensures the outline is hidden for unsupported file types (images, PDFs, binary files).

- [ ] **Step 5: Verify the changes compile**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/CodeReviewView.vue
git commit -m "feat: integrate SymbolOutline into CodeReviewView

- Add symbol outline panel below Monaco editor
- Handle symbol click navigation
- Add localStorage persistence for collapse state
- Implement debounced symbol extraction on content change

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Chunk 3: Testing and Polish

### Task 5: Manual Testing

- [ ] **Step 1: Start the development server**

Run: `./deploy.sh start`
Wait for both frontend and backend to start

- [ ] **Step 2: Test basic functionality**

1. Open the app in browser
2. Navigate to a task with code files
3. Open a TypeScript/JavaScript file from the file tree
4. Verify symbol outline appears below the editor
5. Click on a symbol tag
6. Verify editor scrolls to that line

- [ ] **Step 3: Test collapse/expand**

1. Click the toggle button in the outline header
2. Verify outline collapses to header only
3. Click toggle again
4. Verify outline expands and shows symbols

- [ ] **Step 4: Test persistence**

1. Collapse the outline
2. Refresh the page
3. Verify outline remains collapsed
4. Expand the outline
5. Refresh the page
6. Verify outline remains expanded

- [ ] **Step 5: Test different file types**

1. Open a Python file - verify symbols are extracted
2. Open a Vue file - verify symbols are extracted
3. Open an image file - verify outline is hidden (v-if condition)
4. Open a file in diff mode - verify outline is hidden

- [ ] **Step 6: Test edge cases**

1. Open an empty file - verify "No symbols found" message
2. Open a file with many symbols (>100) - verify symbol limit
3. Edit a file - verify symbols update (debounced)

- [ ] **Step 7: Stop development server**

Run: `./deploy.sh stop`

---

### Task 6: Final Commit and Cleanup

- [ ] **Step 1: Run all tests**

Run: `cd frontend && npm test`
Expected: All tests pass

- [ ] **Step 2: Run lint check**

Run: `cd frontend && npm run lint`
Expected: No errors (or fix any issues)

- [ ] **Step 3: Final commit if needed**

If there are any uncommitted changes:
```bash
git add -A
git commit -m "fix: resolve any remaining issues from testing

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Create useSymbolOutline composable | `useSymbolOutline.ts`, test |
| 2 | Create SymbolOutline component | `SymbolOutline.vue`, test |
| 3 | Add goToLine to MonacoEditor | `MonacoEditor.vue` |
| 4 | Integrate into CodeReviewView | `CodeReviewView.vue` |
| 5 | Manual testing | - |
| 6 | Final commit | - |
# 主题系统扩展实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有的双主题系统扩展为四主题系统，新增豆沙绿护眼主题和仿羊皮纸主题。

**Architecture:** 使用 CSS 变量定义主题色，通过 `theme-{name}` 类切换主题，迁移现有 `dark:` 类名到语义化工具类。

**Tech Stack:** Vue 3, Pinia, Tailwind CSS, Monaco Editor, xterm.js

---

## Chunk 1: 核心主题系统

### Task 1: 更新 Store 主题状态管理

**Files:**
- Modify: `frontend/src/store/index.ts`

- [ ] **Step 1: 添加 ThemeName 类型定义和主题状态**

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ThemeName = 'light' | 'dark' | 'green' | 'parchment'

export const useMainStore = defineStore('main', () => {
  // Theme
  const theme = ref<ThemeName>('dark')
  const themeOrder: ThemeName[] = ['light', 'dark', 'green', 'parchment']
  const validThemes: ThemeName[] = ['light', 'dark', 'green', 'parchment']

  // Keep isDark for backward compatibility during transition
  const isDark = ref(true)

  const setTheme = (newTheme: ThemeName) => {
    theme.value = newTheme
    isDark.value = newTheme === 'dark'

    // Remove all theme classes
    document.documentElement.classList.remove('theme-dark', 'theme-light', 'theme-green', 'theme-parchment', 'dark')
    // Add new theme class
    document.documentElement.classList.add(`theme-${newTheme}`)
    if (newTheme === 'dark') {
      document.documentElement.classList.add('dark')
    }
    localStorage.setItem('theme', newTheme)
  }

  const cycleTheme = () => {
    const currentIndex = themeOrder.indexOf(theme.value)
    const nextIndex = (currentIndex + 1) % themeOrder.length
    setTheme(themeOrder[nextIndex])
  }

  const toggleTheme = () => {
    cycleTheme()
  }

  const initTheme = () => {
    const saved = localStorage.getItem('theme') as ThemeName | null
    const initialTheme = saved && validThemes.includes(saved) ? saved : 'dark'
    setTheme(initialTheme)
  }

  // Current project/task
  const currentProject = ref<any>(null)
  const currentTask = ref<any>(null)

  const setCurrentProject = (project: any) => {
    currentProject.value = project
  }

  const setCurrentTask = (task: any) => {
    currentTask.value = task
  }

  return {
    theme,
    isDark,
    cycleTheme,
    toggleTheme,
    initTheme,
    currentProject,
    currentTask,
    setCurrentProject,
    setCurrentTask
  }
})
```

- [ ] **Step 2: 提交核心状态更新**

```bash
git add frontend/src/store/index.ts
git commit -m "feat(theme): add multi-theme state management with cycleTheme"
```

---

### Task 2: 更新 useTheme composable

**Files:**
- Modify: `frontend/src/composables/useTheme.ts`

- [ ] **Step 1: 暴露 theme 和 cycleTheme**

```typescript
import { onMounted, toRefs } from 'vue'
import { useMainStore } from '@/store'

export function useTheme() {
  const store = useMainStore()

  onMounted(() => {
    store.initTheme()
  })

  const cycleTheme = () => {
    store.cycleTheme()
  }

  const toggleTheme = () => {
    store.toggleTheme()
  }

  // Use toRefs to maintain reactivity when destructuring
  return {
    ...toRefs(store),
    cycleTheme,
    toggleTheme
  }
}
```

- [ ] **Step 2: 提交 composable 更新**

```bash
git add frontend/src/composables/useTheme.ts
git commit -m "feat(theme): expose theme and cycleTheme from composable"
```

---

### Task 3: 添加 CSS 变量和工具类

**Files:**
- Modify: `frontend/src/assets/styles/main.css`

- [ ] **Step 1: 在文件开头添加主题 CSS 变量**

在 `@layer base {` 之前添加：

```css
/* ========================================
   THEME CSS VARIABLES
   ======================================== */

:root {
  /* Light theme (default) */
  --bg-primary: #ffffff;
  --bg-secondary: #f3f4f6;
  --bg-tertiary: #e5e7eb;
  --text-primary: #111827;
  --text-secondary: #6b7280;
  --text-muted: #9ca3af;
  --border-color: #e5e7eb;
  --border-secondary: #d1d5db;
  --accent-color: #3b82f6;
  --accent-hover: #2563eb;
}

/* Dark theme */
.theme-dark {
  --bg-primary: #0d1117;
  --bg-secondary: #161b22;
  --bg-tertiary: #21262d;
  --text-primary: #c9d1d9;
  --text-secondary: #8b949e;
  --text-muted: #6e7681;
  --border-color: #21262d;
  --border-secondary: #30363d;
  --accent-color: #3fb950;
  --accent-hover: #2ea043;
}

/* Green (eye-protection) theme */
.theme-green {
  --bg-primary: #c7edcc;
  --bg-secondary: #d4f1d8;
  --bg-tertiary: #b8e0be;
  --text-primary: #2d5a3d;
  --text-secondary: #4a7c5b;
  --text-muted: #6a9c7b;
  --border-color: #a8d8af;
  --border-secondary: #8fc898;
  --accent-color: #3b82f6;
  --accent-hover: #2563eb;
}

/* Parchment theme */
.theme-parchment {
  --bg-primary: #f4ecd8;
  --bg-secondary: #e8dfc8;
  --bg-tertiary: #dcd2b8;
  --text-primary: #5c4d3a;
  --text-secondary: #7a6b55;
  --text-muted: #9a8b75;
  --border-color: #d4c4a8;
  --border-secondary: #c4b498;
  --accent-color: #b8860b;
  --accent-hover: #9a7209;
}
```

- [ ] **Step 2: 在 `@layer components {` 中添加语义化工具类**

在现有的 `.card-hover` 之后添加：

```css
  /* Theme-aware utility classes */
  .bg-main { background-color: var(--bg-primary); }
  .bg-sub { background-color: var(--bg-secondary); }
  .bg-tertiary { background-color: var(--bg-tertiary); }
  .text-main { color: var(--text-primary); }
  .text-sub { color: var(--text-secondary); }
  .text-muted { color: var(--text-muted); }
  .border-main { border-color: var(--border-color); }
  .border-sub { border-color: var(--border-secondary); }
  .text-accent { color: var(--accent-color); }
  .bg-accent { background-color: var(--accent-color); }
  .hover-accent:hover { background-color: var(--accent-hover); }
```

- [ ] **Step 3: 提交 CSS 更新**

```bash
git add frontend/src/assets/styles/main.css
git commit -m "feat(theme): add CSS variables and utility classes for 4 themes"
```

---

### Task 4: 更新 App.vue 主题类应用

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: 使用 theme 替代 isDark**

```vue
<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useTheme } from './composables/useTheme'

const { theme } = useTheme()
</script>

<template>
  <div :class="`theme-${theme}`" class="min-h-screen bg-main text-main">
    <RouterView />
  </div>
</template>
```

- [ ] **Step 2: 提交 App.vue 更新**

```bash
git add frontend/src/App.vue
git commit -m "feat(theme): apply theme class dynamically in App.vue"
```

---

## Chunk 2: Monaco Editor 主题适配

### Task 5: 定义 Monaco 自定义主题

**Files:**
- Modify: `frontend/src/components/Monaco/MonacoEditor.vue`

- [ ] **Step 1: 添加主题映射和自定义主题定义**

在 `<script setup>` 中，修改以下内容：

```typescript
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import * as monaco from 'monaco-editor'
import { useMainStore, type ThemeName } from '@/store'

// ... existing code ...

const store = useMainStore()

// Define custom Monaco themes
const defineCustomThemes = () => {
  monaco.editor.defineTheme('green', {
    base: 'vs',
    inherit: true,
    rules: [],
    colors: {
      'editor.background': '#c7edcc',
      'editor.foreground': '#2d5a3d',
      'editor.lineHighlightBackground': '#b8e0be',
      'editor.selectionBackground': '#a8d8af',
      'editorCursor.foreground': '#3b82f6',
    }
  })

  monaco.editor.defineTheme('parchment', {
    base: 'vs',
    inherit: true,
    rules: [],
    colors: {
      'editor.background': '#f4ecd8',
      'editor.foreground': '#5c4d3a',
      'editor.lineHighlightBackground': '#e8dfc8',
      'editor.selectionBackground': '#d4c4a8',
      'editorCursor.foreground': '#b8860b',
    }
  })
}

// Theme mapping
const getMonacoTheme = (theme: ThemeName): string => {
  const themeMap: Record<ThemeName, string> = {
    light: 'vs',
    dark: 'vs-dark',
    green: 'green',
    parchment: 'parchment'
  }
  return themeMap[theme]
}
```

- [ ] **Step 2: 更新 onMounted 和 watch**

修改 `onMounted` 中的主题应用：

```typescript
onMounted(() => {
  if (!containerRef.value) return

  // Define custom themes first
  defineCustomThemes()

  // Create Monaco editor
  editor = monaco.editor.create(containerRef.value, {
    value: props.modelValue,
    language: currentLanguage.value,
    theme: getMonacoTheme(store.theme),
    // ... rest of options ...
  })

  // ... rest of onMounted code ...
})
```

修改 `watch(isDark, ...)` 为 `watch(() => store.theme, ...)`:

```typescript
// Watch for theme changes
watch(() => store.theme, (newTheme) => {
  if (editor) {
    monaco.editor.setTheme(getMonacoTheme(newTheme))
  }
})
```

- [ ] **Step 3: 移除 isDark 的解构**

将 `const { isDark } = useTheme()` 改为直接使用 store：

```typescript
const store = useMainStore()
```

- [ ] **Step 4: 提交 Monaco Editor 更新**

```bash
git add frontend/src/components/Monaco/MonacoEditor.vue
git commit -m "feat(theme): add Monaco custom themes for green and parchment"
```

---

### Task 6: 更新 MonacoDiffEditor 主题

**Files:**
- Modify: `frontend/src/components/Monaco/MonacoDiffEditor.vue`

- [ ] **Step 1: 添加相同的主题定义和映射**

与 MonacoEditor.vue 类似的修改：

```typescript
import { useMainStore, type ThemeName } from '@/store'

const store = useMainStore()

const defineCustomThemes = () => {
  // Same as MonacoEditor.vue
}

const getMonacoTheme = (theme: ThemeName): string => {
  // Same as MonacoEditor.vue
}
```

- [ ] **Step 2: 更新 onMounted 和 watch**

与 MonacoEditor.vue 相同的修改模式。

- [ ] **Step 3: 提交 MonacoDiffEditor 更新**

```bash
git add frontend/src/components/Monaco/MonacoDiffEditor.vue
git commit -m "feat(theme): add Monaco diff editor custom themes"
```

---

## Chunk 3: Terminal 主题适配

### Task 7: 更新 Terminal xterm 主题

**Files:**
- Modify: `frontend/src/components/Terminal/Terminal.vue`

- [ ] **Step 1: 添加 GREEN_THEME 和 PARCHMENT_THEME**

在现有 `LIGHT_THEME` 之后添加：

```typescript
import { useMainStore, type ThemeName } from '@/store'

const store = useMainStore()

// Theme configurations for xterm.js
const DARK_THEME = {
  // ... existing ...
}

const LIGHT_THEME = {
  // ... existing ...
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
```

- [ ] **Step 2: 更新 initTerminal 中的主题应用**

```typescript
const initTerminal = () => {
  // ... existing code ...

  xterm.value = new XTerminal({
    // ... other options ...
    theme: getXtermTheme(store.theme),
    // ...
  })

  // ... rest of init code ...
}
```

- [ ] **Step 3: 更新主题 watch**

将：
```typescript
watch(isDark, (dark) => {
  if (xterm.value) {
    xterm.value.options.theme = dark ? DARK_THEME : LIGHT_THEME
  }
})
```

改为：
```typescript
watch(() => store.theme, (newTheme) => {
  if (xterm.value) {
    try {
      xterm.value.options.theme = getXtermTheme(newTheme)
    } catch (error) {
      console.warn('[Terminal] Failed to update theme:', error)
    }
  }
})
```

- [ ] **Step 4: 添加主题特定的 CSS**

在 `<style scoped>` 中添加：

```css
/* Theme-specific xterm backgrounds */
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
```

- [ ] **Step 5: 提交 Terminal 更新**

```bash
git add frontend/src/components/Terminal/Terminal.vue
git commit -m "feat(theme): add xterm themes for green and parchment"
```

---

## Chunk 4: UI 组件迁移

### Task 8: 更新主题切换按钮图标

**Files:**
- Modify: `frontend/src/views/ProjectsView.vue`

- [ ] **Step 1: 更新主题切换按钮显示不同图标**

找到主题切换按钮部分，修改为根据主题显示不同图标：

```vue
<button @click="cycleTheme" class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-700" title="Cycle theme">
  <!-- Sun icon for light theme -->
  <svg v-if="theme === 'light'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-gray-600 dark:text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
  </svg>
  <!-- Moon icon for dark theme -->
  <svg v-else-if="theme === 'dark'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-gray-600 dark:text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
  </svg>
  <!-- Leaf icon for green theme -->
  <svg v-else-if="theme === 'green'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
  </svg>
  <!-- Document icon for parchment theme -->
  <svg v-else-if="theme === 'parchment'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-amber-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
</button>
```

- [ ] **Step 2: 更新 useTheme 解构**

将：
```typescript
const { isDark, toggleTheme } = useTheme()
```

改为：
```typescript
const { theme, cycleTheme } = useTheme()
```

- [ ] **Step 3: 提交按钮更新**

```bash
git add frontend/src/views/ProjectsView.vue
git commit -m "feat(theme): add theme-specific icons for cycle button"
```

---

### Task 9: 迁移核心组件 dark: 类名

**Files:**
- Modify: `frontend/src/views/ProjectsView.vue`
- Modify: `frontend/src/views/TasksView.vue`
- Modify: `frontend/src/views/CodeReviewView.vue`

**注意：** 这是一个较大的重构，需要将 `dark:` 类名替换为新的语义化类名。为减少风险，采用渐进式迁移策略：

- [ ] **Step 1: 迁移 ProjectsView.vue 关键样式**

将 `dark:bg-gray-900` → `theme-dark:bg-gray-900` 或使用 `bg-main`
将 `dark:text-gray-100` → 使用 `text-main`

主要修改：
- 外层容器背景色
- 卡片背景色
- 文字颜色

- [ ] **Step 2: 迁移 TasksView.vue 关键样式**

同上模式。

- [ ] **Step 3: 迁移 CodeReviewView.vue 关键样式**

同上模式。

- [ ] **Step 4: 提交 UI 组件迁移**

```bash
git add frontend/src/views/
git commit -m "refactor(theme): migrate core views to use theme utility classes"
```

---

### Task 10: 最终集成测试

- [ ] **Step 1: 启动前端开发服务器**

```bash
cd frontend && npm run dev
```

- [ ] **Step 2: 测试主题循环切换**

在浏览器中：
1. 点击主题切换按钮
2. 验证 light → dark → green → parchment → light 循环
3. 刷新页面验证主题持久化

- [ ] **Step 3: 测试 Monaco Editor 主题**

1. 打开代码编辑页面
2. 切换主题验证编辑器背景色变化
3. 验证 diff 编辑器同步变化

- [ ] **Step 4: 测试 Terminal 主题**

1. 打开终端页面
2. 切换主题验证终端背景色变化
3. 验证文字颜色可读性

- [ ] **Step 5: 提交最终验证**

```bash
git add -A
git commit -m "feat(theme): complete 4-theme system with green and parchment themes"
```

---

## 文件修改总结

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `frontend/src/store/index.ts` | 重构 | 主题状态从 boolean 改为 string |
| `frontend/src/composables/useTheme.ts` | 重构 | 暴露 theme 和 cycleTheme |
| `frontend/src/assets/styles/main.css` | 新增 | CSS 变量和工具类 |
| `frontend/src/App.vue` | 重构 | 动态主题类应用 |
| `frontend/src/components/Monaco/MonacoEditor.vue` | 重构 | 自定义 Monaco 主题 |
| `frontend/src/components/Monaco/MonacoDiffEditor.vue` | 重构 | 自定义 Monaco 主题 |
| `frontend/src/components/Terminal/Terminal.vue` | 重构 | xterm 主题适配 |
| `frontend/src/views/ProjectsView.vue` | 重构 | 主题切换按钮图标 |
| `frontend/src/views/TasksView.vue` | 重构 | dark: 类名迁移 |
| `frontend/src/views/CodeReviewView.vue` | 重构 | dark: 类名迁移 |
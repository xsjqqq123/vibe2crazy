# 主题系统扩展设计

日期：2026-03-11

## 概述

将现有的白天/黑夜双主题扩展为四主题系统，新增豆沙绿护眼主题和仿羊皮纸主题。

## 需求

1. 新增「柔和豆沙绿」主题（背景 #C7EDCC）
2. 新增「复古羊皮纸」主题（背景 #F4ECD8）
3. 循环切换四种主题
4. Monaco Editor 和 Terminal 同步适配主题

## 技术方案

采用 CSS 变量 + Tailwind 扩展方案，将现有 `.dark` 类模式扩展为多主题类。

### 主题色定义

| 主题 | 背景主色 | 背景次色 | 文字主色 | 文字次色 | 边框色 | 强调色 |
|------|----------|----------|----------|----------|--------|--------|
| light | #ffffff | #f3f4f6 | #111827 | #6b7280 | #e5e7eb | #3b82f6 |
| dark | #0d1117 | #161b22 | #c9d1d9 | #8b949e | #21262d | #3fb950 |
| green | #c7edcc | #d4f1d8 | #2d5a3d | #4a7c5b | #a8d8af | #3b82f6 |
| parchment | #f4ecd8 | #e8dfc8 | #5c4d3a | #7a6b55 | #d4c4a8 | #b8860b |

### 数据结构

```typescript
type ThemeName = 'light' | 'dark' | 'green' | 'parchment'

// store/index.ts
const theme = ref<ThemeName>('dark')
const themeOrder: ThemeName[] = ['light', 'dark', 'green', 'parchment']
```

### CSS 变量

```css
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f3f4f6;
  --text-primary: #111827;
  --text-secondary: #6b7280;
  --border-color: #e5e7eb;
  --accent-color: #3b82f6;
}

.theme-dark { /* dark 色值 */ }
.theme-green { /* green 色值 */ }
.theme-parchment { /* parchment 色值 */ }
```

### Tailwind 工具类

```css
@layer components {
  .bg-main { background-color: var(--bg-primary); }
  .bg-sub { background-color: var(--bg-secondary); }
  .text-main { color: var(--text-primary); }
  .text-sub { color: var(--text-secondary); }
  .border-main { border-color: var(--border-color); }
  .text-accent { color: var(--accent-color); }
}
```

### Monaco Editor 主题

```typescript
monaco.editor.defineTheme('green', {
  base: 'vs',
  inherit: true,
  colors: {
    'editor.background': '#c7edcc',
    'editor.foreground': '#2d5a3d',
  }
})

monaco.editor.defineTheme('parchment', {
  base: 'vs',
  inherit: true,
  colors: {
    'editor.background': '#f4ecd8',
    'editor.foreground': '#5c4d3a',
  }
})
```

### Terminal 主题

```typescript
const xtermThemes: Record<ThemeName, ITheme> = {
  light: { background: '#ffffff', foreground: '#111827', ... },
  dark: { background: '#0d1117', foreground: '#c9d1d9', ... },
  green: { background: '#c7edcc', foreground: '#2d5a3d', ... },
  parchment: { background: '#f4ecd8', foreground: '#5c4d3a', ... },
}
```

### 切换逻辑

```typescript
const cycleTheme = () => {
  const currentIndex = themeOrder.indexOf(theme.value)
  const nextIndex = (currentIndex + 1) % themeOrder.length
  setTheme(themeOrder[nextIndex])
}

const setTheme = (newTheme: ThemeName) => {
  theme.value = newTheme
  document.documentElement.classList.remove('theme-dark', 'theme-light', 'theme-green', 'theme-parchment')
  document.documentElement.classList.add(`theme-${newTheme}`)
  localStorage.setItem('theme', newTheme)
}
```

## 文件修改清单

### 核心

- `frontend/src/store/index.ts` - 主题状态管理
- `frontend/src/composables/useTheme.ts` - 主题 composable
- `frontend/src/assets/styles/main.css` - CSS 变量和工具类
- `frontend/tailwind.config.js` - Tailwind 配置

### Monaco Editor

- `frontend/src/components/Monaco/MonacoEditor.vue`
- `frontend/src/components/Monaco/MonacoDiffEditor.vue`

### Terminal

- `frontend/src/components/Terminal/Terminal.vue`

### UI 组件（迁移 dark: 类名）

- `frontend/src/App.vue`
- `frontend/src/views/ProjectsView.vue`
- `frontend/src/views/TasksView.vue`
- `frontend/src/views/CodeReviewView.vue`
- `frontend/src/components/*.vue`（约 15 个文件）

## 错误处理

- localStorage 存储非法值时，回退到 `dark` 主题
- 新用户默认使用 `dark` 主题

## 向后兼容

- 现有 `dark` 主题用户升级后自动保持 `dark` 主题
- localStorage 中存储的是主题名称字符串，格式不变
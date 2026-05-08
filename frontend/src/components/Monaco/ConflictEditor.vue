<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import { loader } from '@guolao/vue-monaco-editor'
import { useMainStore, type ThemeName } from '@/store'

interface ConflictRegion {
  id: number
  startLine: number
  separatorLine: number
  endLine: number
  currentContent: string
  incomingContent: string
  resolved: boolean
  resolution?: 'current' | 'incoming' | 'both'
}

interface Props {
  content: string
  path?: string
  isMobile?: boolean
}

interface Emits {
  (e: 'update:content', value: string): void
  (e: 'resolved'): void
  (e: 'save'): void
}

const props = withDefaults(defineProps<Props>(), {
  content: '',
  path: '',
  isMobile: false
})

const emit = defineEmits<Emits>()
const store = useMainStore()

const containerRef = ref<HTMLElement | null>(null)
const conflicts = ref<ConflictRegion[]>([])
const currentConflictIndex = ref(0)
const error = ref('')

let editor: any = null
let model: any = null
let decorations: string[] = []
let zoneWidgets: ConflictActionZone[] = []

// Detect language from file extension
const detectLanguage = (path: string): string => {
  const ext = path.split('.').pop()?.toLowerCase() || ''

  const languageMap: Record<string, string> = {
    'js': 'javascript',
    'jsx': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'py': 'python',
    'java': 'java',
    'cpp': 'cpp',
    'c': 'c',
    'h': 'cpp',
    'hpp': 'cpp',
    'cs': 'csharp',
    'go': 'go',
    'rs': 'rust',
    'rb': 'ruby',
    'php': 'php',
    'html': 'html',
    'css': 'css',
    'scss': 'scss',
    'sass': 'sass',
    'less': 'less',
    'json': 'json',
    'xml': 'xml',
    'yaml': 'yaml',
    'yml': 'yaml',
    'md': 'markdown',
    'sh': 'shell',
    'bash': 'shell',
    'zsh': 'shell',
    'sql': 'sql',
    'vue': 'vue'
  }

  return languageMap[ext] || 'plaintext'
}

const currentLanguage = computed(() => props.path ? detectLanguage(props.path) : 'plaintext')

// Parse conflict markers from content
const parseConflicts = (content: string): ConflictRegion[] => {
  const lines = content.split('\n')
  const conflictList: ConflictRegion[] = []
  let currentConflict: Partial<ConflictRegion> | null = null
  let conflictId = 0

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    if (line.startsWith('<<<<<<<')) {
      currentConflict = {
        id: conflictId++,
        startLine: i,
        currentContent: '',
        resolved: false
      }
    } else if (line === '=======') {
      if (currentConflict) {
        currentConflict.separatorLine = i
        currentConflict.incomingContent = ''
      }
    } else if (line.startsWith('>>>>>>>')) {
      if (currentConflict && currentConflict.separatorLine !== undefined) {
        currentConflict.endLine = i
        conflictList.push(currentConflict as ConflictRegion)
        currentConflict = null
      }
    } else if (currentConflict) {
      if (currentConflict.separatorLine === undefined) {
        // Before separator - current content
        currentConflict.currentContent! += (currentConflict.currentContent ? '\n' : '') + line
      } else {
        // After separator - incoming content
        currentConflict.incomingContent! += (currentConflict.incomingContent ? '\n' : '') + line
      }
    }
  }

  return conflictList
}

// Update conflict decorations in editor
const updateDecorations = async () => {
  if (!editor || !model) return

  const monaco = await loader.init()
  const newDecorations: any[] = []

  conflicts.value.forEach((conflict) => {
    if (conflict.resolved) return

    // Highlight current section (between <<<<<<< and =======)
    newDecorations.push({
      range: new monaco.Range(conflict.startLine + 1, 1, conflict.separatorLine + 1, 1),
      options: {
        isWholeLine: true,
        className: 'conflict-current-section',
        glyphMarginClassName: 'conflict-glyph'
      }
    })

    // Highlight incoming section (between ======= and >>>>>>>)
    newDecorations.push({
      range: new monaco.Range(conflict.separatorLine + 1, 1, conflict.endLine + 1, 1),
      options: {
        isWholeLine: true,
        className: 'conflict-incoming-section',
        glyphMarginClassName: 'conflict-glyph'
      }
    })

    // Highlight conflict markers
    newDecorations.push({
      range: new monaco.Range(conflict.startLine + 1, 1, conflict.startLine + 1, 1),
      options: {
        isWholeLine: true,
        className: 'conflict-marker-line',
        glyphMarginClassName: 'conflict-marker-glyph'
      }
    })

    newDecorations.push({
      range: new monaco.Range(conflict.separatorLine + 1, 1, conflict.separatorLine + 1, 1),
      options: {
        isWholeLine: true,
        className: 'conflict-separator-line'
      }
    })

    newDecorations.push({
      range: new monaco.Range(conflict.endLine + 1, 1, conflict.endLine + 1, 1),
      options: {
        isWholeLine: true,
        className: 'conflict-marker-line',
        glyphMarginClassName: 'conflict-marker-glyph'
      }
    })
  })

  decorations = editor.deltaDecorations(decorations, newDecorations)
}

// Resolve a conflict
const resolveConflict = (conflictIndex: number, resolution: 'current' | 'incoming' | 'both') => {
  if (!model) return

  const conflict = conflicts.value[conflictIndex]
  if (!conflict) return

  let resolvedContent: string
  if (resolution === 'current') {
    resolvedContent = conflict.currentContent
  } else if (resolution === 'incoming') {
    resolvedContent = conflict.incomingContent
  } else {
    resolvedContent = conflict.currentContent + '\n' + conflict.incomingContent
  }

  // Get the full content and replace the conflict region
  const lines = model.getValue().split('\n')
  const before = lines.slice(0, conflict.startLine).join('\n')
  const after = lines.slice(conflict.endLine + 1).join('\n')

  const newContent = before + (before && resolvedContent ? '\n' : '') + resolvedContent + (resolvedContent && after ? '\n' : '') + after

  model.setValue(newContent)

  // Mark conflict as resolved
  conflict.resolved = true
  conflict.resolution = resolution

  // Update decorations
  updateDecorations()

  // Emit updated content
  emit('update:content', newContent)

  // Check if all conflicts are resolved
  if (conflicts.value.every(c => c.resolved)) {
    emit('resolved')
  }
}

// Navigate to next/previous conflict
const goToNextConflict = () => {
  const unresolvedIndex = conflicts.value.findIndex((c, i) => i > currentConflictIndex.value && !c.resolved)
  if (unresolvedIndex !== -1) {
    currentConflictIndex.value = unresolvedIndex
    editor?.revealLineInCenter(conflicts.value[unresolvedIndex].startLine + 1)
  } else {
    // Wrap around to first unresolved
    const firstUnresolved = conflicts.value.findIndex(c => !c.resolved)
    if (firstUnresolved !== -1) {
      currentConflictIndex.value = firstUnresolved
      editor?.revealLineInCenter(conflicts.value[firstUnresolved].startLine + 1)
    }
  }
}

const goToPrevConflict = () => {
  const reversedIndex = [...conflicts.value].reverse().findIndex((c, i) => {
    const originalIndex = conflicts.value.length - 1 - i
    return originalIndex < currentConflictIndex.value && !c.resolved
  })

  if (reversedIndex !== -1) {
    const unresolvedIndex = conflicts.value.length - 1 - reversedIndex
    currentConflictIndex.value = unresolvedIndex
    editor?.revealLineInCenter(conflicts.value[unresolvedIndex].startLine + 1)
  } else {
    // Wrap around to last unresolved
    const lastUnresolved = [...conflicts.value].reverse().findIndex(c => !c.resolved)
    if (lastUnresolved !== -1) {
      const index = conflicts.value.length - 1 - lastUnresolved
      currentConflictIndex.value = index
      editor?.revealLineInCenter(conflicts.value[index].startLine + 1)
    }
  }
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

// Computed for unresolved count
const unresolvedCount = computed(() => conflicts.value.filter(c => !c.resolved).length)
const hasUnresolvedConflicts = computed(() => unresolvedCount.value > 0)

// Zone Widget for inline conflict resolution buttons
class ConflictActionZone {
  private editor: any
  private conflict: ConflictRegion
  private onResolve: (resolution: 'current' | 'incoming' | 'both') => void
  private container: HTMLElement | null = null
  private viewZoneId: string | null = null

  constructor(
    editor: any,
    conflict: ConflictRegion,
    onResolve: (resolution: 'current' | 'incoming' | 'both') => void
  ) {
    this.editor = editor
    this.conflict = conflict
    this.onResolve = onResolve
    console.log('[ConflictActionZone] constructor called for line', conflict.startLine + 1)
    this.create()
  }

  private create() {
    console.log('[ConflictActionZone] create() called')
    this.container = document.createElement('div')
    this.container.className = 'conflict-action-zone'
    this.container.style.cssText = 'pointer-events: auto; position: relative; z-index: 10;'
    this.container.addEventListener('mousedown', (e) => {
      console.log('[ConflictActionZone] Container mousedown', e.target)
      e.stopPropagation()
    })

    const buttonsDiv = document.createElement('div')
    buttonsDiv.className = 'conflict-buttons'
    buttonsDiv.style.cssText = 'pointer-events: auto; display: flex; gap: 4px; align-items: center;'

    // Create Accept Current button
    const btnCurrent = document.createElement('button')
    btnCurrent.className = 'conflict-btn conflict-btn-current'
    btnCurrent.title = 'Accept Current Changes'
    btnCurrent.textContent = 'Accept Current'
    btnCurrent.style.cssText = 'pointer-events: auto; cursor: pointer;'
    btnCurrent.addEventListener('mousedown', (e) => {
      console.log('[ConflictActionZone] Accept Current mousedown')
      e.stopPropagation()
    })
    btnCurrent.addEventListener('click', (e) => {
      console.log('[ConflictActionZone] Accept Current clicked')
      e.preventDefault()
      e.stopPropagation()
      this.onResolve('current')
    })

    // Create Accept Incoming button
    const btnIncoming = document.createElement('button')
    btnIncoming.className = 'conflict-btn conflict-btn-incoming'
    btnIncoming.title = 'Accept Incoming Changes'
    btnIncoming.textContent = 'Accept Incoming'
    btnIncoming.style.cssText = 'pointer-events: auto; cursor: pointer;'
    btnIncoming.addEventListener('mousedown', (e) => {
      console.log('[ConflictActionZone] Accept Incoming mousedown')
      e.stopPropagation()
    })
    btnIncoming.addEventListener('click', (e) => {
      console.log('[ConflictActionZone] Accept Incoming clicked')
      e.preventDefault()
      e.stopPropagation()
      this.onResolve('incoming')
    })

    // Create Accept Both button
    const btnBoth = document.createElement('button')
    btnBoth.className = 'conflict-btn conflict-btn-both'
    btnBoth.title = 'Accept Both Changes'
    btnBoth.textContent = 'Accept Both'
    btnBoth.style.cssText = 'pointer-events: auto; cursor: pointer;'
    btnBoth.addEventListener('mousedown', (e) => {
      console.log('[ConflictActionZone] Accept Both mousedown')
      e.stopPropagation()
    })
    btnBoth.addEventListener('click', (e) => {
      console.log('[ConflictActionZone] Accept Both clicked')
      e.preventDefault()
      e.stopPropagation()
      this.onResolve('both')
    })

    buttonsDiv.appendChild(btnCurrent)
    buttonsDiv.appendChild(btnIncoming)
    buttonsDiv.appendChild(btnBoth)
    this.container.appendChild(buttonsDiv)

    // Add view zone (Monaco uses 1-indexed line numbers)
    // Place buttons after the >>>>>>> marker (endLine)
    this.editor.changeViewZones((changeAccessor: any) => {
      this.viewZoneId = changeAccessor.addZone({
        afterLineNumber: this.conflict.endLine + 1,
        heightInLines: 1.6,
        domNode: this.container!,
        suppressMouseDown: true
      })
      console.log('[ConflictActionZone] Zone added with ID:', this.viewZoneId)
    })
  }

  public dispose() {
    if (this.viewZoneId) {
      this.editor.changeViewZones((changeAccessor: any) => {
        changeAccessor.removeZone(this.viewZoneId!)
      })
    }
    if (this.container) {
      this.container.remove()
      this.container = null
    }
  }
}

// Create zone widgets for unresolved conflicts
const createZoneWidgets = () => {
  // Dispose existing widgets
  zoneWidgets.forEach(w => w.dispose())
  zoneWidgets = []

  if (!editor) {
    console.log('[ConflictEditor] createZoneWidgets: no editor')
    return
  }

  const unresolvedConflicts = conflicts.value.filter(c => !c.resolved)
  console.log('[ConflictEditor] createZoneWidgets: found', unresolvedConflicts.length, 'unresolved conflicts')

  // Create new widgets for unresolved conflicts
  conflicts.value.forEach((conflict, index) => {
    if (!conflict.resolved) {
      console.log('[ConflictEditor] Creating widget for conflict', index, 'at line', conflict.startLine + 1)
      const widget = new ConflictActionZone(
        editor!,
        conflict,
        (resolution) => resolveConflict(index, resolution)
      )
      zoneWidgets.push(widget)
    }
  })
}

// Dispose all zone widgets
const disposeZoneWidgets = () => {
  zoneWidgets.forEach(w => w.dispose())
  zoneWidgets = []
}

// Save method exposed to parent
const save = () => {
  emit('save')
}

// Handle Ctrl+S shortcut
const handleKeydown = (e: KeyboardEvent) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault()
    save()
  }
}

onMounted(async () => {
  if (!containerRef.value) return

  const monaco = await loader.init()

  // Define custom Monaco themes before creating editor
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

  // Parse conflicts
  conflicts.value = parseConflicts(props.content)

  // Create model
  model = monaco.editor.createModel(props.content, currentLanguage.value)

  // Create editor
  editor = monaco.editor.create(containerRef.value, {
    model: model,
    theme: getMonacoTheme(store.theme),
    automaticLayout: true,
    minimap: { enabled: false },
    fontSize: 14,
    lineNumbers: props.isMobile ? 'off' : 'on',
    scrollBeyondLastLine: false,
    wordWrap: 'on',
    glyphMargin: true,
    folding: false
  })

  // Update decorations
  updateDecorations()

  // Create zone widgets for inline buttons
  nextTick(() => {
    createZoneWidgets()
  })

  // Listen for content changes
  model.onDidChangeContent(() => {
    if (model) {
      // Re-parse conflicts when content changes
      conflicts.value = parseConflicts(model.getValue())
      updateDecorations()
      emit('update:content', model.getValue())
      // Recreate zone widgets after content changes
      nextTick(() => {
        createZoneWidgets()
      })
    }
  })

  // Add keyboard shortcut listener
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  // Remove keyboard listener
  window.removeEventListener('keydown', handleKeydown)

  // Dispose zone widgets
  disposeZoneWidgets()

  if (model) {
    model.dispose()
    model = null
  }
  if (editor) {
    editor.dispose()
    editor = null
  }
})

// Watch for content changes
watch(() => props.content, (newValue) => {
  if (model && model.getValue() !== newValue) {
    model.setValue(newValue)
    conflicts.value = parseConflicts(newValue)
    updateDecorations()
  }
})

// Watch for language changes
watch(currentLanguage, async (newLanguage) => {
  if (model) {
    const monaco = await loader.init()
    monaco.editor.setModelLanguage(model, newLanguage)
  }
})

// Watch for theme changes
watch(() => store.theme, async (newTheme) => {
  if (editor) {
    const monaco = await loader.init()
    monaco.editor.setTheme(getMonacoTheme(newTheme))
  }
})

// Watch for mobile changes
watch(() => props.isMobile, (isMobile) => {
  if (editor) {
    editor.updateOptions({
      lineNumbers: isMobile ? 'off' : 'on'
    })
  }
})

// Expose methods for parent access
defineExpose({
  goToNextConflict,
  goToPrevConflict,
  hasUnresolvedConflicts,
  unresolvedCount,
  save
})
</script>

<template>
  <div class="conflict-editor-container flex flex-col h-full">
    <!-- Conflict toolbar -->
    <div class="conflict-toolbar border-b px-4 py-2 flex items-center gap-4">
      <div class="flex items-center gap-2">
        <span class="conflict-toolbar-text text-sm font-medium">
          {{ unresolvedCount }} unresolved conflict{{ unresolvedCount !== 1 ? 's' : '' }}
        </span>
      </div>
      <div class="flex items-center gap-1">
        <button
          @click="goToPrevConflict"
          :disabled="!hasUnresolvedConflicts"
          :class="['p-0 rounded-lg conflict-toolbar-btn', { 'opacity-50 cursor-not-allowed': !hasUnresolvedConflicts }]"
          title="Previous conflict"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 conflict-toolbar-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
          </svg>
        </button>
        <button
          @click="goToNextConflict"
          :disabled="!hasUnresolvedConflicts"
          :class="['p-0 rounded-lg conflict-toolbar-btn', { 'opacity-50 cursor-not-allowed': !hasUnresolvedConflicts }]"
          title="Next conflict"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 conflict-toolbar-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Monaco Editor -->
    <div ref="containerRef" class="monaco-editor-container flex-1 min-h-0"></div>

    <!-- Conflict resolution panel - simplified, only shows status -->
    <div v-if="hasUnresolvedConflicts" class="conflict-panel bg-sub border-t border-main px-4 py-2">
      <div class="flex items-center gap-2">
        <span class="text-sm text-sub">{{ conflicts.length - unresolvedCount }} of {{ conflicts.length }} conflicts resolved</span>
      </div>
    </div>

    <!-- Error message -->
    <div v-if="error" class="conflict-error-message border-t px-4 py-2 text-sm">
      {{ error }}
    </div>
  </div>
</template>

<style scoped>
.conflict-editor-container {
  width: 100%;
  height: 100%;
}

.monaco-editor-container {
  width: 100%;
}

:deep(.conflict-current-section) {
  background-color: var(--conflict-current-bg) !important;
}

:deep(.conflict-incoming-section) {
  background-color: var(--conflict-incoming-bg) !important;
}

:deep(.conflict-marker-line) {
  background-color: var(--conflict-bg) !important;
  font-weight: bold;
}

:deep(.conflict-separator-line) {
  background-color: rgba(156, 163, 175, 0.2) !important;
}

:deep(.conflict-glyph) {
  background-color: var(--conflict-glyph);
  width: 4px !important;
  margin-left: 3px;
  border-radius: 2px;
}

:deep(.conflict-marker-glyph) {
  background-color: var(--conflict-glyph);
  width: 8px !important;
  margin-left: 1px;
  border-radius: 4px;
}
</style>

<style>
/* Conflict toolbar styles - theme-aware using CSS variables */
.conflict-toolbar {
  background-color: var(--conflict-bg);
  border-color: var(--conflict-border);
}

.conflict-toolbar-text {
  color: var(--conflict-text);
}

.conflict-toolbar-icon {
  color: var(--conflict-text);
}

@media (hover: hover) {
  .conflict-toolbar-btn:hover:not(:disabled) {
    background-color: var(--conflict-hover);
  }
}

/* Inline conflict action buttons - global styles for dynamically created elements */
.conflict-action-zone {
  background-color: var(--conflict-bg);
  border: 1px solid var(--conflict-border);
  border-radius: 4px;
  margin: 2px 0;
  padding: 4px 6px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  pointer-events: auto !important;
  position: relative;
  z-index: 10;
}

.conflict-buttons {
  display: flex;
  gap: 4px;
  align-items: center;
  pointer-events: auto !important;
}

.conflict-btn {
  padding: 2px 6px;
  font-size: 10px;
  font-weight: 500;
  border-radius: 3px;
  border: 1px solid transparent;
  cursor: pointer !important;
  transition: all 0.15s ease;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  pointer-events: auto !important;
  user-select: none;
  white-space: nowrap;
  line-height: 1.4;
}

.conflict-btn-current {
  background-color: var(--conflict-current-bg);
  color: var(--conflict-current-text);
  border-color: color-mix(in srgb, var(--conflict-current-text) 30%, transparent);
}

@media (hover: hover) {
  .conflict-btn-current:hover {
    background-color: color-mix(in srgb, var(--conflict-current-text) 15%, transparent);
    border-color: color-mix(in srgb, var(--conflict-current-text) 50%, transparent);
  }
}

.conflict-btn-incoming {
  background-color: var(--conflict-incoming-bg);
  color: var(--conflict-incoming-text);
  border-color: color-mix(in srgb, var(--conflict-incoming-text) 30%, transparent);
}

@media (hover: hover) {
  .conflict-btn-incoming:hover {
    background-color: color-mix(in srgb, var(--conflict-incoming-text) 15%, transparent);
    border-color: color-mix(in srgb, var(--conflict-incoming-text) 50%, transparent);
  }
}

.conflict-btn-both {
  background-color: var(--conflict-both-bg);
  color: var(--conflict-both-text);
  border-color: color-mix(in srgb, var(--conflict-both-text) 30%, transparent);
}

@media (hover: hover) {
  .conflict-btn-both:hover {
    background-color: color-mix(in srgb, var(--conflict-both-text) 15%, transparent);
    border-color: color-mix(in srgb, var(--conflict-both-text) 50%, transparent);
  }
}

/* Error message styles - theme-aware */
.conflict-error-message {
  background-color: var(--conflict-error-bg);
  border-color: var(--conflict-error-border);
  color: var(--conflict-error-text);
}

/* Monaco Editor background override for green theme */
.theme-green .conflict-editor-container .monaco-editor,
.theme-green .conflict-editor-container .monaco-editor .margin,
.theme-green .conflict-editor-container .monaco-editor .monaco-editor-background {
  background-color: var(--bg-primary) !important;
}

.theme-green .conflict-editor-container .monaco-editor .cursors-layer .cursor {
  background-color: var(--text-primary);
  border-color: var(--text-primary);
}

.theme-green .conflict-editor-container .monaco-editor .view-lines {
  color: var(--text-primary);
}

/* Monaco Editor background override for parchment theme */
.theme-parchment .conflict-editor-container .monaco-editor,
.theme-parchment .conflict-editor-container .monaco-editor .margin,
.theme-parchment .conflict-editor-container .monaco-editor .monaco-editor-background {
  background-color: var(--bg-primary) !important;
}

.theme-parchment .conflict-editor-container .monaco-editor .cursors-layer .cursor {
  background-color: var(--text-primary);
  border-color: var(--text-primary);
}

.theme-parchment .conflict-editor-container .monaco-editor .view-lines {
  color: var(--text-primary);
}
</style>
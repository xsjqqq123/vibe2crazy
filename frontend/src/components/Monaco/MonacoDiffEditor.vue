<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { loader } from '@guolao/vue-monaco-editor'
import { useMainStore, type ThemeName } from '@/store'

interface Props {
  original?: string
  modified?: string
  language?: string
  readOnly?: boolean
  path?: string
  isMobile?: boolean
}

interface Emits {
  (e: 'update:modified', value: string): void
  (e: 'cursor-word', word: string, position: { lineNumber: number; column: number }): void
}

const props = withDefaults(defineProps<Props>(), {
  original: '',
  modified: '',
  language: 'plaintext',
  readOnly: false,
  path: '',
  isMobile: false
})

const emit = defineEmits<Emits>()
const store = useMainStore()

const containerRef = ref<HTMLElement | null>(null)
const currentDiffIndex = ref(0)
const totalDiffs = ref(0)

let diffEditor: any = null
let originalModel: any = null
let modifiedModel: any = null
let focusInterceptors: Array<(e: Event) => void> = []

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

  return languageMap[ext] || props.language || 'plaintext'
}

const currentLanguage = computed(() => props.path ? detectLanguage(props.path) : props.language)

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

// Update diff count when diff computation completes
const updateDiffCount = () => {
  if (!diffEditor) return

  const lineChanges = diffEditor.getLineChanges()
  totalDiffs.value = lineChanges?.length || 0
  // Always reset current index when diff updates (file switch or content change)
  currentDiffIndex.value = 0
}

// Navigate to the next diff hunk
const goToNextDiff = () => {
  if (!diffEditor || totalDiffs.value === 0) return

  try {
    const lineChanges = diffEditor.getLineChanges()
    if (lineChanges && lineChanges[currentDiffIndex.value]) {
      const change = lineChanges[currentDiffIndex.value]

      // Get the modified editor (right side)
      const modifiedEditor = diffEditor.getModifiedEditor()

      // Reveal the START line of the diff (not end line)
      modifiedEditor.revealLineInCenter(change.modifiedStartLineNumber)

      if (!props.isMobile) {
        modifiedEditor.focus()
      }

      // Increment index AFTER navigation, with wrap-around for next click
      currentDiffIndex.value = (currentDiffIndex.value + 1) % totalDiffs.value
    }
  } catch (e) {
    console.error('Error navigating to diff:', e)
  }
}

// Navigate to the previous diff hunk
const goToPrevDiff = () => {
  if (!diffEditor || totalDiffs.value === 0) return

  // Decrement index BEFORE navigation (go to previous)
  currentDiffIndex.value = currentDiffIndex.value === 0 ? totalDiffs.value - 1 : currentDiffIndex.value - 1

  try {
    const lineChanges = diffEditor.getLineChanges()
    if (lineChanges && lineChanges[currentDiffIndex.value]) {
      const change = lineChanges[currentDiffIndex.value]

      // Get the modified editor (right side)
      const modifiedEditor = diffEditor.getModifiedEditor()

      // Reveal the START line of the diff (not end line)
      modifiedEditor.revealLineInCenter(change.modifiedStartLineNumber)

      if (!props.isMobile) {
        modifiedEditor.focus()
      }
    }
  } catch (e) {
    console.error('Error navigating to diff:', e)
  }
}

// Check if there are any diffs to navigate
const hasDiffs = computed(() => totalDiffs.value > 0)

onMounted(async () => {
  if (!containerRef.value) return

  const monaco = await loader.init()

  // Define custom themes before creating editor
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

  // Wait for container to have proper dimensions before creating editor
  const waitForContainerReady = (): Promise<void> => {
    return new Promise((resolve) => {
      const checkDimensions = () => {
        if (containerRef.value && containerRef.value.offsetWidth > 0 && containerRef.value.offsetHeight > 0) {
          resolve()
        } else {
          requestAnimationFrame(checkDimensions)
        }
      }
      checkDimensions()
    })
  }

  await waitForContainerReady()

  // Create models
  originalModel = monaco.editor.createModel(props.original, currentLanguage.value)
  modifiedModel = monaco.editor.createModel(props.modified, currentLanguage.value)

  // Create diff editor
  diffEditor = monaco.editor.createDiffEditor(containerRef.value, {
    theme: getMonacoTheme(store.theme),
    automaticLayout: true,
    readOnly: props.readOnly,
    minimap: { enabled: !props.isMobile },
    fontSize: 14,
    lineNumbers: props.isMobile ? 'off' : 'on',
    scrollBeyondLastLine: false,
    wordWrap: 'on',
    enableSplitViewResizing: false,
    renderSideBySide: true,
    ignoreTrimWhitespace: false
  })

  // Set models
  diffEditor.setModel({
    original: originalModel,
    modified: modifiedModel
  })

  // Force layout and tokenization after editor creation
  requestAnimationFrame(() => {
    if (diffEditor && originalModel && modifiedModel) {
      diffEditor.layout()
      // Force re-tokenization for both models
      const origLang = originalModel.getLanguageId()
      const modLang = modifiedModel.getLanguageId()
      monaco.editor.setModelLanguage(originalModel, 'plaintext')
      monaco.editor.setModelLanguage(modifiedModel, 'plaintext')
      requestAnimationFrame(() => {
        monaco.editor.setModelLanguage(originalModel, origLang)
        monaco.editor.setModelLanguage(modifiedModel, modLang)
      })
    }
  })

  // Listen for diff update event - this fires when Monaco completes diff computation
  diffEditor.onDidUpdateDiff(() => {
    updateDiffCount()
  })

  // Listen for content changes in modified model
  modifiedModel.onDidChangeContent(() => {
    if (modifiedModel) {
      emit('update:modified', modifiedModel.getValue())
      // updateDiffCount() is handled by onDidUpdateDiff automatically
    }
  })

  // Track cursor position in modified editor for symbol preview
  const modifiedEditor = diffEditor.getModifiedEditor()
  if (props.isMobile) {
    modifiedEditor.onDidChangeCursorPosition((e: any) => {
      const model = modifiedEditor.getModel()
      if (model) {
        const word = model.getWordAtPosition(e.position)
        if (word && word.word) {
          emit('cursor-word', word.word, {
            lineNumber: e.position.lineNumber,
            column: e.position.column
          })
        }
      }
    })
  } else {
    modifiedEditor.onMouseUp((e: any) => {
      if (e.target.position) {
        const model = modifiedEditor.getModel()
        if (model) {
          const word = model.getWordAtPosition(e.target.position)
          if (word && word.word) {
            emit('cursor-word', word.word, {
              lineNumber: e.target.position.lineNumber,
              column: e.target.position.column
            })
          }
        }
      }
    })
  }

  // Mobile: intercept focus events to prevent keyboard popup
  if (props.isMobile) {
    const textareas = containerRef.value.querySelectorAll('textarea')
    textareas.forEach((textarea) => {
      const interceptor = (e: Event) => {
        const target = e.target as HTMLTextAreaElement
        target.blur()
      }
      focusInterceptors.push(interceptor)
      textarea.addEventListener('focus', interceptor)
    })
  }
})

onUnmounted(() => {
  // Remove focus interceptors
  if (focusInterceptors.length > 0 && containerRef.value) {
    const textareas = containerRef.value.querySelectorAll('textarea')
    textareas.forEach((textarea, index) => {
      if (focusInterceptors[index]) {
        textarea.removeEventListener('focus', focusInterceptors[index])
      }
    })
    focusInterceptors = []
  }

  if (originalModel) {
    originalModel.dispose()
    originalModel = null
  }
  if (modifiedModel) {
    modifiedModel.dispose()
    modifiedModel = null
  }
  if (diffEditor) {
    diffEditor.dispose()
    diffEditor = null
  }
})

// Watch for original value changes
watch(() => props.original, (newValue) => {
  if (originalModel && originalModel.getValue() !== newValue) {
    originalModel.setValue(newValue)
    // updateDiffCount() is handled by onDidUpdateDiff automatically
  }
})

// Watch for modified value changes
watch(() => props.modified, (newValue) => {
  if (modifiedModel && modifiedModel.getValue() !== newValue) {
    modifiedModel.setValue(newValue)
    // updateDiffCount() is handled by onDidUpdateDiff automatically
  }
})

// Watch for language changes
watch(currentLanguage, async (newLanguage) => {
  if (originalModel && modifiedModel) {
    const monaco = await loader.init()
    monaco.editor.setModelLanguage(originalModel, newLanguage)
    monaco.editor.setModelLanguage(modifiedModel, newLanguage)
  }
})

// Watch for theme changes
watch(() => store.theme, async (newTheme) => {
  if (diffEditor) {
    const monaco = await loader.init()
    monaco.editor.setTheme(getMonacoTheme(newTheme))
  }
})

// Watch for read-only changes
watch(() => props.readOnly, (readOnly) => {
  if (diffEditor) {
    diffEditor.updateOptions({ readOnly })
  }
})

// Watch for mobile changes to update line numbers and minimap
watch(() => props.isMobile, (isMobile) => {
  if (diffEditor) {
    diffEditor.updateOptions({
      lineNumbers: isMobile ? 'off' : 'on',
      minimap: { enabled: !isMobile }
    })
  }
})

// Expose the goToNextDiff method and getDiffEditor for parent access
defineExpose({
  goToNextDiff,
  goToPrevDiff,
  getDiffEditor: () => diffEditor,
  hasDiffs
})
</script>

<template>
  <div ref="containerRef" class="monaco-diff-editor-container"></div>
</template>

<style scoped>
.monaco-diff-editor-container {
  width: 100%;
  height: 100%;
}
</style>

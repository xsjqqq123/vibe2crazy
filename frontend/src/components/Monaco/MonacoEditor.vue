<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { loader } from '@guolao/vue-monaco-editor'
import { useMainStore, type ThemeName } from '@/store'
import { detectLanguage } from '@/utils/languageDetection'

interface Props {
  modelValue?: string
  language?: string
  readOnly?: boolean
  path?: string
  filePath?: string | null
  enableSaveShortcut?: boolean
  isMobile?: boolean
}

interface Emits {
  (e: 'update:modelValue', value: string): void
  (e: 'save'): void
  (e: 'previewMarkdown'): void
  (e: 'content-change'): void
  (e: 'cursor-word', word: string, position: { lineNumber: number; column: number }): void
  (e: 'find-references', selectedText: string): void
  (e: 'cursor-change', position: { lineNumber: number; column: number }): void
  (e: 'focus'): void
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  language: 'plaintext',
  readOnly: false,
  path: '',
  filePath: null,
  enableSaveShortcut: false,
  isMobile: false
})

const emit = defineEmits<Emits>()
const store = useMainStore()

const containerRef = ref<HTMLElement | null>(null)
let editor: any = null
let focusInterceptor: ((e: Event) => void) | null = null

const currentLanguage = computed(() => {
  const path = props.path || props.filePath
  return path ? detectLanguage(path) : props.language
})

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

  // Create Monaco editor
  editor = monaco.editor.create(containerRef.value, {
    value: props.modelValue,
    language: currentLanguage.value,
    theme: getMonacoTheme(store.theme),
    automaticLayout: true,
    readOnly: props.readOnly,
    minimap: { enabled: !props.isMobile },
    fontSize: 14,
    lineNumbers: props.isMobile ? 'off' : 'on',
    scrollBeyondLastLine: false,
    wordWrap: 'on',
    formatOnPaste: true,
    formatOnType: true
  })

  // Register Ctrl+S save command (always registered, but checks state before emitting)
  editor.addAction({
    id: 'save-file',
    label: 'Save File',
    keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS],
    run: () => {
      if (props.enableSaveShortcut) {
        emit('save')
      }
    }
  })

  // Add markdown preview action for .md files
  const filePath = props.path || props.filePath
  const isMarkdownFile = filePath?.toLowerCase().endsWith('.md')
  if (isMarkdownFile) {
    editor.addAction({
      id: 'preview-markdown',
      label: 'Preview Markdown',
      contextMenuGroupId: 'navigation',
      run: () => {
        emit('previewMarkdown')
      }
    })
  }

  // Add find references context menu action
  editor.addAction({
    id: 'find-references',
    label: 'Find References',
    contextMenuGroupId: 'navigation',
    run: () => {
      const selection = editor.getSelection()
      const model = editor.getModel()
      let searchText = ''

      // First try to get selected text
      if (selection && !selection.isEmpty()) {
        searchText = model?.getValueInRange(selection) || ''
      } else if (model && selection) {
        // No selection, get word at cursor position
        const word = model.getWordAtPosition(selection.getStartPosition())
        if (word && word.word) {
          searchText = word.word
        }
      }

      if (searchText) {
        emit('find-references', searchText)
      }
    }
  })

  // Listen for content changes
  editor.onDidChangeModelContent(() => {
    if (editor) {
      emit('update:modelValue', editor.getValue())
      emit('content-change')
    }
  })

  // Listen for cursor position changes
  editor.onDidChangeCursorPosition((e: any) => {
    if (editor) {
      emit('cursor-change', {
        lineNumber: e.position.lineNumber,
        column: e.position.column
      })
    }
  })

  // Listen for editor focus
  editor.onDidFocusEditorWidget(() => {
    emit('focus')
  })

  // Listen for cursor word based on device type
  // Mobile: use onDidChangeCursorPosition to support touch events
  // Desktop: use onMouseUp to only trigger on explicit mouse clicks (not keyboard navigation)
  if (props.isMobile) {
    editor.onDidChangeCursorPosition((e: any) => {
      if (editor) {
        const model = editor.getModel()
        if (model) {
          const word = model.getWordAtPosition(e.position)
          if (word && word.word) {
            emit('cursor-word', word.word, {
              lineNumber: e.position.lineNumber,
              column: e.position.column
            })
          }
        }
      }
    })
  } else {
    editor.onMouseUp((e: any) => {
      if (editor && e.target.position) {
        const model = editor.getModel()
        if (model) {
          const word = model.getWordAtPosition(e.target.position)
          if (word && word.word) {
            emit('cursor-word', word.word, { lineNumber: e.target.position.lineNumber, column: e.target.position.column })
          }
        }
      }
    })
  }

  // Mobile: intercept focus events to prevent keyboard popup
  if (props.isMobile) {
    const textarea = containerRef.value.querySelector('textarea')
    if (textarea) {
      focusInterceptor = (e: Event) => {
        const target = e.target as HTMLTextAreaElement
        target.blur()
      }
      textarea.addEventListener('focus', focusInterceptor)
    }
  }
})

onUnmounted(() => {
  // Remove focus interceptor
  if (focusInterceptor && containerRef.value) {
    const textarea = containerRef.value.querySelector('textarea')
    if (textarea) {
      textarea.removeEventListener('focus', focusInterceptor)
    }
  }

  if (editor) {
    editor.dispose()
    editor = null
  }
})

// Watch for model value changes
watch(() => props.modelValue, (newValue) => {
  if (editor && editor.getValue() !== newValue) {
    editor.setValue(newValue)
  }
})

// Watch for language changes
watch(currentLanguage, async (newLanguage) => {
  if (editor) {
    const model = editor.getModel()
    if (model) {
      const monaco = await loader.init()
      monaco.editor.setModelLanguage(model, newLanguage)
    }
  }
})

// Watch for theme changes
watch(() => store.theme, async (newTheme) => {
  if (editor) {
    const monaco = await loader.init()
    monaco.editor.setTheme(getMonacoTheme(newTheme))
  }
})

// Watch for read-only changes
watch(() => props.readOnly, (readOnly) => {
  if (editor) {
    editor.updateOptions({ readOnly })
  }
})

// Watch for mobile changes to update line numbers and minimap
watch(() => props.isMobile, (isMobile) => {
  if (editor) {
    editor.updateOptions({
      lineNumbers: isMobile ? 'off' : 'on',
      minimap: { enabled: !isMobile }
    })
  }
})

// Expose methods for parent components
defineExpose({
  goToLine: (lineNumber: number) => {
    if (editor) {
      editor.revealLineNearTop(lineNumber)
      editor.setSelection({
        startLineNumber: lineNumber,
        startColumn: 1,
        endLineNumber: lineNumber,
        endColumn: 1
      })
      if (!props.isMobile) {
        editor.focus()
      }
    }
  },
  getModel: () => editor?.getModel() || null,
  getValue: () => editor?.getValue() || '',
  // Position and scroll methods for state restoration
  getEditor: () => editor,
  getPosition: () => editor?.getPosition() || null,
  getScrollTop: () => editor?.getScrollTop() || 0,
  getScrollLeft: () => editor?.getScrollLeft() || 0,
  setScrollPosition: (pos: { scrollTop: number; scrollLeft: number }) => {
    if (editor) {
      editor.setScrollPosition(pos)
    }
  },
  setPosition: (pos: { lineNumber: number; column: number }) => {
    if (editor) {
      editor.setPosition(pos)
    }
  },
  revealLineInCenter: (lineNumber: number) => {
    if (editor) {
      editor.revealLineInCenter(lineNumber)
    }
  }
})
</script>

<template>
  <div ref="containerRef" class="monaco-editor-container"></div>
</template>

<style scoped>
.monaco-editor-container {
  width: 100%;
  height: 100%;
}
</style>

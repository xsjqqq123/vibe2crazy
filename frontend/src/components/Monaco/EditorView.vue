<script setup lang="ts">
import { ref, computed } from 'vue'
import MonacoEditor from './MonacoEditor.vue'
import EditorHistoryDropdown from './EditorHistoryDropdown.vue'
import { type HistoryEntry, type ViewType } from '@/types/editor'

interface Props {
  viewType: ViewType
  filePath: string | null
  content: string
  history: HistoryEntry[]
}

interface Emits {
  (e: 'update:content', value: string): void
  (e: 'history-select', entry: HistoryEntry): void
  (e: 'cursor-change', position: { lineNumber: number; column: number }): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Refs
const editorRef = ref<InstanceType<typeof MonacoEditor> | null>(null)

// Computed
const isPreview = computed(() => props.viewType !== 'main')

const viewLabel = computed(() => {
  const labels: Record<ViewType, string> = {
    main: 'Editor',
    preview1: 'Preview 1',
    preview2: 'Preview 2'
  }
  return labels[props.viewType]
})

const currentFile = computed(() => props.filePath)

// Local content with getter/setter for v-model (props cannot be mutated directly)
const localContent = computed({
  get: () => props.content,
  set: (val) => emit('update:content', val)
})

// Methods
const handleHistorySelect = (entry: HistoryEntry) => {
  emit('history-select', entry)
}

const handleCursorChange = (position: { lineNumber: number; column: number }) => {
  emit('cursor-change', position)
}

/**
 * Save the current cursor and scroll position
 * Returns a position object that can be passed to restorePosition
 */
const savePosition = (): { cursorPosition: { lineNumber: number; column: number } | null; scrollPosition: { top: number; left: number } | null } => {
  if (!editorRef.value) {
    return { cursorPosition: null, scrollPosition: null }
  }

  const editor = editorRef.value

  // Get cursor position
  const position = editor.getPosition()
  const cursorPosition = position ? { lineNumber: position.lineNumber, column: position.column } : null

  // Get scroll position
  const scrollTop = editor.getScrollTop()
  const scrollLeft = editor.getScrollLeft()
  const scrollPosition = { top: scrollTop, left: scrollLeft }

  return { cursorPosition, scrollPosition }
}

/**
 * Restore cursor and scroll position
 * Sets scroll position first, then cursor, and reveals the line in center
 */
const restorePosition = (pos: { cursorPosition: { lineNumber: number; column: number } | null; scrollPosition: { top: number; left: number } | null }) => {
  if (!editorRef.value || !pos.cursorPosition) {
    return
  }

  const editor = editorRef.value
  // Capture cursorPosition before setTimeout to avoid TypeScript narrowing issue
  const cursorPos = pos.cursorPosition
  const scrollPos = pos.scrollPosition

  // Use setTimeout to ensure the editor is ready
  setTimeout(() => {
    // Set scroll position first
    if (scrollPos) {
      editor.setScrollPosition({
        scrollTop: scrollPos.top,
        scrollLeft: scrollPos.left
      })
    }

    // Then set cursor position and reveal the line
    const { lineNumber, column } = cursorPos
    editor.setPosition({ lineNumber, column })
    editor.revealLineInCenter(lineNumber)

    // Note: We don't focus here to avoid stealing focus from the active editor
  }, 100)
}

/**
 * Get the Monaco model for symbol extraction
 */
const getModel = () => {
  return editorRef.value?.getModel() || null
}

/**
 * Jump to a specific line number
 * Used for preview files from search results
 */
const goToLine = (lineNumber: number) => {
  if (!editorRef.value) {
    return
  }

  // Use setTimeout to ensure the editor is ready
  setTimeout(() => {
    editorRef.value!.goToLine(lineNumber)
  }, 100)
}

// Expose methods for parent components
defineExpose({
  savePosition,
  restorePosition,
  goToLine,
  getModel
})
</script>

<template>
  <div class="editor-view flex flex-col h-full">
    <!-- Toolbar with history dropdown and view type indicator -->
    <div class="editor-toolbar flex items-center justify-between px-2 py-1 border-b border-main">
      <div class="flex items-center gap-2">
        <span class="view-type-label text-sm font-medium">{{ viewLabel }}</span>
        <span v-if="filePath" class="text-xs text-muted truncate max-w-48">{{ filePath.split('/').pop() }}</span>
      </div>
      <EditorHistoryDropdown
        :history="history"
        :current-file="currentFile"
        @select="handleHistorySelect"
      />
    </div>

    <!-- Monaco editor instance -->
    <div class="editor-container flex-1 min-h-0">
      <MonacoEditor
        ref="editorRef"
        v-model="localContent"
        :file-path="filePath"
        :read-only="isPreview"
        @cursor-change="handleCursorChange"
      />
    </div>
  </div>
</template>

<style scoped>
.editor-view {
  background: var(--bg-primary);
}

.editor-toolbar {
  min-height: 28px;
  flex-shrink: 0;
  background: var(--bg-primary);
}

.view-type-label {
  color: var(--text-primary);
}

.editor-container {
  min-height: 0;
}
</style>
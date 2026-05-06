<script setup lang="ts">
import { ref, computed } from 'vue'
import MonacoEditor from './MonacoEditor.vue'

/**
 * History entry structure for tracking file navigation history
 */
export interface HistoryEntry {
  filePath: string
  cursorPosition: { lineNumber: number; column: number } | null
  scrollPosition: { top: number; left: number } | null
  timestamp: number
}

/**
 * View type for the editor
 * - main: Primary editor view (editable)
 * - preview1: First preview pane (read-only)
 * - preview2: Second preview pane (read-only)
 */
export type ViewType = 'main' | 'preview1' | 'preview2'

interface Props {
  viewType: ViewType
  filePath: string | null
  content: string
  history: HistoryEntry[]
  isMobile?: boolean
}

interface Emits {
  (e: 'update:content', value: string): void
  (e: 'save'): void
  (e: 'preview-markdown'): void
  (e: 'history-select', entry: HistoryEntry): void
  (e: 'cursor-word', word: string, position: { lineNumber: number; column: number }): void
  (e: 'find-references', text: string): void
}

const props = withDefaults(defineProps<Props>(), {
  isMobile: false
})

const emit = defineEmits<Emits>()

// Refs
const editorRef = ref<InstanceType<typeof MonacoEditor> | null>(null)
const showHistoryDropdown = ref(false)

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

const fileName = computed(() => {
  if (!props.filePath) return ''
  return props.filePath.split('/').pop() || props.filePath
})

// Methods
const handleContentChange = (value: string) => {
  emit('update:content', value)
}

const handleSave = () => {
  emit('save')
}

const handlePreviewMarkdown = () => {
  emit('preview-markdown')
}

const handleCursorWord = (word: string, position: { lineNumber: number; column: number }) => {
  emit('cursor-word', word, position)
}

const handleFindReferences = (text: string) => {
  emit('find-references', text)
}

const handleHistorySelect = (entry: HistoryEntry) => {
  emit('history-select', entry)
  showHistoryDropdown.value = false
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

// Expose methods for parent components
defineExpose({
  savePosition,
  restorePosition,
  getModel,
  goToLine: (lineNumber: number) => {
    editorRef.value?.goToLine(lineNumber)
  },
  getValue: () => {
    return editorRef.value?.getValue() || ''
  }
})
</script>

<template>
  <div class="editor-view flex flex-col h-full">
    <!-- Toolbar with history dropdown and view type indicator -->
    <div class="editor-toolbar flex items-center justify-between px-2 py-1 border-b border-main bg-main">
      <div class="flex items-center gap-2 min-w-0">
        <span
          class="view-type-label text-xs font-medium px-2 py-0.5 rounded"
          :class="{
            'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400': viewType === 'main',
            'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400': viewType !== 'main'
          }"
        >
          {{ viewLabel }}
        </span>
        <span
          v-if="fileName"
          class="text-sm text-sub truncate"
          :title="filePath || ''"
        >
          {{ fileName }}
        </span>
      </div>

      <!-- History dropdown toggle -->
      <div class="relative" v-if="history.length > 0">
        <button
          @click="showHistoryDropdown = !showHistoryDropdown"
          class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          :title="'Recent files (' + history.length + ')'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </button>

        <!-- History dropdown panel -->
        <div
          v-if="showHistoryDropdown"
          class="absolute right-0 top-full mt-1 w-64 bg-white dark:bg-gray-800 border border-main rounded-md shadow-lg z-50 max-h-64 overflow-y-auto"
        >
          <div class="py-1">
            <div
              v-for="entry in history"
              :key="entry.filePath + entry.timestamp"
              @click="handleHistorySelect(entry)"
              class="px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer"
              :class="{ 'bg-blue-50 dark:bg-blue-900/20': entry.filePath === currentFile }"
            >
              <div class="text-sm font-medium text-main truncate">
                {{ entry.filePath.split('/').pop() }}
              </div>
              <div class="text-xs text-muted truncate">
                {{ entry.filePath }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Monaco editor instance -->
    <div class="editor-container flex-1 min-h-0">
      <MonacoEditor
        ref="editorRef"
        :model-value="content"
        :path="filePath || ''"
        :read-only="isPreview"
        :enable-save-shortcut="!isPreview"
        :is-mobile="isMobile"
        class="h-full"
        @update:model-value="handleContentChange"
        @save="handleSave"
        @preview-markdown="handlePreviewMarkdown"
        @cursor-word="handleCursorWord"
        @find-references="handleFindReferences"
      />
    </div>
  </div>
</template>

<style scoped>
.editor-view {
  background: var(--bg-color, #fff);
}

.editor-toolbar {
  min-height: 28px;
  flex-shrink: 0;
}

.editor-container {
  min-height: 0;
}
</style>
<script setup lang="ts">
import { ref, computed } from 'vue'

/**
 * History entry structure for tracking file navigation history
 */
export interface HistoryEntry {
  filePath: string
  cursorPosition: { line: number; column: number }
  scrollPosition: { top: number; left: number }
  timestamp: number
}

interface Props {
  history: HistoryEntry[]
  currentFile: string | null
}

interface Emits {
  (e: 'select', entry: HistoryEntry): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const showDropdown = ref(false)

// Sort history by timestamp (most recent first)
const sortedHistory = computed(() => {
  return [...props.history].sort((a, b) => b.timestamp - a.timestamp)
})

const handleSelect = (entry: HistoryEntry) => {
  emit('select', entry)
  showDropdown.value = false
}

const getFileName = (filePath: string) => {
  return filePath.split('/').pop() || filePath
}
</script>

<template>
  <div class="editor-history-dropdown relative">
    <!-- History dropdown toggle -->
    <button
      v-if="history.length > 0"
      class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
      :title="'Recent files (' + history.length + ')'"
      @click="showDropdown = !showDropdown"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        class="h-4 w-4 text-muted"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    </button>

    <!-- History dropdown panel -->
    <div
      v-if="showDropdown && history.length > 0"
      class="absolute right-0 top-full mt-1 w-64 bg-white dark:bg-gray-800 border border-main rounded-md shadow-lg z-50 max-h-64 overflow-y-auto"
    >
      <div class="py-1">
        <div
          v-for="entry in sortedHistory"
          :key="entry.filePath + entry.timestamp"
          class="px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer"
          :class="{ 'bg-blue-50 dark:bg-blue-900/20': entry.filePath === currentFile }"
          @click="handleSelect(entry)"
        >
          <div class="text-sm font-medium text-main truncate">
            {{ getFileName(entry.filePath) }}
          </div>
          <div class="text-xs text-muted truncate">
            {{ entry.filePath }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.editor-history-dropdown {
  display: inline-block;
}
</style>
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { type HistoryEntry } from '@/types/editor'

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

// Click-outside handler to close dropdown
const handleClickOutside = (event: MouseEvent) => {
  const dropdownEl = document.querySelector('.editor-history-dropdown')
  if (dropdownEl && !dropdownEl.contains(event.target as Node)) {
    showDropdown.value = false
  }
}

onMounted(() => {
  window.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div class="editor-history-dropdown relative flex items-center">
    <!-- History dropdown toggle -->
    <button
      v-if="history.length > 0"
      class="p-0 rounded-lg hover:bg-sub transition-colors"
      :title="'Recent files (' + history.length + ')'"
      @click.stop="showDropdown = !showDropdown"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        class="h-5 w-5 text-sub"
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
      class="absolute right-0 top-full mt-1 w-64 bg-main border border-main rounded-lg shadow-lg z-50 max-h-64 overflow-y-auto"
    >
      <div class="py-1">
        <div
          v-for="entry in sortedHistory"
          :key="entry.filePath + entry.timestamp"
          class="px-3 py-2 hover:bg-sub cursor-pointer"
          :class="{ 'item-selected': entry.filePath === currentFile }"
          @click.stop="handleSelect(entry)"
        >
          <div class="text-sm font-medium text-main truncate">
            {{ getFileName(entry.filePath) }}
          </div>
          <div class="text-xs text-sub truncate">
            {{ entry.filePath }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.editor-history-dropdown {
  display: flex;
}
</style>
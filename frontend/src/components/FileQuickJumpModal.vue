<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'

interface Props {
  show: boolean
  taskId: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
  'select-file': [filePath: string]
}>()

// State
const searchQuery = ref('')
const results = ref<string[]>([])
const loading = ref(false)
const error = ref('')
const selectedIndex = ref(0)
const inputRef = ref<HTMLInputElement>()
let searchTimeout: number | null = null

// Debounced search - wait 300ms after user stops typing
watch(searchQuery, () => {
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }
  searchTimeout = window.setTimeout(() => {
    performSearch()
  }, 300)
})

// Watch results to update selected index
watch(() => results.value.length, (newLength) => {
  if (newLength > 0 && selectedIndex.value >= newLength) {
    selectedIndex.value = 0
  }
})

// Load files when modal opens
watch(() => props.show, (newShow) => {
  if (newShow) {
    searchQuery.value = ''
    results.value = []
    selectedIndex.value = 0
    error.value = ''
    nextTick(() => {
      inputRef.value?.focus()
    })
    // Load initial files (first 100)
    performSearch()
  } else {
    // Clear search timeout when modal closes
    if (searchTimeout) {
      clearTimeout(searchTimeout)
      searchTimeout = null
    }
  }
})

// Perform server-side search
const performSearch = async () => {
  loading.value = true
  error.value = ''
  try {
    // Import filesApi dynamically to avoid circular dependency
    const filesApiModule = await import('@/api/files')
    const filesApi = filesApiModule.default
    const result = await filesApi.searchFiles(props.taskId, searchQuery.value, 100)
    results.value = result.files
  } catch (err: any) {
    error.value = err.message || 'Failed to search files'
    console.error('Failed to search files:', err)
  } finally {
    loading.value = false
  }
}

// Handle file selection
const selectFile = (filePath: string) => {
  emit('select-file', filePath)
  emit('close')
}

// Keyboard navigation
const handleKeyDown = (e: KeyboardEvent) => {
  if (!props.show) return

  // ESC to close
  if (e.key === 'Escape') {
    emit('close')
    return
  }

  const searchResults = results.value
  if (searchResults.length === 0) return

  // Arrow down
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    selectedIndex.value = (selectedIndex.value + 1) % searchResults.length
    return
  }

  // Arrow up
  if (e.key === 'ArrowUp') {
    e.preventDefault()
    selectedIndex.value = selectedIndex.value <= 0
      ? searchResults.length - 1
      : selectedIndex.value - 1
    return
  }

  // Enter to open selected file
  if (e.key === 'Enter' && searchResults.length > 0) {
    e.preventDefault()
    selectFile(searchResults[selectedIndex.value])
    return
  }
}

// Scroll selected item into view
watch(selectedIndex, (newIndex) => {
  nextTick(() => {
    const items = document.querySelectorAll('.file-quick-jump-item')
    const selected = items[newIndex] as HTMLElement
    if (selected) {
      selected.scrollIntoView({ block: 'nearest' })
    }
  })
})

// Global keyboard handler for Ctrl+P
const handleGlobalKeydown = (e: KeyboardEvent) => {
  if (e.ctrlKey && e.key === 'p') {
    e.preventDefault()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeyDown)
  document.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyDown)
  document.removeEventListener('keydown', handleGlobalKeydown)
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="show" class="file-quick-jump-overlay" @click.self="$emit('close')">
        <div class="file-quick-jump-container">
          <!-- Header -->
          <div class="file-quick-jump-header">
            <input
              ref="inputRef"
              v-model="searchQuery"
              type="text"
              placeholder="Search files... (Ctrl+P)"
              class="file-quick-jump-input"
            />
            <button
              @click="$emit('close')"
              class="file-quick-jump-close"
              title="Close (ESC)"
            >
              ✕
            </button>
          </div>

          <!-- Results -->
          <div class="file-quick-jump-results">
            <div v-if="loading" class="file-quick-jump-loading">
              <div class="spinner"></div>
              <span>Searching...</span>
            </div>
            <div v-else-if="error" class="file-quick-jump-error">
              {{ error }}
            </div>
            <div v-else-if="results.length === 0" class="file-quick-jump-empty">
              {{ searchQuery ? 'No matching files found' : 'No files' }}
            </div>
            <div v-else class="file-quick-jump-list">
              <div
                v-for="(file, index) in results"
                :key="file"
                :class="[
                  'file-quick-jump-item',
                  { 'selected': index === selectedIndex }
                ]"
                @click="selectFile(file)"
              >
                <span class="file-quick-jump-item-icon">📄</span>
                <span class="file-quick-jump-item-path">{{ file }}</span>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="file-quick-jump-footer">
            <span class="file-quick-jump-hint">
              <kbd>↑</kbd> <kbd>↓</kbd> Navigate · <kbd>Enter</kbd> Open · <kbd>ESC</kbd> Close
            </span>
            <span class="file-quick-jump-count">
              {{ results.length }} result{{ results.length !== 1 ? 's' : '' }}
              <span v-if="results.length >= 100"> (limited to 100)</span>
            </span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.file-quick-jump-overlay {
  position: fixed;
  inset: 0;
  background-color: rgb(0 0 0 / 0.5);
  backdrop-filter: blur(2px);
  z-index: 9999;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 10vh;
}

.file-quick-jump-container {
  width: 90%;
  max-width: 700px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  background-color: rgb(31 41 55); /* gray-800 */
  border-radius: 0.5rem;
  box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 10px 10px -5px rgb(0 0 0 / 0.04);
  overflow: hidden;
}

/* Header */
.file-quick-jump-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  border-bottom: 1px solid rgb(55 65 81); /* gray-700 */
}

.file-quick-jump-input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  background-color: rgb(17 24 39); /* gray-900 */
  color: rgb(255 255 255);
  border: 1px solid rgb(55 65 81); /* gray-700 */
  border-radius: 0.375rem;
  font-size: 0.875rem;
  outline: none;
}

.file-quick-jump-input:focus {
  border-color: rgb(59 130 246); /* blue-500 */
}

.file-quick-jump-input::placeholder {
  color: rgb(156 163 175); /* gray-400 */
}

.file-quick-jump-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  padding: 0;
  background-color: rgb(75 85 99); /* gray-600 */
  color: rgb(255 255 255);
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 1.25rem;
  line-height: 1;
  transition: background-color 0.15s ease;
}

@media (hover: hover) {
.file-quick-jump-close:hover {
  background-color: rgb(107 114 128); /* gray-500 */
}
}

/* Results */
.file-quick-jump-results {
  flex: 1;
  overflow-y: auto;
  min-height: 200px;
}

.file-quick-jump-loading,
.file-quick-jump-error,
.file-quick-jump-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 3rem;
  color: rgb(156 163 175); /* gray-400 */
  font-size: 0.875rem;
}

.file-quick-jump-error {
  color: rgb(248 113 113); /* red-400 */
}

.file-quick-jump-list {
  display: flex;
  flex-direction: column;
}

.file-quick-jump-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.625rem 1rem;
  cursor: pointer;
  transition: background-color 0.1s ease;
}

.file-quick-jump-item.selected {
  background-color: rgb(59 130 246); /* blue-500 */
}

.file-quick-jump-item-icon {
  flex-shrink: 0;
  opacity: 0.7;
}

.file-quick-jump-item-path {
  flex: 1;
  color: rgb(229 231 235); /* gray-200 */
  font-size: 0.875rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-quick-jump-item.selected .file-quick-jump-item-path {
  color: rgb(255 255 255);
}

/* Footer */
.file-quick-jump-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.5rem 1rem;
  border-top: 1px solid rgb(55 65 81); /* gray-700 */
  background-color: rgb(17 24 39); /* gray-900 */
}

.file-quick-jump-hint {
  color: rgb(156 163 175); /* gray-400 */
  font-size: 0.75rem;
}

.file-quick-jump-hint kbd {
  display: inline-block;
  padding: 0.125rem 0.375rem;
  background-color: rgb(55 65 81); /* gray-700 */
  border: 1px solid rgb(75 85 99); /* gray-600 */
  border-radius: 0.25rem;
  font-size: 0.6875rem;
  font-family: monospace;
  margin: 0 0.125rem;
}

.file-quick-jump-count {
  color: rgb(156 163 175); /* gray-400 */
  font-size: 0.75rem;
}

/* Spinner */
.spinner {
  width: 1.5rem;
  height: 1.5rem;
  border: 2px solid rgb(55 65 81); /* gray-700 */
  border-top-color: rgb(59 130 246); /* blue-500 */
  border-radius: 9999px;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Scrollbar */
.file-quick-jump-results::-webkit-scrollbar {
  width: 0.5rem;
}

.file-quick-jump-results::-webkit-scrollbar-track {
  background-color: rgb(17 24 39); /* gray-900 */
}

.file-quick-jump-results::-webkit-scrollbar-thumb {
  background-color: rgb(55 65 81); /* gray-700 */
  border-radius: 0.25rem;
}

.file-quick-jump-results::-webkit-scrollbar-thumb:hover {
  background-color: rgb(75 85 99); /* gray-600 */
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .file-quick-jump-container {
    width: 95%;
    max-height: 80vh;
  }

  .file-quick-jump-footer {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }
}
</style>
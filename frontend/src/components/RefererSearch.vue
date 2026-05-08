<script setup lang="ts">
import { ref, computed } from 'vue'
import searchApi, { type SearchMatch } from '@/api/search'

const props = defineProps<{
  taskId: string
  worktreePath: string
  currentFile: string
  query: string
  results: SearchMatch[]
  total: number
  totalMatches: number
  page: number
  expandedFiles: Set<string>
}>()

const emit = defineEmits<{
  selectFile: [filePath: string, lineNumber: number]
  previewFile: [filePath: string, lineNumber: number]
  'update:query': [value: string]
  'update:results': [value: SearchMatch[]]
  'update:total': [value: number]
  'update:totalMatches': [value: number]
  'update:page': [value: number]
  'update:expandedFiles': [value: Set<string>]
}>()

const perPage = 20
const loading = ref(false)
const hasSearched = ref(false)
const searchInputRef = ref<HTMLInputElement | null>(null)

// Focus the search input
const focusInput = () => {
  if (searchInputRef.value) {
    searchInputRef.value.focus()
  }
}

// Expose focusInput for parent component to call
defineExpose({ focusInput })

// Use computed setters for two-way binding
const queryModel = computed({
  get: () => props.query,
  set: (val) => emit('update:query', val)
})

const resultsModel = computed({
  get: () => props.results,
  set: (val) => emit('update:results', val)
})

const totalModel = computed({
  get: () => props.total,
  set: (val) => emit('update:total', val)
})

const totalMatchesModel = computed({
  get: () => props.totalMatches,
  set: (val) => emit('update:totalMatches', val)
})

const pageModel = computed({
  get: () => props.page,
  set: (val) => emit('update:page', val)
})

const expandedFilesModel = computed({
  get: () => props.expandedFiles,
  set: (val) => emit('update:expandedFiles', val)
})

const totalPages = computed(() => Math.ceil(totalModel.value / perPage))
const startIndex = computed(() => (pageModel.value - 1) * perPage + 1)
const endIndex = computed(() => Math.min(pageModel.value * perPage, totalModel.value))

// Group results by file
const groupedResults = computed(() => {
  const groups: Map<string, SearchMatch[]> = new Map()
  for (const r of resultsModel.value) {
    if (!groups.has(r.file)) {
      groups.set(r.file, [])
    }
    groups.get(r.file)!.push(r)
  }
  return Array.from(groups.entries()).map(([file, matches]) => ({
    file,
    matches: matches.slice(0, 5),
    totalMatches: matches.length
  }))
})

const toggleFile = (file: string) => {
  const newSet = new Set(expandedFilesModel.value)
  if (newSet.has(file)) {
    newSet.delete(file)
  } else {
    newSet.add(file)
  }
  expandedFilesModel.value = newSet
}

const search = async (pageNum: number = 1) => {
  if (!queryModel.value.trim()) return
  loading.value = true
  hasSearched.value = true
  try {
    const data = await searchApi.grep({
      task_id: props.taskId,
      query: queryModel.value,
      page: pageNum,
      per_page: perPage,
      current_file: props.currentFile || undefined
    })
    resultsModel.value = data.results
    totalModel.value = data.total
    totalMatchesModel.value = data.total_matches
    pageModel.value = pageNum
    // Auto-expand first 3 file groups
    const fileSet = new Set<string>()
    for (const r of data.results) {
      fileSet.add(r.file)
      if (fileSet.size >= 3) break
    }
    expandedFilesModel.value = fileSet
  } catch (e) {
    console.error('Search failed:', e)
  } finally {
    loading.value = false
  }
}

const clear = async () => {
  queryModel.value = ''
  resultsModel.value = []
  totalModel.value = 0
  totalMatchesModel.value = 0
  pageModel.value = 1
  expandedFilesModel.value = new Set()
  hasSearched.value = false
  try {
    await searchApi.clearCache(props.taskId)
  } catch (e) {
    console.error('Clear cache failed:', e)
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter') {
    search(1)
  }
}

const handleResultClick = (match: SearchMatch) => {
  // 将绝对路径转为相对路径
  let filePath = match.file
  if (props.worktreePath && filePath.startsWith(props.worktreePath)) {
    filePath = filePath.slice(props.worktreePath.length).replace(/^\//, '')
  }
  emit('selectFile', filePath, match.line)
}

const handleMiddleClick = (e: MouseEvent, match: SearchMatch) => {
  // Only handle middle-click (button === 1)
  if (e.button !== 1) return

  // Prevent default browser behavior
  e.preventDefault()

  // Convert absolute path to relative path
  let filePath = match.file
  if (props.worktreePath && filePath.startsWith(props.worktreePath)) {
    filePath = filePath.slice(props.worktreePath.length).replace(/^\//, '')
  }
  emit('previewFile', filePath, match.line)
}

const prevPage = () => {
  if (pageModel.value > 1) search(pageModel.value - 1)
}

const nextPage = () => {
  if (pageModel.value < totalPages.value) search(pageModel.value + 1)
}

// Get relative path from worktree root
const getRelativePath = (path: string) => {
  if (props.worktreePath && path.startsWith(props.worktreePath)) {
    return path.slice(props.worktreePath.length).replace(/^\//, '')
  }
  return path
}

// Extract filename from full path
const getFileName = (path: string) => {
  const relative = getRelativePath(path)
  const parts = relative.split('/')
  return parts[parts.length - 1]
}

const getFileDir = (path: string) => {
  const relative = getRelativePath(path)
  const parts = relative.split('/')
  parts.pop()
  const dir = parts.join('/')
  if (dir.length > 45) {
    return '...' + dir.slice(-42)
  }
  return dir
}

// Highlight matching text in content
const highlightMatch = (content: string) => {
  if (!queryModel.value.trim()) return content
  const regex = new RegExp(`(${queryModel.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return content.replace(regex, '<mark class="search-highlight">$1</mark>')
}
</script>

<template>
  <div class="referer-search">
    <!-- Search Bar -->
    <div class="search-header mb-2">
      <div class="search-input-wrapper">
        <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/>
          <path d="m21 21-4.35-4.35"/>
        </svg>
        <input
          ref="searchInputRef"
          v-model="queryModel"
          type="text"
          placeholder="Search in project..."
          class="search-input"
          @keydown="handleKeydown"
        />
        <button v-if="queryModel" @click="clear" class="clear-btn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6 6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>
      <button @click="search(1)" class="btn btn-primary search-btn" :disabled="loading">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/>
          <path d="m21 21-4.35-4.35"/>
        </svg>
      </button>
    </div>

    <!-- Results Summary -->
    <div v-if="total > 0" class="results-summary mb-2 text-sm text-sub">
      <span class="count-number">{{ totalMatches.toLocaleString() }}</span> matches · Page {{ page }} of {{ totalPages.toLocaleString() }}
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center py-4">
      <div class="spinner"></div>
    </div>

    <!-- Empty States -->
    <div v-else-if="results.length === 0 && hasSearched" class="text-sm text-sub py-2">
      No matches found
    </div>

    <div v-else-if="results.length === 0 && !hasSearched" class="text-sm text-sub py-2">
      Type to search across all project files
    </div>

    <!-- Results List -->
    <div v-else class="results-list space-y-1">
      <div
        v-for="group in groupedResults"
        :key="group.file"
        class="result-group"
      >
        <!-- File Header -->
        <div
          class="file-header flex items-center justify-between cursor-pointer hover:bg-sub rounded px-2 py-1 transition-colors"
          :class="{ 'bg-sub': expandedFiles.has(group.file) }"
          @click="toggleFile(group.file)"
        >
          <div class="flex items-center gap-2 min-w-0 flex-1">
            <svg class="w-4 h-4 text-sub flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <path d="M14 2v6h6"/>
            </svg>
            <div class="min-w-0">
              <div class="file-name text-sm font-medium truncate">{{ getFileName(group.file) }}</div>
              <div class="file-dir text-xs text-sub truncate">{{ getFileDir(group.file) }}</div>
            </div>
          </div>
          <svg
            class="w-4 h-4 text-sub transition-transform flex-shrink-0"
            :class="{ 'rotate-180': expandedFiles.has(group.file) }"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path d="m6 9 6 6 6-6"/>
          </svg>
        </div>

        <!-- Expanded Matches -->
        <Transition name="expand">
          <div v-if="expandedFiles.has(group.file)" class="matches-container ml-5 mt-1 border-l-2 border-accent">
            <div
              v-for="match in group.matches"
              :key="`${match.file}:${match.line}`"
              class="match-item px-3 py-1 text-sm cursor-pointer hover:bg-sub transition-colors"
              @click="handleResultClick(match)"
              @mousedown="handleMiddleClick($event, match)"
            >
              <span class="text-sub w-6 inline-block text-right mr-2">{{ match.line }}</span>
              <span class="font-mono" v-html="highlightMatch(match.content)"></span>
            </div>
            <div v-if="group.totalMatches > 5" class="px-3 py-1 text-xs text-sub italic">
              +{{ group.totalMatches - 5 }} more
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="total > 0" class="pagination flex items-center justify-between mt-3 pt-2 border-t border-main">
      <span class="text-sm text-sub">Showing {{ startIndex }}-{{ endIndex }}</span>
      <div class="flex items-center gap-1">
        <button
          @click="prevPage"
          :disabled="page <= 1"
          class="px-2 py-0.5 rounded border border-main bg-main hover:bg-sub
                 disabled:opacity-50 disabled:cursor-not-allowed
                 transition-colors text-sm text-main"
        >
          Prev
        </button>
        <span class="text-sm text-sub px-2">{{ page }}/{{ totalPages }}</span>
        <button
          @click="nextPage"
          :disabled="page >= totalPages"
          class="px-2 py-0.5 rounded border border-main bg-main hover:bg-sub
                 disabled:opacity-50 disabled:cursor-not-allowed
                 transition-colors text-sm text-main"
        >
          Next
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.referer-search {
  font-family: 'Source Sans Pro', -apple-system, BlinkMacSystemFont, sans-serif;
}

.search-header {
  display: flex;
  gap: 8px;
}

.search-input-wrapper {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 10px;
  width: 14px;
  height: 14px;
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 6px 28px 6px 32px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: all 0.2s ease;
}

.search-input:focus {
  border-color: var(--accent-color);
}

.search-input::placeholder {
  color: var(--text-muted);
}

.clear-btn {
  position: absolute;
  right: 6px;
  width: 16px;
  height: 16px;
  padding: 0;
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.clear-btn:hover {
  color: var(--text-primary);
}

.clear-btn svg {
  width: 10px;
  height: 10px;
}

.search-btn {
  padding: 6px 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.search-btn svg {
  width: 14px;
  height: 14px;
}

.results-summary .count-number {
  font-weight: 600;
  color: var(--accent-color);
}

.file-name {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  color: var(--text-primary);
}

.match-item :deep(.search-highlight) {
  background: rgba(251, 191, 36, 0.3);
  color: var(--accent-color);
  padding: 0 1px;
  border-radius: 2px;
}

/* Transitions */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>

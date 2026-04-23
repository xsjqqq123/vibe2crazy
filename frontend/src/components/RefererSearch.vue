<script setup lang="ts">
import { ref, computed } from 'vue'
import searchApi, { type SearchMatch } from '@/api/search'

const props = defineProps<{
  taskId: string
}>()

const emit = defineEmits<{
  selectFile: [filePath: string, lineNumber: number]
}>()

const query = ref('')
const results = ref<SearchMatch[]>([])
const total = ref(0)
const page = ref(1)
const perPage = 20
const loading = ref(false)
const expandedFiles = ref<Set<string>>(new Set())

const totalPages = computed(() => Math.ceil(total.value / perPage))
const startIndex = computed(() => (page.value - 1) * perPage + 1)
const endIndex = computed(() => Math.min(page.value * perPage, total.value))

// Group results by file
const groupedResults = computed(() => {
  const groups: Map<string, SearchMatch[]> = new Map()
  for (const r of results.value) {
    if (!groups.has(r.file)) {
      groups.set(r.file, [])
    }
    groups.get(r.file)!.push(r)
  }
  return Array.from(groups.entries()).map(([file, matches]) => ({
    file,
    matches: matches.slice(0, 3),
    totalMatches: matches.length
  }))
})

const toggleFile = (file: string) => {
  if (expandedFiles.value.has(file)) {
    expandedFiles.value.delete(file)
  } else {
    expandedFiles.value.add(file)
  }
}

const search = async (pageNum: number = 1) => {
  if (!query.value.trim()) return
  loading.value = true
  try {
    const data = await searchApi.grep({
      task_id: props.taskId,
      query: query.value,
      page: pageNum,
      per_page: perPage
    })
    results.value = data.results
    total.value = data.total
    page.value = pageNum
    expandedFiles.value.clear()
  } catch (e) {
    console.error('Search failed:', e)
  } finally {
    loading.value = false
  }
}

const clear = async () => {
  query.value = ''
  results.value = []
  total.value = 0
  page.value = 1
  expandedFiles.value.clear()
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
  emit('selectFile', match.file, match.line)
}

const prevPage = () => {
  if (page.value > 1) search(page.value - 1)
}

const nextPage = () => {
  if (page.value < totalPages.value) search(page.value + 1)
}
</script>

<template>
  <div class="referer-search h-full flex flex-col min-h-0">
    <!-- Search Bar -->
    <div class="p-3 border-b border-main shrink-0">
      <div class="flex gap-2">
        <input
          v-model="query"
          type="text"
          placeholder="Search..."
          class="input flex-1 text-sm"
          @keydown="handleKeydown"
        />
        <button @click="search(1)" class="btn btn-primary text-sm" :disabled="loading">
          Search
        </button>
        <button @click="clear" class="btn btn-secondary text-sm">
          Clear
        </button>
      </div>
      <div v-if="total > 0" class="text-xs text-muted mt-2">
        {{ total }} matches found
      </div>
    </div>

    <!-- Results List -->
    <div class="flex-1 overflow-y-auto min-h-0">
      <div v-if="loading" class="flex items-center justify-center py-8">
        <div class="spinner"></div>
      </div>

      <div v-else-if="results.length === 0 && query" class="text-center py-8 text-sm text-muted">
        No results found
      </div>

      <div v-else-if="results.length === 0" class="text-center py-8 text-sm text-muted">
        Enter a search term
      </div>

      <div v-else class="divide-y divide-main">
        <div
          v-for="group in groupedResults"
          :key="group.file"
          class="border-b border-main"
        >
          <!-- File Header (clickable to expand/collapse) -->
          <div
            class="px-3 py-2 text-sm cursor-pointer hover:bg-sub transition-colors"
            @click="toggleFile(group.file)"
          >
            <span class="text-primary font-medium">{{ group.file }}</span>
            <span class="text-muted ml-2">({{ group.totalMatches }} matches)</span>
            <svg
              class="inline w-4 h-4 ml-1 transition-transform"
              :class="{ 'rotate-90': expandedFiles.has(group.file) }"
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>

          <!-- Expanded Matches -->
          <div v-if="expandedFiles.has(group.file)" class="bg-sub/50">
            <div
              v-for="match in group.matches"
              :key="`${match.file}:${match.line}`"
              class="px-4 py-1 text-xs cursor-pointer hover:bg-primary/10 transition-colors font-mono"
              @click="handleResultClick(match)"
            >
              <span class="text-muted w-8 inline-block text-right mr-3 shrink-0">{{ match.line }}</span>
              <span class="text-main">{{ match.content }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="total > 0" class="p-3 border-t border-main shrink-0">
      <div class="flex items-center justify-between text-sm">
        <span class="text-muted">
          Showing {{ startIndex }}-{{ endIndex }} of {{ total }}
        </span>
        <div class="flex gap-2">
          <button
            @click="prevPage"
            :disabled="page <= 1"
            class="btn btn-secondary text-xs px-2 py-1"
          >
            Prev
          </button>
          <span class="text-muted self-center px-2">
            Page {{ page }}
          </span>
          <button
            @click="nextPage"
            :disabled="page >= totalPages"
            class="btn btn-secondary text-xs px-2 py-1"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.referer-search {
  background-color: var(--bg-secondary);
}
</style>
<script setup lang="ts">
import { computed } from 'vue'
import type { NotebookSearchResult } from '@/api/notebooks'

interface Props {
  query: string
  results: NotebookSearchResult[]
  loading: boolean
  total: number
  truncated: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  select: [id: string]
}>()

interface Segment {
  text: string
  match: boolean
  /** Stable list key — adjacent segments can repeat the same text. */
  key: string
}

/**
 * Split a snippet around the query so it can be highlighted without v-html —
 * the snippet is file content from disk and must stay inert.
 */
function segments(text: string, query: string): Segment[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return [{ text, match: false, key: '0-0' }]

  const haystack = text.toLowerCase()
  const parts: Segment[] = []
  const push = (value: string, match: boolean) => {
    parts.push({ text: value, match, key: `${parts.length}-${match ? 'm' : 't'}` })
  }

  let cursor = 0
  let index = haystack.indexOf(needle)
  while (index !== -1) {
    if (index > cursor) push(text.slice(cursor, index), false)
    push(text.slice(index, index + needle.length), true)
    cursor = index + needle.length
    index = haystack.indexOf(needle, cursor)
  }
  if (cursor < text.length) push(text.slice(cursor), false)
  return parts
}

const highlighted = computed(() =>
  props.results.map((result) => ({
    ...result,
    titleParts: segments(result.title, props.query),
    snippetParts: result.snippet ? segments(result.snippet, props.query) : []
  }))
)
</script>

<template>
  <div class="flex-1 min-h-0 flex flex-col">
    <div class="px-2 py-1.5 text-xs text-muted shrink-0">
      <span v-if="loading">Searching…</span>
      <span v-else>{{ total }} result<span v-if="total !== 1">s</span><span v-if="truncated"> (truncated)</span></span>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto px-1 pb-2">
      <p v-if="!loading && results.length === 0" class="px-3 py-4 text-sm text-muted">
        No matching notes
      </p>

      <div
        v-for="result in highlighted"
        :key="result.id"
        class="search-result px-2 py-2 rounded-md cursor-pointer"
        :title="`${result.group_name} / ${result.filename}`"
        @click="emit('select', result.id)"
      >
        <div class="flex items-center gap-1.5">
          <span class="match-badge" :class="result.match_type === 'filename' ? 'is-name' : 'is-body'">
            {{ result.match_type === 'filename' ? 'Name' : 'Body' }}
          </span>
          <span class="flex-1 truncate text-sm text-main">
            <template v-for="part in result.titleParts" :key="part.key">
              <mark v-if="part.match" class="search-hit">{{ part.text }}</mark>
              <template v-else>{{ part.text }}</template>
            </template>
          </span>
        </div>

        <p v-if="result.snippet" class="mt-1 text-xs text-sub line-clamp-2 break-all">
          <template v-for="part in result.snippetParts" :key="part.key">
            <mark v-if="part.match" class="search-hit">{{ part.text }}</mark>
            <template v-else>{{ part.text }}</template>
          </template>
        </p>

        <p class="mt-0.5 text-xs text-muted">
          {{ result.group_name }}<span v-if="result.line"> · line {{ result.line }}</span>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.search-result {
  transition: background-color 0.12s ease;
}

.search-result:hover {
  background-color: var(--bg-secondary);
}

.search-hit {
  background-color: color-mix(in srgb, var(--accent-color) 28%, transparent);
  color: inherit;
  border-radius: 2px;
}

.match-badge {
  flex-shrink: 0;
  padding: 0 0.3rem;
  border-radius: 0.25rem;
  font-size: 0.625rem;
  line-height: 1.4;
}

.match-badge.is-name {
  background-color: color-mix(in srgb, var(--accent-color) 18%, transparent);
  color: var(--accent-color);
}

.match-badge.is-body {
  background-color: var(--bg-tertiary);
  color: var(--text-muted);
}

/* Two-line clamp without pulling in line-clamp plugin */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>

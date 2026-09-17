<script setup lang="ts">
import { computed, ref } from 'vue'
import NotebookGroupNode from './NotebookGroupNode.vue'
import NotebookSearchResults from './NotebookSearchResults.vue'
import type { Notebook, NotebookTreeGroup } from '@/api/notebooks'

interface Props {
  groups: NotebookTreeGroup[]
  selectedId: string | null
  loading: boolean
  query: string
  searchResults: import('@/api/notebooks').NotebookSearchResult[]
  searchTotal: number
  searchTruncated: boolean
  searching: boolean
  isCollapsed: (groupId: string) => boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  select: [id: string]
  createNote: []
  createGroup: []
  toggleCollapse: [groupId: string]
  updateQuery: [query: string]
  noteContextMenu: [payload: { note: Notebook; event: MouseEvent }]
  groupContextMenu: [payload: { group: NotebookTreeGroup; event: MouseEvent }]
  backgroundContextMenu: [event: MouseEvent]
}>()

const searchInput = ref<HTMLInputElement>()

const isSearching = computed(() => props.query.trim().length > 0)
</script>

<template>
  <aside class="h-full flex flex-col bg-main border-r border-main min-h-0">
    <!-- Search -->
    <div class="p-2 border-b border-main shrink-0">
      <div class="relative">
        <input
          ref="searchInput"
          :value="query"
          type="text"
          class="input w-full text-sm pr-7"
          placeholder="Search names and contents…"
          @input="emit('updateQuery', ($event.target as HTMLInputElement).value)"
        />
        <button
          v-if="isSearching"
          class="clear-btn absolute right-1.5 top-1/2 -translate-y-1/2 text-muted hover:text-main"
          title="Clear search"
          @click="emit('updateQuery', '')"
        >✕</button>
      </div>
    </div>

    <!-- Search results replace the tree while a query is active -->
    <NotebookSearchResults
      v-if="isSearching"
      :query="query"
      :results="searchResults"
      :loading="searching"
      :total="searchTotal"
      :truncated="searchTruncated"
      @select="emit('select', $event)"
    />

    <!-- Group tree -->
    <template v-else>
      <div
        class="flex-1 min-h-0 overflow-y-auto p-1"
        @contextmenu.prevent="emit('backgroundContextMenu', $event)"
      >
        <p v-if="loading && groups.length === 0" class="px-3 py-4 text-sm text-muted">
          Loading…
        </p>

        <NotebookGroupNode
          v-for="group in groups"
          :key="group.id"
          :group="group"
          :selected-id="selectedId"
          :collapsed="isCollapsed(group.id)"
          @select="emit('select', $event)"
          @toggle-collapse="emit('toggleCollapse', $event)"
          @note-context-menu="emit('noteContextMenu', $event)"
          @group-context-menu="emit('groupContextMenu', $event)"
        />
      </div>

      <div class="p-2 border-t border-main flex gap-2 shrink-0">
        <button class="btn btn-primary flex-1 text-sm" @click="emit('createNote')">
          + New note
        </button>
        <button class="btn btn-secondary text-sm" title="New group" @click="emit('createGroup')">
          + Group
        </button>
      </div>
    </template>
  </aside>
</template>

<style scoped>
.clear-btn {
  line-height: 1;
  font-size: 0.75rem;
  padding: 0.125rem;
}
</style>

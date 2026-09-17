<script setup lang="ts">
import type { Notebook, NotebookTreeGroup } from '@/api/notebooks'

interface Props {
  group: NotebookTreeGroup
  selectedId: string | null
  collapsed: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  select: [id: string]
  toggleCollapse: [groupId: string]
  noteContextMenu: [payload: { note: Notebook; event: MouseEvent }]
  groupContextMenu: [payload: { group: NotebookTreeGroup; event: MouseEvent }]
}>()

const onNoteContextMenu = (note: Notebook, event: MouseEvent) => {
  emit('noteContextMenu', { note, event })
}

const onGroupContextMenu = (event: MouseEvent) => {
  emit('groupContextMenu', { group: props.group, event })
}
</script>

<template>
  <div class="notebook-group">
    <div
      class="group-header flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-sub cursor-pointer select-none"
      :title="group.name"
      @click="emit('toggleCollapse', group.id)"
      @contextmenu.prevent.stop="onGroupContextMenu"
    >
      <svg
        class="h-3.5 w-3.5 text-muted shrink-0 transition-transform"
        :class="{ 'rotate-90': !collapsed }"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
      </svg>
      <span
        class="flex-1 truncate text-sm font-medium text-main"
        :class="{ 'text-muted font-normal': group.is_default }"
      >{{ group.name }}</span>
      <span class="text-xs text-muted shrink-0">{{ group.notes.length }}</span>
    </div>

    <div v-show="!collapsed" class="group-notes">
      <p v-if="group.notes.length === 0" class="px-2 pl-6 py-1 text-xs text-muted">
        Empty
      </p>
      <div
        v-for="note in group.notes"
        :key="note.id"
        class="note-item flex items-center gap-2 pl-6 pr-2 py-1.5 rounded-md cursor-pointer"
        :class="{ 'item-selected': note.id === selectedId }"
        :title="note.filename"
        @click="emit('select', note.id)"
        @contextmenu.prevent.stop="onNoteContextMenu(note, $event)"
      >
        <svg
          v-if="note.pinned"
          class="pinned-icon h-3 w-3 text-accent shrink-0"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M16 3l5 5-3 1-4 4v5l-2 2-3-5-5-3 2-2h5l4-4 1-3z" />
        </svg>
        <span class="flex-1 truncate text-sm text-main">{{ note.title }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.note-item {
  transition: background-color 0.12s ease;
}

.note-item:hover:not(.item-selected) {
  background-color: var(--bg-secondary);
}
</style>

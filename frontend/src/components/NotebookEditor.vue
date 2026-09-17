<script setup lang="ts">
import { computed, ref } from 'vue'
import { Splitpanes, Pane } from 'splitpanes'
import MonacoEditor from './Monaco/MonacoEditor.vue'
import MarkdownPane from './MarkdownPane.vue'
import type { EditorMode } from '@/store/notebook'
import type { NotebookDetail } from '@/api/notebooks'

interface Props {
  note: NotebookDetail | null
  groupName: string
  modelValue: string
  mode: EditorMode
  saving: boolean
  isDirty: boolean
  sidebarVisible: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'update:mode': [mode: EditorMode]
  toggleSidebar: []
  contentChange: []
  save: []
  rename: []
  moveToGroup: []
  remove: []
}>()

const editorRef = ref<any>(null)

const MODES: { value: EditorMode; label: string; title: string }[] = [
  { value: 'edit', label: 'Edit', title: 'Editor only' },
  { value: 'split', label: 'Split', title: 'Editor with live preview' },
  { value: 'preview', label: 'Preview', title: 'Preview only' }
]

const isMobile = ref(window.innerWidth < 768)

// Split mode is not useful on a phone — keep it out of the switcher there.
const availableModes = computed(() =>
  isMobile.value ? MODES.filter((m) => m.value !== 'split') : MODES
)

const wordCount = computed(() => props.modelValue.length)
const lineCount = computed(() => (props.modelValue ? props.modelValue.split('\n').length : 0))

const onContentInput = (value: string) => {
  emit('update:modelValue', value)
  emit('contentChange')
}

const setMode = (mode: EditorMode) => {
  emit('update:mode', mode)
}

/** Monaco does not notice the pane resizing on its own. */
const relayout = () => {
  editorRef.value?.getEditor?.()?.layout?.()
}

defineExpose({
  getEditor: () => editorRef.value,
  relayout
})
</script>

<template>
  <section class="h-full min-h-0 flex flex-col bg-main">
    <!-- Toolbar -->
    <div class="h-10 shrink-0 flex items-center gap-2 px-3 border-b border-main">
      <!-- Always rendered, so the list can be reopened with no note selected. -->
      <button
        class="p-0 rounded hover:bg-sub shrink-0"
        :title="sidebarVisible ? 'Hide note list' : 'Show note list'"
        @click="emit('toggleSidebar')"
      >
        <svg class="h-4 w-4 text-sub" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <rect x="3" y="4" width="18" height="16" rx="2" stroke-width="2" />
          <path stroke-linecap="round" stroke-width="2" d="M9 4v16" />
          <path
            v-if="sidebarVisible"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M17 9l-3 3 3 3"
          />
          <path
            v-else
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M14 9l3 3-3 3"
          />
        </svg>
      </button>

      <span class="truncate text-sm font-medium text-main" :title="note?.filename">
        {{ note ? note.title : 'Notebook' }}
      </span>
      <span v-if="note" class="text-xs text-muted shrink-0 truncate max-w-[10rem]">
        / {{ groupName }}
      </span>

      <div class="flex items-center gap-2 ml-auto shrink-0">
        <span class="text-xs text-muted hidden sm:inline">
          {{ lineCount }} lines · {{ wordCount }} chars
        </span>

        <!-- Mode switcher -->
        <div v-if="note" class="mode-switch flex items-center rounded-md p-0.5 bg-sub">
          <button
            v-for="m in availableModes"
            :key="m.value"
            class="mode-btn px-2 py-0.5 text-xs rounded"
            :class="{ 'tab-active': mode === m.value }"
            :title="m.title"
            @click="setMode(m.value)"
          >{{ m.label }}</button>
        </div>

        <span
          v-if="note"
          class="save-status text-xs shrink-0"
          :class="{ 'is-dirty': isDirty }"
        >
          <template v-if="saving">Saving…</template>
          <template v-else-if="isDirty">● Unsaved</template>
          <template v-else>✓ Saved</template>
        </span>

        <button v-if="note" class="p-0 rounded hover:bg-sub" title="Rename" @click="emit('rename')">
          <svg class="h-4 w-4 text-sub" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
        </button>
        <button v-if="note" class="p-0 rounded hover:bg-sub" title="Move to group" @click="emit('moveToGroup')">
          <svg class="h-4 w-4 text-sub" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
          </svg>
        </button>
        <button v-if="note" class="p-0 rounded hover:bg-sub" title="Delete note" @click="emit('remove')">
          <svg class="h-4 w-4 text-sub" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3M4 7h16" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="!note" class="flex-1 flex items-center justify-center">
      <p class="text-sm text-sub">Select a note on the left, or create one</p>
    </div>

    <!-- Edit only -->
    <MonacoEditor
      v-else-if="mode === 'edit'"
      :key="`${note.id}-edit`"
      :model-value="modelValue"
      :file-path="note.filename"
      :enable-save-shortcut="true"
      @update:model-value="onContentInput"
      @save="emit('save')"
    />

    <!-- Split: editor left, live preview right -->
    <splitpanes
      v-else-if="mode === 'split'"
      class="default-theme flex-1 min-h-0"
      @resize="relayout"
    >
      <pane :size="50" :min-size="20" class="flex flex-col min-h-0">
        <MonacoEditor
          ref="editorRef"
          :key="`${note.id}-split`"
          :model-value="modelValue"
          :file-path="note.filename"
          :enable-save-shortcut="true"
          @update:model-value="onContentInput"
          @save="emit('save')"
        />
      </pane>
      <pane :size="50" :min-size="20" class="flex flex-col min-h-0">
        <MarkdownPane :content="modelValue" :show-outline="false" />
      </pane>
    </splitpanes>

    <!-- Preview only -->
    <MarkdownPane v-else :content="modelValue" />
  </section>
</template>

<style scoped>
.mode-switch {
  border: 1px solid var(--border-color);
}

.mode-btn {
  color: var(--text-secondary);
  transition: all 0.12s ease;
}

.mode-btn:hover:not(.tab-active) {
  color: var(--text-primary);
}

.mode-btn.tab-active {
  background-color: var(--bg-primary);
}

.save-status {
  color: var(--text-muted);
}

.save-status.is-dirty {
  color: var(--accent-color);
}
</style>

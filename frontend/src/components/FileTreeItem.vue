<script setup lang="ts">
import { computed, inject } from 'vue'
import { injectFileTree } from '@/composables/useFileTree'

interface Props {
  path: string
  level: number
  status?: string  // Optional Git status code
}

const props = defineProps<Props>()
const emit = defineEmits<{
  toggle: [path: string]
  selectFile: [path: string]
  showContextMenu: [event: { x: number; y: number; path: string; type: string }]
  previewFile: [path: string]
}>()

const { nodes, expandedDirs } = injectFileTree()

const node = computed(() => nodes.value.get(props.path))
const isExpanded = computed(() => node.value?.type === 'directory' && expandedDirs.value.has(props.path))
const childPaths = computed(() => {
  const n = node.value
  return n?.type === 'directory' ? (n.children || []) : []
})

const handleClick = () => {
  if (!node.value) return

  // Emit click event
  if (node.value.type === 'directory') {
    emit('toggle', props.path)
  } else {
    emit('selectFile', props.path)
  }
}

const handleContextMenu = (e: MouseEvent) => {
  e.preventDefault()
  e.stopPropagation()
  if (!node.value) return
  emit('showContextMenu', {
    x: e.clientX,
    y: e.clientY,
    path: props.path,
    type: node.value.type
  })
}

const handleMiddleClick = (e: MouseEvent) => {
  if (e.button === 1 && node.value?.type === 'file') {
    e.preventDefault()
    emit('previewFile', props.path)
  }
}

let touchTimer: ReturnType<typeof setTimeout> | null = null

const onTouchStart = (e: TouchEvent) => {
  if (!node.value) return
  touchTimer = setTimeout(() => {
    emit('showContextMenu', {
      x: e.touches[0].clientX,
      y: e.touches[0].clientY,
      path: props.path,
      type: node.value!.type
    })
  }, 500)
}

const onTouchEnd = () => {
  if (touchTimer) {
    clearTimeout(touchTimer)
    touchTimer = null
  }
}

const onTouchMove = () => {
  if (touchTimer) {
    clearTimeout(touchTimer)
    touchTimer = null
  }
}

const isChanged = inject<(path: string) => boolean>('isChanged', () => false)
const isSelected = inject<(path: string) => boolean>('isSelected', () => false)
const isLoading = inject<(path: string) => boolean>('isLoading', () => false)
const getFileStatus = inject<(path: string) => string | undefined>('getFileStatus', () => undefined)

const status = computed(() => props.status ?? getFileStatus(props.path))

const indentStyle = computed(() => ({
  paddingLeft: `${props.level * 16}px`
}))
</script>

<template>
  <div v-if="node">
    <!-- Directory Node -->
    <div
      v-if="node.type === 'directory'"
      @click.stop="handleClick"
      @contextmenu.prevent.stop="handleContextMenu"
      @touchstart="onTouchStart"
      @touchend="onTouchEnd"
      @touchmove="onTouchMove"
      class="file-tree-item"
      :class="{
        'loading': isLoading(path),
        'error': node.error
      }"
      :style="indentStyle"
    >
      <span class="file-tree-icon">
        <template v-if="isLoading(path)">
          ⏳
        </template>
        <template v-else-if="node.error">
          ⚠️
        </template>
        <template v-else>
          {{ isExpanded ? '📂' : '📁' }}
        </template>
      </span>
      <span>{{ node.name }}</span>
      <span v-if="status" class="ml-auto px-1.5 py-0.5 rounded text-xs font-mono font-medium min-w-[20px] text-center flex-shrink-0"
        :class="{
          'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400': status === 'A',
          'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400': status === 'M',
          'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400': status === 'D',
          'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400': status === 'R',
          'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400': status === 'C',
          'bg-gray-100 text-gray-700 dark:bg-gray-700/30 dark:text-gray-300': status === 'T',
          'bg-gray-50 text-gray-500 dark:bg-gray-800/30 dark:text-gray-500': status === '?'
        }">{{ status }}</span>
    </div>

    <!-- File Node -->
    <div
      v-else
      @mousedown="handleMiddleClick"
      @click.stop="handleClick"
      @contextmenu.prevent.stop="handleContextMenu"
      @touchstart="onTouchStart"
      @touchend="onTouchEnd"
      @touchmove="onTouchMove"
      class="file-tree-item"
      :class="{
        'selected': isSelected(path),
        'changed': isChanged(path)
      }"
      :style="indentStyle"
    >
      <span class="file-tree-icon">📄</span>
      <span>{{ node.name }}</span>
      <span v-if="status" class="ml-auto px-1.5 py-0.5 rounded text-xs font-mono font-medium min-w-[20px] text-center flex-shrink-0"
        :class="{
          'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400': status === 'A',
          'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400': status === 'M',
          'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400': status === 'D',
          'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400': status === 'R',
          'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400': status === 'C',
          'bg-gray-100 text-gray-700 dark:bg-gray-700/30 dark:text-gray-300': status === 'T',
          'bg-gray-50 text-gray-500 dark:bg-gray-800/30 dark:text-gray-500': status === '?'
        }">{{ status }}</span>
    </div>

    <!-- Child Nodes (Recursive Rendering) -->
    <template v-if="node.type === 'directory' && isExpanded">
      <FileTreeItem
        v-for="childPath in childPaths"
        :key="childPath"
        :path="childPath"
        :level="level + 1"
        @toggle="$emit('toggle', $event)"
        @select-file="$emit('selectFile', $event)"
        @show-context-menu="$emit('showContextMenu', $event)"
        @preview-file="$emit('previewFile', $event)"
      />
    </template>
  </div>
</template>

<style scoped>
.file-tree-item {
  padding: 4px 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  user-select: none;
  border-radius: 4px;
  transition: background-color 0.15s ease, box-shadow 0.15s ease;
}

@media (hover: hover) {
  .file-tree-item:hover {
    background-color: var(--bg-tertiary);
  }

  .file-tree-item.selected:hover {
    background-color: color-mix(in srgb, var(--accent-color) 18%, var(--bg-tertiary));
  }
}

/* Theme-aware changed file indicator */
.file-tree-item.changed {
  color: var(--accent-color);
  font-weight: 500;
}

.file-tree-item.loading {
  opacity: 0.6;
}

.file-tree-item.error {
  color: rgb(239 68 68);
}

.file-tree-icon {
  min-width: 20px;
}

.status-badge {
  @apply px-1.5 py-0.5 rounded text-xs font-mono font-medium min-w-[20px] text-center;
  flex-shrink: 0;
}

.status-a {
  @apply bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400;
}

.status-m {
  @apply bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400;
}

.status-d {
  @apply bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400;
}

.status-r {
  @apply bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400;
}

.status-c {
  @apply bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400;
}

.status-t {
  @apply bg-gray-100 text-gray-700 dark:bg-gray-700/30 dark:text-gray-300;
}

.status-\? {
  @apply bg-gray-50 text-gray-500 dark:bg-gray-800/30 dark:text-gray-500;
}
</style>

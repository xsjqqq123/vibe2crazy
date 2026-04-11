<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useMatrixStore, type MatrixTask } from '@/store/matrixStore'
import matrixApi from '@/api/matrix'
import MatrixTerminal from '@/components/MatrixTerminal.vue'

const matrixStore = useMatrixStore()

const gridRef = ref<HTMLElement | null>(null)

// Column options
const columnOptions = [2, 3, 4, 5, 6, 7, 8, 9, 10]

// Height ratio options
const heightRatioOptions = [
  { value: 0.6, label: '0.6x' },
  { value: 0.8, label: '0.8x' },
  { value: 1.0, label: '1.0x' },
  { value: 1.2, label: '1.2x' },
  { value: 1.4, label: '1.4x' },
  { value: 1.6, label: '1.6x' },
  { value: 1.8, label: '1.8x' },
  { value: 2.0, label: '2.0x' },
  { value: 2.5, label: '2.5x' }
]

// Mode options
const modeOptions = [
  { value: 'tasks', label: 'All Tasks' },
  { value: 'sessions', label: 'New Sessions' }
]

// Row options based on maxRows
const rowOptions = computed(() => {
  return Array.from({ length: matrixStore.maxRows }, (_, i) => i + 1)
})

// Terminal title computation
const getTerminalTitle = (item: any, index: number): string => {
  if (matrixStore.mode === 'tasks') {
    const task = item as MatrixTask
    return `${task.project_name}/${task.name}`
  } else {
    return `Terminal ${index + 1}`
  }
}

// Get task ID for terminal (tasks mode only)
const getTaskId = (item: any): string | undefined => {
  if (matrixStore.mode === 'tasks') {
    const task = item as MatrixTask
    return task.id
  }
  return undefined
}

// Get session name for terminal
const getSessionName = (item: any, index: number): string => {
  if (matrixStore.mode === 'tasks') {
    const task = item as MatrixTask
    return task.tmux_session || `v2d-${task.id}`
  } else {
    return `v2d-matrix-${index + 1}`
  }
}

// Grid style
const gridStyle = computed(() => {
  return {
    gridTemplateColumns: `repeat(${matrixStore.columns}, 1fr)`
  }
})

// Load data based on mode
const loadData = async () => {
  if (matrixStore.mode === 'tasks') {
    matrixStore.tasksLoading = true
    try {
      const tasks = await matrixApi.getAllTasks()
      matrixStore.setTasks(tasks)
    } catch (err) {
      console.error('Failed to load tasks:', err)
    }
    matrixStore.tasksLoading = false
  } else {
    matrixStore.sessionsLoading = true
    try {
      const sessions = await matrixApi.createSessions(matrixStore.gridCapacity)
      matrixStore.setSessions(sessions)
    } catch (err) {
      console.error('Failed to create sessions:', err)
    }
    matrixStore.sessionsLoading = false
  }
}

// Handle terminal selection (-1 means deselect)
const handleSelect = (index: number) => {
  if (index === -1) {
    // Deselect: set selectedIndex to -1 (no terminal selected)
    matrixStore.setSelectedIndex(-1)
  } else {
    matrixStore.setSelectedIndex(index)
  }
}

// Initialize
onMounted(async () => {
  matrixStore.loadFromStorage()
  await loadData()
})

// Watch mode changes
watch(() => matrixStore.mode, async () => {
  await loadData()
})

// Watch grid size changes for sessions mode
watch([() => matrixStore.columns, () => matrixStore.rows], async () => {
  if (matrixStore.mode === 'sessions') {
    await loadData()
  }
})
</script>

<template>
  <div class="min-h-screen bg-main">
    <!-- Header -->
    <header class="fixed top-0 left-0 right-0 z-30 bg-main border-b border-main">
      <div class="px-4 py-2 flex items-center gap-4 flex-wrap">
        <!-- Columns -->
        <div class="flex items-center gap-2">
          <label class="text-sm text-sub">Columns:</label>
          <select
            v-model.number="matrixStore.columns"
            @change="matrixStore.setColumns(matrixStore.columns)"
            class="input text-sm py-1 px-2 w-16"
          >
            <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
          </select>
        </div>

        <!-- Rows -->
        <div class="flex items-center gap-2">
          <label class="text-sm text-sub">Rows:</label>
          <select
            v-model.number="matrixStore.rows"
            @change="matrixStore.setRows(matrixStore.rows)"
            class="input text-sm py-1 px-2 w-16"
          >
            <option v-for="row in rowOptions" :key="row" :value="row">{{ row }}</option>
          </select>
        </div>

        <!-- Height Ratio -->
        <div class="flex items-center gap-2">
          <label class="text-sm text-sub">Height:</label>
          <select
            v-model.number="matrixStore.heightRatio"
            @change="matrixStore.setHeightRatio(matrixStore.heightRatio)"
            class="input text-sm py-1 px-2 w-20"
          >
            <option
              v-for="opt in heightRatioOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </div>

        <!-- Mode -->
        <div class="flex items-center gap-2">
          <label class="text-sm text-sub">Mode:</label>
          <select
            v-model="matrixStore.mode"
            @change="matrixStore.setMode(matrixStore.mode)"
            class="input text-sm py-1 px-2 w-28"
          >
            <option
              v-for="opt in modeOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </div>

        <!-- Pagination (only for tasks mode) -->
        <div v-if="matrixStore.mode === 'tasks'" class="flex items-center gap-2 ml-auto">
          <button
            @click="matrixStore.prevPage()"
            :disabled="matrixStore.currentPage === 1"
            class="btn btn-secondary text-sm py-1 px-2 disabled:opacity-50"
          >
            Prev
          </button>
          <span class="text-sm text-sub">
            第 {{ matrixStore.currentPage }}/{{ matrixStore.totalPages }} 页
          </span>
          <button
            @click="matrixStore.nextPage()"
            :disabled="matrixStore.currentPage === matrixStore.totalPages"
            class="btn btn-secondary text-sm py-1 px-2 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </header>

    <!-- Main grid -->
    <main class="pt-12 px-4 pb-4">
      <div
        v-if="matrixStore.tasksLoading || matrixStore.sessionsLoading"
        class="flex items-center justify-center py-20"
      >
        <div class="spinner"></div>
      </div>

      <div
        v-else
        ref="gridRef"
        class="grid gap-2"
        :style="gridStyle"
      >
        <MatrixTerminal
          v-for="(item, idx) in matrixStore.currentItems"
          :key="`${matrixStore.mode}-${matrixStore.currentPage}-${idx}`"
          :index="idx"
          :title="getTerminalTitle(item, idx)"
          :is-selected="matrixStore.selectedIndex === idx"
          :session-name="getSessionName(item, idx)"
          :task-id="getTaskId(item)"
          :mode="matrixStore.mode"
          @select="handleSelect"
          :style="{ height: `calc((100vw - 2rem) / ${matrixStore.columns} * ${matrixStore.heightRatio})` }"
          class="matrix-terminal-item"
        />
      </div>

      <!-- Empty state for tasks mode -->
      <div
        v-if="matrixStore.mode === 'tasks' && !matrixStore.tasksLoading && matrixStore.tasks.length === 0"
        class="text-center py-20"
      >
        <p class="text-sub">No tasks found</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.matrix-terminal-item {
  min-height: 100px;
}
</style>
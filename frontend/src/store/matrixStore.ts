import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const STORAGE_KEY = 'vibe2crazy-matrix-settings'

export interface MatrixTask {
  id: string
  name: string
  project_id: string
  project_name: string
  status: 'running' | 'idle'
  tmux_session: string
}

export type MatrixMode = 'tasks' | 'sessions'

export const useMatrixStore = defineStore('matrix', () => {
  // Grid settings
  const columns = ref(4)
  const rows = ref(4)
  const heightRatio = ref(1.0)
  const mode = ref<MatrixMode>('tasks')

  // Selection and pagination
  const selectedIndex = ref(0)
  const currentPage = ref(1)

  // Tasks data for 'tasks' mode
  const tasks = ref<MatrixTask[]>([])
  const tasksLoading = ref(false)

  // Sessions data for 'sessions' mode
  const sessions = ref<Array<{ index: number; session_name: string; exists: boolean }>>([])
  const sessionsLoading = ref(false)

  // Max rows based on columns (total cells <= 64)
  const maxRows = computed(() => Math.floor(64 / columns.value))

  // Grid capacity
  const gridCapacity = computed(() => columns.value * rows.value)

  // Total pages for tasks mode
  const totalPages = computed(() => {
    if (mode.value === 'sessions') return 1
    return Math.ceil(tasks.value.length / gridCapacity.value) || 1
  })

  // Current page tasks/sessions
  const currentItems = computed(() => {
    if (mode.value === 'sessions') {
      // Generate placeholder items for all grid positions
      return Array.from({ length: gridCapacity.value }, (_, i) => ({
        index: i + 1,
        session_name: `v2d-matrix-${i + 1}`,
        exists: sessions.value.find(s => s.index === i + 1)?.exists ?? false
      }))
    } else {
      const start = (currentPage.value - 1) * gridCapacity.value
      const end = start + gridCapacity.value
      return tasks.value.slice(start, end)
    }
  })

  // Load settings from localStorage
  const loadFromStorage = () => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (parsed.columns) columns.value = parsed.columns
        if (parsed.rows) rows.value = parsed.rows
        if (parsed.heightRatio) heightRatio.value = parsed.heightRatio
        if (parsed.mode) mode.value = parsed.mode
        if (parsed.currentPage) currentPage.value = parsed.currentPage
      }
    } catch {
      // Ignore parse errors
    }

    // Ensure rows doesn't exceed maxRows
    if (rows.value > maxRows.value) {
      rows.value = maxRows.value
    }
  }

  // Save settings to localStorage
  const saveToStorage = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        columns: columns.value,
        rows: rows.value,
        heightRatio: heightRatio.value,
        mode: mode.value,
        currentPage: currentPage.value
      }))
    } catch {
      // Ignore storage errors
    }
  }

  // Set columns and adjust rows if needed
  const setColumns = (val: number) => {
    columns.value = val
    if (rows.value > maxRows.value) {
      rows.value = maxRows.value
    }
    currentPage.value = 1
    saveToStorage()
  }

  // Set rows
  const setRows = (val: number) => {
    rows.value = Math.min(val, maxRows.value)
    currentPage.value = 1
    saveToStorage()
  }

  // Set height ratio
  const setHeightRatio = (val: number) => {
    heightRatio.value = val
    saveToStorage()
  }

  // Set mode
  const setMode = (val: MatrixMode) => {
    mode.value = val
    currentPage.value = 1
    selectedIndex.value = 0
    saveToStorage()
  }

  // Set selected index
  const setSelectedIndex = (val: number) => {
    selectedIndex.value = val
  }

  // Set current page
  const setCurrentPage = (val: number) => {
    currentPage.value = Math.max(1, Math.min(val, totalPages.value))
    selectedIndex.value = 0
    saveToStorage()
  }

  // Go to next page
  const nextPage = () => {
    if (currentPage.value < totalPages.value) {
      setCurrentPage(currentPage.value + 1)
    }
  }

  // Go to previous page
  const prevPage = () => {
    if (currentPage.value > 1) {
      setCurrentPage(currentPage.value - 1)
    }
  }

  // Set tasks
  const setTasks = (val: MatrixTask[]) => {
    tasks.value = val
  }

  // Set sessions
  const setSessions = (val: Array<{ index: number; session_name: string; exists: boolean }>) => {
    sessions.value = val
  }

  return {
    columns,
    rows,
    heightRatio,
    mode,
    selectedIndex,
    currentPage,
    tasks,
    tasksLoading,
    sessions,
    sessionsLoading,
    maxRows,
    gridCapacity,
    totalPages,
    currentItems,
    loadFromStorage,
    saveToStorage,
    setColumns,
    setRows,
    setHeightRatio,
    setMode,
    setSelectedIndex,
    setCurrentPage,
    nextPage,
    prevPage,
    setTasks,
    setSessions
  }
})
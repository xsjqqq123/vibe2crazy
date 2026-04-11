<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuth } from '@/composables/useAuth'
import { useTheme } from '@/composables/useTheme'
import { useConfirm } from '@/composables/useConfirm'
import { useMainStore } from '@/store'
import projectsApi from '@/api/projects'
import tasksApi, { type Task, isTaskCompleted } from '@/api/tasks'
import { isLanMode } from '@/api/client'
import TaskCard from '@/components/TaskCard.vue'
import GlobalTerminalIcon from '@/components/GlobalTerminalIcon.vue'

const router = useRouter()
const route = useRoute()
const { logout } = useAuth()
const { theme, cycleTheme } = useTheme()
const { showConfirm } = useConfirm()
const store = useMainStore()

const projectId = computed(() => route.params.id as string)
const tasks = ref<Task[]>([])
const loading = ref(false)
const showCreateDialog = ref(false)
const newTaskName = ref('')
const newTaskDirectOnBranch = ref(false)
const createError = ref('')
const refreshing = ref(false)

const inProgressTasks = computed(() =>
  tasks.value.filter(t => !isTaskCompleted(t))
)

const completedTasks = computed(() =>
  tasks.value.filter(t => isTaskCompleted(t))
)

// Smart update: only replace tasks that have changed to prevent UI jitter
const updateTasksSmartly = (newTasks: Task[]) => {
  const currentTasksMap = new Map(tasks.value.map(t => [t.id, t]))
  const newTasksMap = new Map(newTasks.map(t => [t.id, t]))

  // Update existing tasks in-place if they changed
  tasks.value.forEach((task) => {
    const newTask = newTasksMap.get(task.id)
    if (newTask) {
      // Check if task actually changed by comparing JSON
      const oldJson = JSON.stringify(task)
      const newJson = JSON.stringify(newTask)
      if (oldJson !== newJson) {
        // Update in-place to preserve component state
        Object.assign(task, newTask)
      }
    }
  })

  // Add new tasks
  newTasks.forEach(newTask => {
    if (!currentTasksMap.has(newTask.id)) {
      tasks.value.push(newTask)
    }
  })

  // Remove deleted tasks
  tasks.value = tasks.value.filter(task => newTasksMap.has(task.id))
}

const loadTasks = async (isBackgroundRefresh = false) => {
  if (!isBackgroundRefresh) {
    loading.value = true
  }

  try {
    const project = await projectsApi.get(projectId.value)
    store.setCurrentProject(project)
    const newTasks = await tasksApi.list(projectId.value)

    // For initial load or explicit reload, replace all tasks
    if (!isBackgroundRefresh) {
      tasks.value = newTasks
    } else {
      // For background refresh, use smart update
      updateTasksSmartly(newTasks)
    }
  } catch (err: any) {
    console.error('Failed to load tasks:', err)
    if (!isBackgroundRefresh) {
      router.push('/projects')
    }
  }

  if (!isBackgroundRefresh) {
    loading.value = false
  }
}

let refreshTimer: number | null = null

const startStatusRefresh = () => {
  refreshTimer = window.setInterval(async () => {
    if (!isLanMode()) return  // 非局域网跳过本次刷新
    refreshing.value = true
    try {
      await loadTasks(true)  // true = background refresh
    } finally {
      refreshing.value = false
    }
  }, 5000)  // 5 seconds (reduced from 15 seconds)
}

const stopStatusRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

const createTask = async () => {
  if (!newTaskName.value.trim()) {
    createError.value = 'Please enter a task name'
    return
  }

  loading.value = true
  createError.value = ''

  try {
    await tasksApi.create(projectId.value, {
      name: newTaskName.value,
      direct_on_branch: newTaskDirectOnBranch.value
    })
    showCreateDialog.value = false
    newTaskName.value = ''
    newTaskDirectOnBranch.value = false
    await loadTasks()
  } catch (err: any) {
    createError.value = err.message || 'Failed to create task'
  }

  loading.value = false
}

const deleteTask = async (task: Task) => {
  const confirmed = await showConfirm({
    title: 'Delete Task',
    message: `Are you sure you want to delete task "${task.name}"?`,
    confirmText: 'Delete',
    danger: true
  })

  if (!confirmed) return

  loading.value = true
  try {
    await tasksApi.delete(task.id)
    await loadTasks()
  } catch (err: any) {
    console.error('Failed to delete task:', err)
  }
  loading.value = false
}

onMounted(() => {
  loadTasks()
  startStatusRefresh()
})

onUnmounted(() => {
  stopStatusRefresh()
})
</script>

<template>
  <div class="min-h-screen">
    <!-- Header -->
    <header class="bg-main border-b border-main">
      <div class="max-w-7xl mx-auto px-3 sm:px-4 lg:px-6 py-2 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <button @click="router.push('/projects')" class="text-sub hover:text-main">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 class="text-lg font-semibold text-main">{{ store.currentProject?.name || 'Project' }}</h1>
            <p class="text-xs text-sub">Tasks</p>
          </div>
          <!-- Refresh indicator -->
          <div v-if="refreshing" class="flex items-center gap-1 text-xs text-muted">
            <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Refreshing...</span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button @click="cycleTheme" class="p-1.5 rounded-lg hover:bg-sub" title="Cycle theme">
            <!-- Sun icon for light theme -->
            <svg v-if="theme === 'light'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            <!-- Moon icon for dark theme -->
            <svg v-else-if="theme === 'dark'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
            <!-- Leaf icon for green theme -->
            <svg v-else-if="theme === 'green'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
            </svg>
            <!-- Document icon for parchment theme -->
            <svg v-else-if="theme === 'parchment'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </button>
          <GlobalTerminalIcon />
          <button @click="logout" class="p-1.5 rounded-lg hover:bg-sub" title="Logout">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>
    </header>

    <!-- Main content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-xl font-semibold text-main">Tasks</h2>
        <button @click="showCreateDialog = true" class="btn btn-primary">
          + New Task
        </button>
      </div>

      <!-- Tasks list -->
      <div v-if="loading && tasks.length === 0" class="flex items-center justify-center py-12">
        <div class="spinner"></div>
      </div>

      <div v-else-if="tasks.length === 0" class="text-center py-12">
        <p class="text-sub mb-4">No tasks yet</p>
        <button @click="showCreateDialog = true" class="btn btn-primary">Create your first task</button>
      </div>

      <div v-else>
        <!-- In Progress Section -->
        <section class="mb-8">
          <h2 class="text-xl font-semibold text-main mb-4">
            In Progress ({{ inProgressTasks.length }})
          </h2>
          <div v-if="inProgressTasks.length === 0 && !loading" class="text-center py-8 text-sub">
            No in-progress tasks
          </div>
          <div v-else-if="inProgressTasks.length > 0" class="space-y-3">
            <TaskCard v-for="task in inProgressTasks" :key="task.id" :task="task" @delete="deleteTask" />
          </div>
        </section>

        <!-- Completed Section -->
        <section>
          <h2 class="text-xl font-semibold text-main mb-4">
            Completed ({{ completedTasks.length }})
          </h2>
          <div v-if="completedTasks.length === 0 && !loading" class="text-center py-8 text-sub">
            No completed tasks
          </div>
          <div v-else-if="completedTasks.length > 0" class="space-y-3">
            <TaskCard v-for="task in completedTasks" :key="task.id" :task="task" @delete="deleteTask" />
          </div>
        </section>
      </div>
    </main>

    <!-- Create task dialog -->
    <div v-if="showCreateDialog" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card max-w-md w-full">
        <h3 class="text-lg font-semibold text-main mb-4">Create New Task</h3>

        <form @submit.prevent="createTask" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-sub mb-2">
              Task Name *
            </label>
            <input v-model="newTaskName" type="text" class="input w-full" placeholder="Implement feature X" />
          </div>

          <div class="flex items-start gap-2">
            <input
              type="checkbox"
              id="directOnBranch"
              v-model="newTaskDirectOnBranch"
              class="mt-1"
            />
            <label for="directOnBranch" class="text-sm text-sub">
              <span class="font-medium text-main">Directly on the branch</span>
              <br />
              <span class="text-xs">Work directly on main branch, no worktree created, merge not supported.</span>
            </label>
          </div>

          <div v-if="createError" class="text-red-600 dark:text-red-400 text-sm">
            {{ createError }}
          </div>

          <div class="flex gap-3 justify-end">
            <button type="button" @click="showCreateDialog = false; newTaskDirectOnBranch = false" class="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" :disabled="loading" class="btn btn-primary">
              <span v-if="loading" class="spinner mr-2"></span>
              Create
            </button>
          </div>
        </form>

        <p v-if="!newTaskDirectOnBranch" class="text-xs text-sub mt-4">
          A new Git worktree and tmux session will be created for this task.
        </p>
        <p v-else class="text-xs text-amber-600 dark:text-amber-400 mt-4">
          Warning: Multiple direct-on-branch tasks share the same working directory.
        </p>
      </div>
    </div>
  </div>
</template>

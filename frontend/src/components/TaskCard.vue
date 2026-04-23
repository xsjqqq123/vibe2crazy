<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useMainStore } from '@/store'
import type { Task } from '@/api/tasks'
import { getTaskStatusLabel, getCodeStatusLabel } from '@/api/tasks'

const props = defineProps<{
  task: Task
}>()

const router = useRouter()
const store = useMainStore()

const openTask = () => {
  store.setCurrentTask(props.task)
  router.push(`/tasks/${props.task.id}`)
}

const taskStatus = computed(() => getTaskStatusLabel(props.task.task_status))
const codeStatus = computed(() => getCodeStatusLabel(props.task.code_status))

const emit = defineEmits<{
  delete: [task: Task]
}>()
</script>

<template>
  <div class="card group relative flex items-center justify-between cursor-pointer hover:shadow-md transition-shadow" @click="openTask">
    <!-- Delete button (top-right, always visible) -->
    <button
      @click.stop="emit('delete', task)"
      class="absolute top-2 right-2 p-1 text-red-600 hover:text-red-700"
      title="Delete task"
    >
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
      </svg>
    </button>
    <div class="flex-1 pr-10">
      <div class="flex items-center gap-2">
        <h3 class="text-lg font-semibold text-main">{{ task.name }}</h3>
        <span v-if="task.direct_on_branch" class="px-1.5 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 rounded">
          Direct
        </span>
      </div>
      <p class="text-sm text-sub">{{ task.branch_name }}</p>
    </div>

    <!-- Status badges (bottom-right) -->
    <div class="flex flex-col gap-1 items-end pr-10">
      <!-- Task Status -->
      <div class="flex items-center gap-1 text-sm font-medium" :class="taskStatus.color">
        <span>{{ taskStatus.icon }}</span>
        <span>{{ taskStatus.label }}</span>
      </div>
      <!-- Code Status -->
      <div class="text-sm font-medium" :class="codeStatus.color">
        {{ codeStatus.label }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  padding: 1rem;
  border-radius: 0.5rem;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
}
.theme-dark .card {
  background: linear-gradient(145deg, #161b22 0%, #0d1117 100%);
  border-color: #30363d;
  box-shadow:
    0 2px 8px rgba(0, 0, 0, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.03);
}
</style>

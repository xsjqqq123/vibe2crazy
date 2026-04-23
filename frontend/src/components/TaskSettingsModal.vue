<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import tasksApi from '@/api/tasks'

const props = defineProps<{
  taskId: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const paths = ref('')
const isSaving = ref(false)
const isLoading = ref(true)
const error = ref('')
const success = ref('')

async function loadTaskData() {
  isLoading.value = true
  error.value = ''
  try {
    const task = await tasksApi.get(props.taskId)
    paths.value = task.extra_index_paths || ''
  } catch (e: any) {
    error.value = e.message || 'Failed to load task settings'
  } finally {
    isLoading.value = false
  }
}

async function handleSave() {
  if (isSaving.value) return

  isSaving.value = true
  error.value = ''
  success.value = ''

  try {
    // Get the task to find project_id
    const task = await tasksApi.get(props.taskId)

    // Update the task with new extra_index_paths
    await tasksApi.update(task.project_id, props.taskId, {
      extra_index_paths: paths.value.trim() || undefined
    })
    success.value = 'Settings saved successfully'
    setTimeout(() => {
      success.value = ''
    }, 2000)
  } catch (e: any) {
    error.value = e.message || 'Failed to save settings'
  } finally {
    isSaving.value = false
  }
}

function handleClose() {
  emit('close')
}

onMounted(() => {
  loadTaskData()
})

// Reload when taskId changes
watch(() => props.taskId, () => {
  loadTaskData()
})
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" @click.self="handleClose">
      <div class="bg-main border border-sub rounded-lg shadow-xl w-full max-w-lg mx-4">
        <!-- Header -->
        <div class="flex items-center justify-between px-4 py-3 border-b border-sub">
          <h2 class="text-lg font-semibold text-main">Task Settings</h2>
          <button
            @click="handleClose"
            class="p-1 rounded hover:bg-sub text-sub"
            title="Close"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Content -->
        <div class="p-4 space-y-4">
          <!-- Loading state -->
          <div v-if="isLoading" class="flex items-center justify-center py-8">
            <svg class="animate-spin h-6 w-6 text-sub" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </div>

          <!-- Settings form -->
          <div v-else>
            <!-- Extra Index Paths -->
            <div>
              <label class="block text-sm font-medium text-main mb-2">
                Extra Symbol Index Paths
              </label>
              <textarea
                v-model="paths"
                rows="3"
                class="w-full px-3 py-2 border border-sub rounded-lg bg-main text-main placeholder-sub focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter paths to index, e.g., /usr/include"
                :disabled="isSaving"
              />
              <p class="text-xs text-sub mt-1">
                Multiple paths separated by semicolon (;). These paths will be indexed when you click the Index button in the Symbol Preview panel.
              </p>
            </div>

            <!-- Error Message -->
            <div v-if="error" class="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
            </div>

            <!-- Success Message -->
            <div v-if="success" class="mt-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
              <p class="text-sm text-green-600 dark:text-green-400">{{ success }}</p>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div v-if="!isLoading" class="flex justify-end gap-2 px-4 py-3 border-t border-sub">
          <button
            @click="handleClose"
            class="px-4 py-2 text-sub hover:text-main rounded-lg"
          >
            Close
          </button>
          <button
            @click="handleSave"
            :disabled="isSaving"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <svg v-if="isSaving" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ isSaving ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import queueApi, { type QueueItem } from '@/api/queue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useConfirm } from '@/composables/useConfirm'

interface Props {
  taskId: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
}>()

const { onMessage, offMessage } = useWebSocket(props.taskId)
const { showConfirm } = useConfirm()

const queue = ref<QueueItem[]>([])
const loading = ref(false)
const error = ref('')
const newMessage = ref('')
const autoAppend = ref(true)

const loadQueue = async () => {
  loading.value = true
  error.value = ''
  try {
    queue.value = await queueApi.getQueue(props.taskId)
  } catch (err: any) {
    error.value = err.message || 'Failed to load queue'
    console.error('Failed to load queue:', err)
  }
  loading.value = false
}

const addToQueue = async () => {
  if (!newMessage.value.trim()) return

  let messageToSend = newMessage.value
  if (autoAppend.value && !messageToSend.endsWith('.Don\'t ask me')) {
    messageToSend = messageToSend.trim() + '.Don\'t ask me'
  }

  loading.value = true
  error.value = ''
  try {
    await queueApi.addToQueue(props.taskId, messageToSend)
    newMessage.value = ''
    await loadQueue()
  } catch (err: any) {
    error.value = err.message || 'Failed to add message'
    console.error('Failed to add message:', err)
  }
  loading.value = false
}

const removeFromQueue = async (messageId: string) => {
  loading.value = true
  error.value = ''
  try {
    await queueApi.removeFromQueue(props.taskId, messageId)
    await loadQueue()
  } catch (err: any) {
    error.value = err.message || 'Failed to remove message'
    console.error('Failed to remove message:', err)
  }
  loading.value = false
}

const clearQueue = async () => {
  const confirmed = await showConfirm({
    title: 'Clear Queue',
    message: 'Clear all messages from queue?',
    confirmText: 'Clear',
    danger: true
  })

  if (!confirmed) return

  loading.value = true
  error.value = ''
  try {
    await queueApi.clearQueue(props.taskId)
    await loadQueue()
  } catch (err: any) {
    error.value = err.message || 'Failed to clear queue'
    console.error('Failed to clear queue:', err)
  }
  loading.value = false
}

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'pending': return '⏳'
    case 'executing': return '▶'
    case 'completed': return '✓'
    default: return '?'
  }
}

const getPreview = (content: string) => {
  return content.length > 50 ? content.substring(0, 50) + '...' : content
}

const formatTime = (dateStr: string) => {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  return date.toLocaleDateString()
}

// Listen for queue updates via WebSocket
const handleQueueUpdate = (msg: any) => {
  if (msg.task_id === props.taskId) {
    console.log('[QueueModal] Queue update received, reloading...')
    loadQueue()
  }
}

onMounted(() => {
  loadQueue()
  // Register WebSocket listener for queue updates
  onMessage('queue_updated', handleQueueUpdate)
})

onUnmounted(() => {
  // Cleanup WebSocket listener
  offMessage('queue_updated')
})
</script>

<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
    <div class="card max-w-2xl w-full max-h-[80vh] flex flex-col">
      <!-- Header -->
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-main">
          Message Queue
        </h2>
        <button
          @click="emit('close')"
          class="text-sub hover:text-main"
        >
          ✕
        </button>
      </div>

      <!-- Error message -->
      <div v-if="error" class="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
        <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
      </div>

      <!-- Queue list -->
      <div class="flex-1 overflow-y-auto mb-4 border border-main rounded-lg p-2 min-h-[200px] max-h-[300px]">
        <div v-if="loading && queue.length === 0" class="flex items-center justify-center py-8">
          <div class="spinner"></div>
        </div>
        <div v-else-if="queue.length === 0" class="text-center py-8 text-sub">
          Queue is empty. Add messages to execute when terminal is idle.
        </div>
        <div v-else class="space-y-2">
          <div
            v-for="item in queue"
            :key="item.id"
            :class="[
              'p-3 rounded-lg border',
              {
                'border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-900/30': item.status === 'executing',
                'border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-900/30': item.status === 'completed',
                'border-main bg-main': item.status === 'pending'
              }
            ]"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-lg">{{ getStatusIcon(item.status) }}</span>
                  <span class="text-xs font-mono text-sub uppercase">
                    {{ item.status }}
                  </span>
                </div>
                <div class="text-sm text-main break-words font-mono">
                  {{ getPreview(item.content) }}
                </div>
                <div class="text-xs text-sub mt-1">
                  Added {{ formatTime(item.created_at) }}
                  <span v-if="item.executed_at" class="ml-2">
                    · Executed {{ formatTime(item.executed_at) }}
                  </span>
                </div>
              </div>
              <button
                v-if="item.status === 'pending'"
                @click="removeFromQueue(item.id)"
                :disabled="loading"
                class="text-red-500 hover:text-red-700 disabled:opacity-50"
                title="Remove from queue"
              >
                ✕
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Add message section -->
      <div class="border-t border-main pt-4">
        <label class="block text-sm font-medium text-sub mb-2">
          Add message (multi-line supported):
        </label>
        <textarea
          v-model="newMessage"
          class="input w-full mb-2 min-h-[80px] font-mono text-sm"
          placeholder="Enter command or message..."
          @keydown.ctrl.enter="addToQueue"
        ></textarea>
        <div class="flex items-center gap-2 justify-between">
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" v-model="autoAppend" class="form-checkbox" />
            <span class="text-sm text-sub">Auto</span>
          </label>
          <div class="flex gap-2">
            <button
              @click="addToQueue"
              :disabled="loading || !newMessage.trim()"
              class="btn btn-primary text-xs"
            >
              <span v-if="loading" class="spinner-small mr-1"></span>
              Add
            </button>
            <button
              v-if="queue.length > 0"
              @click="clearQueue"
              :disabled="loading"
              class="btn btn-secondary text-xs"
            >
              Clear Queue
            </button>
          </div>
        </div>
        <p class="text-xs text-sub mt-2">
          Tip: Press Ctrl+Enter to add message quickly
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import commandPresetsApi from '@/api/commandPresets'

interface CommandPreset {
  id: number
  command: string
  created_at: string
}

interface Props {
  connected: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
  execute: [command: string]
}>()

const presets = ref<CommandPreset[]>([])
const loading = ref(false)
const error = ref('')
const newCommand = ref('')

const loadPresets = async () => {
  loading.value = true
  error.value = ''
  try {
    presets.value = await commandPresetsApi.list()
  } catch (err: any) {
    error.value = err.message || 'Failed to load presets'
    console.error('Failed to load presets:', err)
  }
  loading.value = false
}

const handleCreate = async () => {
  const trimmed = newCommand.value.trim()
  if (!trimmed) return

  try {
    const newPreset = await commandPresetsApi.create({ command: trimmed })
    presets.value.unshift(newPreset)
    newCommand.value = ''
  } catch (err: any) {
    error.value = err.message || 'Failed to create preset'
    console.error('Failed to create preset:', err)
  }
}

const handleDelete = async (id: number) => {
  try {
    await commandPresetsApi.delete(id)
    presets.value = presets.value.filter(p => p.id !== id)
  } catch (err: any) {
    error.value = err.message || 'Failed to delete preset'
    console.error('Failed to delete preset:', err)
  }
}

const handleExecute = (command: string) => {
  if (!props.connected) {
    error.value = 'Terminal not connected'
    return
  }
  emit('execute', command)
  emit('close')
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape') {
    emit('close')
  } else if (e.key === 'Enter' && newCommand.value.trim()) {
    handleCreate()
  }
}

onMounted(() => {
  loadPresets()
})
</script>

<template>
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
    @click.self="emit('close')"
    @keydown="handleKeydown"
  >
    <div class="card max-w-md w-full max-h-[80vh] flex flex-col">
      <!-- Header -->
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-main">Command Presets</h3>
        <button
          @click="emit('close')"
          class="text-sub hover:text-main text-xl"
        >
          ✕
        </button>
      </div>

      <!-- Error message -->
      <div v-if="error" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
        <p class="text-sm text-red-600">{{ error }}</p>
      </div>

      <!-- Loading state -->
      <div v-if="loading" class="flex-1 flex items-center justify-center py-8">
        <div class="spinner"></div>
      </div>

      <!-- Presets list -->
      <div v-else class="flex-1 overflow-y-auto mb-4">
        <div v-if="presets.length === 0" class="text-center py-8 text-sub">
          No commands yet. Add one below!
        </div>
        <div v-else class="space-y-2">
          <div
            v-for="preset in presets"
            :key="preset.id"
            class="group flex items-center justify-between p-3 bg-sub rounded-lg hover:bg-accent/10 cursor-pointer transition-colors"
            @click="handleExecute(preset.command)"
          >
            <span
              class="flex-1 font-mono text-sm truncate mr-2"
              :title="preset.command"
            >
              {{ preset.command }}
            </span>
            <button
              @click.stop="handleDelete(preset.id)"
              class="text-muted hover:text-red-600"
              title="Delete command"
            >
              ×
            </button>
          </div>
        </div>
      </div>

      <!-- Add new command -->
      <div class="flex gap-2">
        <input
          v-model="newCommand"
          type="text"
          class="input flex-1 min-w-0"
          placeholder="Type command..."
          @keydown.enter.prevent="handleCreate"
        />
        <button
          @click="handleCreate"
          :disabled="!newCommand.trim()"
          class="btn btn-primary text-sm px-3 py-1.5 shrink-0"
        >
          Add
        </button>
      </div>
    </div>
  </div>
</template>

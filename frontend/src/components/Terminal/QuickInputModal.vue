<script setup lang="ts">
interface Props {
  connected: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
  send: [content: string]
  openInput: []
}>()

const handleSend = (content: string) => {
  if (!props.connected) return
  emit('send', content)
}

const handleOpenInput = () => {
  emit('openInput')
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape') {
    emit('close')
  }
}
</script>

<template>
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
    @click.self="emit('close')"
    @keydown="handleKeydown"
  >
    <div class="card max-w-sm w-full">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <h3 class="text-lg font-semibold text-main">Quick Input</h3>
        <button
          @click="emit('close')"
          class="text-sub hover:text-main text-xl"
        >
          ×
        </button>
      </div>

      <!-- Quick input buttons -->
      <div class="space-y-2">
        <!-- ESC button -->
        <button
          @click="handleSend('\x1b')"
          :disabled="!connected"
          class="quick-input-btn w-full font-mono"
        >
          ESC
        </button>

        <!-- Ctrl+C button -->
        <button
          @click="handleSend('\x03')"
          :disabled="!connected"
          class="quick-input-btn w-full font-mono"
        >
          Ctrl + C
        </button>

        <!-- INPUT button (opens multi-line input) -->
        <button
          @click="handleOpenInput"
          :disabled="!connected"
          class="quick-input-btn w-full font-mono"
        >
          INPUT
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.quick-input-btn {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 16px;
  font-weight: 500;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  min-height: 48px;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  transition: all 0.15s ease;
}

.quick-input-btn:hover:not(:disabled) {
  background-color: var(--bg-secondary);
}

.quick-input-btn:active:not(:disabled) {
  background-color: var(--bg-tertiary);
  transform: scale(0.98);
}

.quick-input-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: var(--bg-secondary);
  color: var(--text-muted);
}
</style>
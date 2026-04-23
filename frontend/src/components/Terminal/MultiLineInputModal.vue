<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  connected: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
  send: [content: string]
}>()

const inputText = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

const handleSend = () => {
  if (!props.connected || !inputText.value) return
  emit('send', inputText.value)
  inputText.value = ''
  emit('close')
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape') {
    emit('close')
  }
  // Ctrl+Enter 发送
  if (e.key === 'Enter' && e.ctrlKey) {
    e.preventDefault()
    handleSend()
  }
}
</script>

<template>
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
    @click.self="emit('close')"
    @keydown="handleKeydown"
  >
    <div class="card max-w-lg w-full">
      <!-- Header -->
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-main">Multi-line Input</h3>
        <button
          @click="emit('close')"
          class="text-sub hover:text-main text-xl"
        >
          ×
        </button>
      </div>

      <!-- Textarea -->
      <textarea
        ref="textareaRef"
        v-model="inputText"
        :disabled="!connected"
        class="multiline-input"
        placeholder="Enter text here..."
        rows="10"
        @keydown="handleKeydown"
      ></textarea>

      <!-- Footer -->
      <div class="flex items-center justify-between mt-4">
        <span class="text-xs text-sub">Ctrl+Enter to send</span>
        <button
          @click="handleSend"
          :disabled="!connected || !inputText"
          class="control-btn control-btn-action px-4"
        >
          Send
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.multiline-input {
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.5;
  resize: vertical;
  outline: none;
}

.multiline-input:focus {
  border-color: var(--accent-color, #3b82f6);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.multiline-input::placeholder {
  color: var(--text-muted);
}

.multiline-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: var(--bg-secondary);
}

.control-btn {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--bg-primary);
  color: var(--text-primary);
}

.control-btn-action {
  min-width: 48px;
  height: 28px;
  padding: 0 8px;
  font-weight: 500;
}

@media (hover: hover) {
  .control-btn-action:hover:not(:disabled) {
    background-color: var(--bg-tertiary);
  }
}

.control-btn-action:active:not(:disabled) {
  background-color: var(--border-secondary);
}

.control-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: var(--bg-tertiary);
  color: var(--text-muted);
}
</style>
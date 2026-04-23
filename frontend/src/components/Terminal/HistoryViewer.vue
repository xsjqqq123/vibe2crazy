<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'

interface Props {
  content: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
}>()

const historyRef = ref<HTMLElement | null>(null)

const scrollToBottom = async () => {
  // Use multiple nextTick to ensure DOM is fully rendered
  await nextTick()
  await nextTick()
  await nextTick()

  if (historyRef.value) {
    historyRef.value.scrollTop = historyRef.value.scrollHeight
  }
}

onMounted(() => {
  scrollToBottom()
})

// Watch for content changes and scroll to bottom
watch(() => props.content, () => {
  scrollToBottom()
}, { flush: 'post' })
</script>

<template>
  <div class="history-viewer h-full flex flex-col bg-main">
    <div class="history-header flex items-center justify-between px-4 py-2 bg-sub border-b border-main">
      <div class="flex items-center gap-2">
        <span class="text-sm text-main">Terminal History</span>
        <span class="text-xs text-muted">({{ content.split('\n').length }} lines)</span>
      </div>
      <button
        @click="emit('close')"
        class="text-sub hover:text-main text-sm px-3 py-1 rounded hover:bg-tertiary"
        title="Return to terminal"
      >
        ← Back to Terminal
      </button>
    </div>
    <div
      ref="historyRef"
      class="flex-1 overflow-auto p-4 font-mono text-sm leading-relaxed bg-main text-main"
      style="white-space: pre; tab-size: 4;"
    >{{ content }}</div>
  </div>
</template>

<style scoped>
.history-viewer {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
}

/* Custom scrollbar */
.history-viewer > div:last-child::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}

.history-viewer > div:last-child::-webkit-scrollbar-track {
  background: var(--bg-secondary);
}

.history-viewer > div:last-child::-webkit-scrollbar-thumb {
  background: var(--border-secondary);
  border-radius: 5px;
}

.history-viewer > div:last-child::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}
</style>

<script setup lang="ts">
interface Props {
  showPreviews: boolean
}

interface Emits {
  (e: 'toggle'): void
}

defineProps<Props>()
const emit = defineEmits<Emits>()

const togglePreviews = () => {
  emit('toggle')
}
</script>

<template>
  <button
    class="preview-toggle-btn"
    :class="{ active: showPreviews }"
    title="Toggle preview panels"
    @click="togglePreviews"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      class="h-4 w-4"
      fill="none"
      stroke="currentColor"
    >
      <!-- Left pane -->
      <rect x="2" y="4" width="9" height="16" rx="1" stroke-width="2" />
      <!-- Right pane -->
      <rect x="13" y="4" width="9" height="16" rx="1" stroke-width="2" />
    </svg>
  </button>
</template>

<style scoped>
.preview-toggle-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.375rem;
  border-radius: 0.375rem;
  background-color: transparent;
  border: none;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
  color: var(--text-muted);
}

.preview-toggle-btn:hover {
  background-color: var(--bg-tertiary);
}

.preview-toggle-btn.active {
  color: var(--accent-color);
  background-color: var(--bg-tertiary);
}
</style>
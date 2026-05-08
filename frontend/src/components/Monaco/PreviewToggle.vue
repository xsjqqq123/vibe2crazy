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
    class="p-0 rounded-lg hover:bg-sub transition-colors"
    :class="{ 'text-accent': showPreviews, 'text-sub': !showPreviews }"
    title="Toggle preview panels"
    @click="togglePreviews"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      class="h-5 w-5"
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
</style>
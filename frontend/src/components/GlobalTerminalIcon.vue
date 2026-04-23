<script setup lang="ts">
import { useGlobalTerminalStore } from '@/store/globalTerminal'

const store = useGlobalTerminalStore()
</script>

<template>
  <button
    @click="store.toggle()"
    class="p-1.5 rounded-lg hover:bg-sub"
    title="Global Terminal"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      class="h-5 w-5 text-sub"
      fill="none"
      stroke="currentColor"
    >
      <!-- Monitor/terminal screen outline -->
      <rect x="2" y="3" width="20" height="14" rx="2" stroke-width="2" />
      <!-- Monitor stand -->
      <path stroke-width="2" stroke-linecap="round" d="M8 21h8" />
      <path stroke-width="2" stroke-linecap="round" d="M12 17v4" />
      <!-- Prompt lines inside screen -->
      <path stroke-linecap="round" stroke-width="2" d="M6 9l2.5 2.5L6 14" />
      <path stroke-linecap="round" stroke-width="2" d="M10 14h5" />
    </svg>
  </button>
</template>
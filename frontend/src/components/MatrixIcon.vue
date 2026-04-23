<script setup lang="ts">
const openMatrix = () => {
  window.open('/matrix', '_blank')
}
</script>

<template>
  <button
    @click="openMatrix"
    class="p-1.5 rounded-lg hover:bg-sub hidden md:block"
    title="Terminal Matrix"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      class="h-5 w-5 text-sub"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <!-- 2x2 grid -->
      <rect x="3" y="3" width="7.5" height="7.5" rx="1.5" stroke-width="1.8" />
      <rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5" stroke-width="1.8" />
      <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5" stroke-width="1.8" />
      <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5" stroke-width="1.8" />
    </svg>
  </button>
</template>
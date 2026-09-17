<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const open = () => {
  router.push('/notebook')
}
</script>

<template>
  <button
    @click="open"
    class="p-0 rounded-lg hover:bg-sub"
    title="Markdown Notebook"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      class="h-5 w-5 text-sub"
      fill="none"
      stroke="currentColor"
    >
      <!-- Notebook cover -->
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M6 3h10a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V5a2 2 0 012-2z"
      />
      <!-- Spine -->
      <path stroke-linecap="round" stroke-width="2" d="M8 3v18" />
      <!-- Ruled lines -->
      <path stroke-linecap="round" stroke-width="2" d="M11.5 8h3.5" />
      <path stroke-linecap="round" stroke-width="2" d="M11.5 12h3.5" />
    </svg>
  </button>
</template>

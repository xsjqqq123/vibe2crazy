<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useTheme } from './composables/useTheme'
import GlobalTerminal from '@/components/GlobalTerminal.vue'

const { theme } = useTheme()
</script>

<template>
  <div :class="`theme-${theme}`" class="min-h-screen bg-main text-main">
    <RouterView />
    <GlobalTerminal />
  </div>
</template>
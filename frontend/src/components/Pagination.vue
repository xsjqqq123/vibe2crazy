<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  total: number
  page: number
  pageSize: number
  totalPages: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'page-change', page: number): void
}>()

const pageNumbers = computed(() => {
  const pages: (number | string)[] = []
  const maxVisible = 7

  if (props.totalPages === 0) {
    return pages
  }

  if (props.totalPages <= maxVisible) {
    for (let i = 1; i <= props.totalPages; i++) {
      pages.push(i)
    }
  } else {
    if (props.page <= 3) {
      pages.push(1, 2, 3, 4, '...', props.totalPages)
    } else if (props.page >= props.totalPages - 2) {
      pages.push(1, '...', props.totalPages - 3, props.totalPages - 2,
                 props.totalPages - 1, props.totalPages)
    } else {
      pages.push(1, '...', props.page - 1, props.page,
                 props.page + 1, '...', props.totalPages)
    }
  }

  return pages
})

function goToPage(pageNum: number | string) {
  if (typeof pageNum === 'number') {
    if (pageNum >= 1 && pageNum <= props.totalPages && pageNum !== props.page) {
      emit('page-change', pageNum)
    }
  }
}
</script>

<template>
  <div v-if="totalPages > 0" class="flex flex-col items-center gap-1 py-3">
    <div class="flex items-center gap-1">
      <button
        @click="goToPage(page - 1)"
        :disabled="page === 1"
        class="px-2 py-0.5 rounded border border-gray-300 dark:border-gray-600
               hover:bg-gray-100 dark:hover:bg-gray-700
               disabled:opacity-50 disabled:cursor-not-allowed
               transition-colors text-xs"
      >
        Previous
      </button>

      <template v-for="p in pageNumbers" :key="p">
        <span v-if="p === '...'" class="px-1.5 text-xs">...</span>
        <button
          v-else
          @click="goToPage(p)"
          :class="[
            'px-2 py-0.5 rounded border transition-colors text-xs',
            page === p
              ? 'bg-blue-500 text-white border-blue-500'
              : 'border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700'
          ]"
        >
          {{ p }}
        </button>
      </template>

      <button
        @click="goToPage(page + 1)"
        :disabled="page === totalPages || totalPages === 0"
        class="px-2 py-0.5 rounded border border-gray-300 dark:border-gray-600
               hover:bg-gray-100 dark:hover:bg-gray-700
               disabled:opacity-50 disabled:cursor-not-allowed
               transition-colors text-xs"
      >
        Next
      </button>
    </div>

    <div class="text-xs text-gray-500 dark:text-gray-300">
      Showing {{ total > 0 ? (page - 1) * pageSize + 1 : 0 }}-{{ Math.min(page * pageSize, total) }}
      of {{ total }} commits
    </div>
  </div>
</template>

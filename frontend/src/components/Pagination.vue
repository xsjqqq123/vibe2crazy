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
        class="px-2 py-0.5 rounded border border-main bg-main hover:bg-sub
               disabled:opacity-50 disabled:cursor-not-allowed
               transition-colors text-sm text-main"
      >
        Previous
      </button>

      <template v-for="p in pageNumbers" :key="p">
        <span v-if="p === '...'" class="px-1.5 text-sm">...</span>
        <button
          v-else
          @click="goToPage(p)"
          :class="[
            'px-2 py-0.5 rounded border transition-colors text-sm',
            page === p
              ? 'bg-accent text-white border-accent'
              : 'border-main bg-main hover:bg-sub text-main'
          ]"
        >
          {{ p }}
        </button>
      </template>

      <button
        @click="goToPage(page + 1)"
        :disabled="page === totalPages || totalPages === 0"
        class="px-2 py-0.5 rounded border border-main bg-main hover:bg-sub
               disabled:opacity-50 disabled:cursor-not-allowed
               transition-colors text-sm text-main"
      >
        Next
      </button>
    </div>

    <div class="text-sm text-sub">
      Showing {{ total > 0 ? (page - 1) * pageSize + 1 : 0 }}-{{ Math.min(page * pageSize, total) }}
      of {{ total }} commits
    </div>
  </div>
</template>

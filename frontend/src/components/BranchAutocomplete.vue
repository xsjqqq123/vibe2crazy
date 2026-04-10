<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { getBranches } from '@/api/git'

interface Props {
  modelValue: string
  gitPath: string
  placeholder?: string
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: 'Select branch',
  disabled: false
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  blur: []
}>()

// State
const query = ref(props.modelValue)
const showDropdown = ref(false)
const branches = ref<string[]>([])
const currentBranch = ref('')
const highlightedIndex = ref(-1)
const loading = ref(false)
const isValidRepo = ref(false)

// Template refs
const inputRef = ref<HTMLInputElement>()
const dropdownRef = ref<HTMLDivElement>()
const wrapperRef = ref<HTMLDivElement>()

// Load branches from git repository
const loadBranches = async (path: string) => {
  if (!path || path.trim() === '') {
    branches.value = []
    currentBranch.value = ''
    isValidRepo.value = false
    showDropdown.value = false
    return
  }

  loading.value = true
  try {
    const response = await getBranches(path)
    if (response.success) {
      branches.value = response.branches
      currentBranch.value = response.current_branch
      isValidRepo.value = true

      // Auto-fill current branch if modelValue is empty
      if (!props.modelValue && response.current_branch) {
        query.value = response.current_branch
        emit('update:modelValue', response.current_branch)
      }
    } else {
      branches.value = []
      currentBranch.value = ''
      isValidRepo.value = false
    }
  } catch (error) {
    console.error('Failed to fetch branches:', error)
    branches.value = []
    currentBranch.value = ''
    isValidRepo.value = false
  } finally {
    loading.value = false
  }
}

// Watch for gitPath prop changes
watch(() => props.gitPath, (newPath) => {
  if (newPath) {
    loadBranches(newPath)
  } else {
    branches.value = []
    currentBranch.value = ''
    isValidRepo.value = false
  }
}, { immediate: true })

// Watch for modelValue prop changes
watch(() => props.modelValue, (newValue) => {
  if (newValue !== query.value) {
    query.value = newValue
  }
})

// Watch for query changes
watch(query, (newQuery) => {
  emit('update:modelValue', newQuery)
})

// Select a branch
const selectBranch = (branch: string) => {
  query.value = branch
  showDropdown.value = false
  highlightedIndex.value = -1
}

// Toggle dropdown
const toggleDropdown = () => {
  if (!props.disabled && branches.value.length > 0) {
    showDropdown.value = !showDropdown.value
    highlightedIndex.value = -1
  }
}

// Keyboard navigation
const handleKeydown = (event: KeyboardEvent) => {
  if (!showDropdown.value || branches.value.length === 0) {
    return
  }

  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      highlightedIndex.value = Math.min(highlightedIndex.value + 1, branches.value.length - 1)
      break
    case 'ArrowUp':
      event.preventDefault()
      highlightedIndex.value = Math.max(highlightedIndex.value - 1, -1)
      break
    case 'Enter':
      if (highlightedIndex.value >= 0) {
        event.preventDefault()
        selectBranch(branches.value[highlightedIndex.value])
      }
      break
    case 'Escape':
      showDropdown.value = false
      highlightedIndex.value = -1
      break
  }
}

// Handle blur with delay to allow click events
const handleBlur = () => {
  setTimeout(() => {
    showDropdown.value = false
    highlightedIndex.value = -1
    emit('blur')
  }, 200)
}

// Click outside handler
onClickOutside(wrapperRef, () => {
  showDropdown.value = false
  highlightedIndex.value = -1
})

onBeforeUnmount(() => {
  // Cleanup is handled by onClickOutside
})
</script>

<template>
  <div ref="wrapperRef" class="relative flex">
    <input
      ref="inputRef"
      v-model="query"
      type="text"
      :placeholder="placeholder"
      :disabled="disabled"
      @keydown="handleKeydown"
      @blur="handleBlur"
      class="flex-1 px-3 py-2 border border-gray-300 dark:border-dark-700 rounded-l-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-dark-800 dark:text-gray-100 dark:placeholder-gray-500 disabled:bg-gray-100 dark:disabled:bg-dark-900 disabled:cursor-not-allowed"
    />
    <button
      type="button"
      @click="toggleDropdown"
      :disabled="disabled || branches.length === 0"
      class="px-3 py-2 border border-l-0 border-gray-300 dark:border-dark-700 bg-gray-50 dark:bg-dark-700 rounded-r-md shadow-sm hover:bg-gray-100 dark:hover:bg-dark-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 dark:disabled:bg-dark-900 disabled:cursor-not-allowed disabled:opacity-50"
      title="Select branch"
    >
      <svg
        v-if="loading"
        class="animate-spin h-4 w-4 text-gray-500 dark:text-gray-300"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          class="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          stroke-width="4"
        ></circle>
        <path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        ></path>
      </svg>
      <svg
        v-else
        class="h-4 w-4 text-gray-500 dark:text-gray-300"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M19 9l-7 7-7-7"
        />
      </svg>
    </button>

    <!-- Dropdown list -->
    <div
      v-if="showDropdown && branches.length > 0"
      ref="dropdownRef"
      class="absolute z-10 w-full mt-10 bg-white dark:bg-dark-800 border border-gray-300 dark:border-dark-700 rounded-md shadow-lg max-h-60 overflow-auto"
    >
      <ul class="py-1">
        <li
          v-for="(branch, index) in branches"
          :key="index"
          @click="selectBranch(branch)"
          @mousedown.prevent
          class="px-3 py-2 cursor-pointer transition-colors"
          :class="{
            'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300': index === highlightedIndex,
            'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-700': index !== highlightedIndex,
            'font-semibold': branch === currentBranch
          }"
        >
          {{ branch }}
          <span v-if="branch === currentBranch" class="text-xs text-gray-500 dark:text-gray-400 ml-1">(current)</span>
        </li>
      </ul>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useDebounceFn, onClickOutside } from '@vueuse/core'
import filesystemApi from '@/api/filesystem'

interface Props {
  modelValue: string
  placeholder?: string
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: 'Enter path...',
  disabled: false
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  blur: []
}>()

// State
const query = ref(props.modelValue)
const showDropdown = ref(false)
const suggestions = ref<string[]>([])
const highlightedIndex = ref(-1)
const loading = ref(false)

// Template refs
const inputRef = ref<HTMLInputElement>()
const dropdownRef = ref<HTMLDivElement>()
const wrapperRef = ref<HTMLDivElement>()

// Debounced fetch function
const fetchSuggestions = useDebounceFn(async (path: string) => {
  if (!path || path.trim() === '') {
    suggestions.value = []
    showDropdown.value = false
    return
  }

  loading.value = true
  try {
    const response = await filesystemApi.listDirectories(path)
    suggestions.value = response.directories
    showDropdown.value = suggestions.value.length > 0
    highlightedIndex.value = -1
  } catch (error) {
    console.error('Failed to fetch directories:', error)
    suggestions.value = []
    showDropdown.value = false
  } finally {
    loading.value = false
  }
}, 300)

// Watch for query changes
watch(query, (newQuery) => {
  emit('update:modelValue', newQuery)
  fetchSuggestions(newQuery)
})

// Watch for external modelValue changes
watch(() => props.modelValue, (newValue) => {
  if (newValue !== query.value) {
    query.value = newValue
  }
})

// Select a suggestion
const selectSuggestion = (suggestion: string) => {
  // Auto-append slash to allow continued browsing
  query.value = suggestion.endsWith('/') ? suggestion : suggestion + '/'
  showDropdown.value = false
  highlightedIndex.value = -1
}

// Keyboard navigation
const handleKeydown = (event: KeyboardEvent) => {
  if (!showDropdown.value || suggestions.value.length === 0) {
    return
  }

  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      highlightedIndex.value = Math.min(highlightedIndex.value + 1, suggestions.value.length - 1)
      break
    case 'ArrowUp':
      event.preventDefault()
      highlightedIndex.value = Math.max(highlightedIndex.value - 1, -1)
      break
    case 'Enter':
      if (highlightedIndex.value >= 0) {
        event.preventDefault()
        selectSuggestion(suggestions.value[highlightedIndex.value])
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

// Handle focus
const handleFocus = () => {
  if (query.value && query.value.trim() !== '') {
    fetchSuggestions(query.value)
  }
}

// Click outside handler
onClickOutside(wrapperRef, () => {
  showDropdown.value = false
  highlightedIndex.value = -1
})

// Lifecycle hooks
onMounted(() => {
  // Initialize with current value
  if (query.value && query.value.trim() !== '') {
    fetchSuggestions(query.value)
  }
})

onBeforeUnmount(() => {
  // Cleanup is handled by onClickOutside
})
</script>

<template>
  <div ref="wrapperRef" class="relative">
    <input
      ref="inputRef"
      v-model="query"
      type="text"
      :placeholder="placeholder"
      :disabled="disabled"
      @keydown="handleKeydown"
      @blur="handleBlur"
      @focus="handleFocus"
      class="w-full px-3 py-2 border border-gray-300 dark:border-dark-700 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-dark-800 dark:text-gray-100 dark:placeholder-gray-500 disabled:bg-gray-100 dark:disabled:bg-dark-900 disabled:cursor-not-allowed"
    />

    <!-- Loading indicator -->
    <div
      v-if="loading"
      class="absolute right-3 top-1/2 -translate-y-1/2"
    >
      <svg
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
    </div>

    <!-- Dropdown list -->
    <div
      v-if="showDropdown && suggestions.length > 0"
      ref="dropdownRef"
      class="absolute z-10 w-full mt-1 bg-white dark:bg-dark-800 border border-gray-300 dark:border-dark-700 rounded-md shadow-lg max-h-60 overflow-auto"
    >
      <ul class="py-1">
        <li
          v-for="(suggestion, index) in suggestions"
          :key="index"
          @click="selectSuggestion(suggestion)"
          @mousedown.prevent
          class="px-3 py-2 cursor-pointer transition-colors"
          :class="{
            'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300': index === highlightedIndex,
            'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-700': index !== highlightedIndex
          }"
        >
          {{ suggestion }}
        </li>
      </ul>
    </div>
  </div>
</template>

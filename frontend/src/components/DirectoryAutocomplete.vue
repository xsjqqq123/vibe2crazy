<script setup lang="ts">
import { ref, watch, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
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
const rawSuggestions = ref<string[]>([])
const highlightedIndex = ref(-1)
const loading = ref(false)
const lastFetchedParentPath = ref<string | null>(null)

// Fuzzy match function - matches query characters in order
const fuzzyMatch = (text: string, query: string): boolean => {
  const textLower = text.toLowerCase()
  const queryLower = query.toLowerCase()
  let queryIdx = 0
  for (let i = 0; i < textLower.length && queryIdx < queryLower.length; i++) {
    if (textLower[i] === queryLower[queryIdx]) {
      queryIdx++
    }
  }
  return queryIdx === queryLower.length
}

// Extract parent directory path for API call
const getParentPath = (path: string): string => {
  const lastSlashIndex = path.lastIndexOf('/')
  if (lastSlashIndex <= 0) return '/'
  return path.substring(0, lastSlashIndex + 1)
}

// Extract the segment user is typing (for fuzzy matching)
const getTypingSegment = (path: string): string => {
  const lastSlashIndex = path.lastIndexOf('/')
  return path.substring(lastSlashIndex + 1).toLowerCase()
}

// Computed filtered suggestions with fuzzy matching
const suggestions = computed(() => {
  const typingSegment = getTypingSegment(query.value)
  if (!typingSegment) return rawSuggestions.value.slice(0, 60)
  return rawSuggestions.value
    .filter(dir => {
      // Extract just the directory name (last segment) for matching
      const dirName = dir.split('/').pop()?.toLowerCase() || ''
      return fuzzyMatch(dirName, typingSegment)
    })
    .slice(0, 60)
})

// Template refs
const inputRef = ref<HTMLInputElement>()
const dropdownRef = ref<HTMLDivElement>()
const wrapperRef = ref<HTMLDivElement>()

// Debounced fetch function - fetches parent directory's children
const fetchSuggestions = useDebounceFn(async (path: string) => {
  if (!path || path.trim() === '') {
    rawSuggestions.value = []
    showDropdown.value = false
    lastFetchedParentPath.value = null
    return
  }

  // Get parent directory for API call (where to list directories from)
  const parentPath = getParentPath(path)

  loading.value = true
  lastFetchedParentPath.value = parentPath
  try {
    const response = await filesystemApi.listDirectories(parentPath)
    rawSuggestions.value = response.directories
    // Show dropdown if there are filtered matches
    showDropdown.value = suggestions.value.length > 0
    highlightedIndex.value = -1
  } catch (error) {
    console.error('Failed to fetch directories:', error)
    rawSuggestions.value = []
    showDropdown.value = false
  } finally {
    loading.value = false
  }
}, 300)

// Watch for query changes - emit update and check if we need to fetch
watch(query, (newQuery) => {
  emit('update:modelValue', newQuery)

  // Only fetch if parent path changed (new directory to explore)
  const newParentPath = getParentPath(newQuery)
  if (newParentPath !== lastFetchedParentPath.value) {
    fetchSuggestions(newQuery)
  }
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

// Scroll selected item into view
watch(highlightedIndex, (newIndex) => {
  nextTick(() => {
    if (dropdownRef.value && newIndex >= 0) {
      const items = dropdownRef.value.querySelectorAll('.dropdown-item')
      const selected = items[newIndex] as HTMLElement
      if (selected) {
        selected.scrollIntoView({ block: 'nearest' })
      }
    }
  })
})

// Reset highlightedIndex when filtered suggestions change
// Also update showDropdown based on filtered results
watch(suggestions, (newSuggestions) => {
  highlightedIndex.value = -1
  // Show dropdown if there are filtered matches
  // Hide dropdown if no matches (but keep showing if rawSuggestions is empty - waiting for API)
  if (newSuggestions.length > 0) {
    showDropdown.value = true
  } else if (rawSuggestions.value.length > 0) {
    // No matches for current typing segment, hide dropdown
    showDropdown.value = false
  }
})

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
    // Fetch suggestions using parent path
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
      class="w-full px-3 py-2 border border-main bg-main rounded-md shadow-sm text-main placeholder:text-sub focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent disabled:bg-gray-100 disabled:cursor-not-allowed"
    />

    <!-- Loading indicator -->
    <div
      v-if="loading"
      class="absolute right-3 top-1/2 -translate-y-1/2"
    >
      <svg
        class="animate-spin h-4 w-4 text-sub"
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
      class="absolute z-10 w-full mt-1 bg-main border border-main rounded-md shadow-lg max-h-60 overflow-auto"
    >
      <ul class="py-1">
        <li
          v-for="(suggestion, index) in suggestions"
          :key="index"
          @click="selectSuggestion(suggestion)"
          @mousedown.prevent
          class="dropdown-item px-3 py-2 cursor-pointer transition-colors text-sm"
          :class="{
            'item-selected': index === highlightedIndex,
            'text-main hover:bg-sub': index !== highlightedIndex
          }"
        >
          {{ suggestion }}
        </li>
      </ul>
    </div>
  </div>
</template>

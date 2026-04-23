<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import filesApi, { type TempUploadResult } from '@/api/files'

interface Props {
  taskId: string
}

const props = defineProps<Props>()
const emit = defineEmits<{ close: [], insert: [path: string] }>()

const isUploading = ref(false)
const progress = ref(0)
const uploadSpeed = ref('')
const results = ref<TempUploadResult[]>([])
const isDragging = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const copiedIndex = ref<number | null>(null)

const handleFileSelect = () => fileInputRef.value?.click()

const handleFiles = async (fileList: FileList | null) => {
  if (!fileList || fileList.length === 0) return

  isUploading.value = true
  progress.value = 0

  try {
    const files = Array.from(fileList)
    const response = await filesApi.uploadToTemp(
      props.taskId,
      files,
      (p, s) => {
        progress.value = p
        uploadSpeed.value = s
      }
    )
    results.value.push(...response.results)
  } catch (err: any) {
    results.value = [{
      filename: 'Upload failed',
      path: '',
      size: 0,
      success: false,
      error: err.message || 'Unknown error'
    }]
  } finally {
    isUploading.value = false
  }
}

const handleDrop = (e: DragEvent) => {
  isDragging.value = false
  e.preventDefault()
  handleFiles(e.dataTransfer?.files || null)
}

const handleDragOver = (e: DragEvent) => {
  e.preventDefault()
  isDragging.value = true
}

const handleDragLeave = () => {
  isDragging.value = false
}

const handlePaste = async (e: ClipboardEvent) => {
  const items = e.clipboardData?.items
  if (!items) return

  const files: File[] = []
  for (const item of items) {
    if (item.kind === 'file') {
      const file = item.getAsFile()
      if (file) {
        // Rename clipboard images with timestamp
        if (file.type.startsWith('image/')) {
          const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14)
          const ext = file.name.split('.').pop() || 'png'
          const renamedFile = new File([file], `screenshot-${timestamp}.${ext}`, { type: file.type })
          files.push(renamedFile)
        } else {
          files.push(file)
        }
      }
    }
  }

  if (files.length > 0) {
    isUploading.value = true
    progress.value = 0

    try {
      const response = await filesApi.uploadToTemp(props.taskId, files, (p, s) => {
        progress.value = p
        uploadSpeed.value = s
      })
      results.value.push(...response.results)
    } catch (err: any) {
      results.value = [{
        filename: 'Upload failed',
        path: '',
        size: 0,
        success: false,
        error: err.message
      }]
    } finally {
      isUploading.value = false
    }
  }
}

const copyPath = async (path: string, index: number) => {
  try {
    // Try modern clipboard API first
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(path)
    } else {
      // Fallback for older browsers or non-HTTPS
      const textArea = document.createElement('textarea')
      textArea.value = path
      textArea.style.position = 'fixed'
      textArea.style.left = '-999999px'
      document.body.appendChild(textArea)
      textArea.focus()
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
    }
    // Show success feedback
    copiedIndex.value = index
    setTimeout(() => {
      copiedIndex.value = null
    }, 1500)
  } catch (err) {
    console.error('Failed to copy:', err)
  }
}

const insertPath = (path: string) => {
  emit('insert', path)
}

const clearAll = () => {
  results.value = []
  progress.value = 0
}

const formatSize = (bytes: number) => {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

// Register paste listener on mount
onMounted(() => {
  window.addEventListener('paste', handlePaste)
})

// Clean up paste listener on unmount
onUnmounted(() => {
  window.removeEventListener('paste', handlePaste)
})
</script>

<template>
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
    @click.self="emit('close')"
    @keydown.esc="emit('close')"
  >
    <div class="card max-w-lg w-full">
      <!-- Header -->
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-main">Upload Files</h3>
        <button @click="emit('close')" class="text-sub hover:text-main text-xl">×</button>
      </div>

      <!-- Drop Zone -->
      <div
        v-if="!isUploading && results.length === 0"
        class="drop-zone"
        :class="{ 'drop-zone-active': isDragging }"
        @click="handleFileSelect"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @drop="handleDrop"
      >
        <svg class="w-12 h-12 mx-auto mb-2 text-sub" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        <p class="text-main mb-1">Drag files here or click to select</p>
        <p class="text-sm text-sub">Ctrl+V to paste image from clipboard</p>
      </div>
      <input
        ref="fileInputRef"
        type="file"
        multiple
        class="hidden"
        @change="handleFiles(($event.target as HTMLInputElement).files)"
      />

      <!-- Progress -->
      <div v-if="isUploading" class="upload-progress">
        <p class="text-main mb-2">Uploading... {{ progress }}%</p>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: `${progress}%` }"></div>
        </div>
        <p class="text-sm text-sub mt-1">{{ uploadSpeed }}</p>
      </div>

      <!-- Results -->
      <div v-if="results.length > 0 && !isUploading" class="upload-results">
        <div v-for="(result, index) in results" :key="result.filename" class="result-item">
          <div class="flex items-start gap-2">
            <span v-if="result.success" class="text-green-500">✓</span>
            <span v-else class="text-red-500">✗</span>
            <div class="flex-1 min-w-0">
              <p class="text-main font-medium truncate">{{ result.filename }}</p>
              <p v-if="result.success" class="text-sm text-sub font-mono truncate">{{ result.path }}</p>
              <p v-if="result.success" class="text-xs text-sub">{{ formatSize(result.size) }}</p>
              <p v-if="result.error" class="text-sm text-red-500">{{ result.error }}</p>
            </div>
            <div v-if="result.success" class="flex gap-1">
            <button
              @click.stop="copyPath(result.path, index)"
              class="copy-btn"
              :class="{ 'copy-btn-success': copiedIndex === index }"
            >
              {{ copiedIndex === index ? 'Copied!' : 'Copy' }}
            </button>
            <button
              @click.stop="insertPath(result.path)"
              class="copy-btn insert-btn"
            >
              Insert
            </button>
          </div>
          </div>
        </div>
        <button @click="clearAll" class="upload-more-btn mt-4">
          Clear All
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.drop-zone {
  border: 2px dashed var(--border-color);
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}
@media (hover: hover) {
  .drop-zone:hover {
    border-color: var(--accent-color);
    background-color: var(--bg-secondary);
  }
}
.progress-bar {
  height: 8px;
  background: var(--bg-tertiary);
  border-radius: 4px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: var(--accent-color);
  transition: width 0.2s;
}
.result-item {
  padding: 0.75rem;
  border-radius: 6px;
  background: var(--bg-secondary);
  margin-bottom: 0.5rem;
}
.copy-btn {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
  border-radius: 4px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border: none;
  cursor: pointer;
}
@media (hover: hover) {
  .copy-btn:hover {
    background: var(--accent-color);
  }
}
.copy-btn-success {
  background: #22c55e;
  color: white;
}
.insert-btn {
  background: var(--accent-color);
}
@media (hover: hover) {
  .insert-btn:hover {
    opacity: 0.9;
  }
}
.upload-more-btn {
  width: 100%;
  padding: 0.5rem;
  border-radius: 6px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border: none;
  cursor: pointer;
}
@media (hover: hover) {
  .upload-more-btn:hover {
    background: var(--accent-color);
  }
}
</style>
<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { gitApi, type CommitDiff, type FileDiff } from '@/api/git'
import MonacoDiffEditor from '@/components/Monaco/MonacoDiffEditor.vue'
import Pagination from '@/components/Pagination.vue'

interface Props {
  taskId: string
  commitHash: string
}

const props = defineProps<Props>()

// Commit info
const commitInfo = ref<CommitDiff | null>(null)
const loadingCommit = ref(false)
const commitError = ref('')

// File list
const files = ref<CommitDiff['files']>([])
const currentPage = ref(1)
const pageSize = 20

// File diff cache and loading state
const fileDiffs = ref<Map<string, FileDiff>>(new Map())
const loadingFiles = ref<Set<string>>(new Set())
const expandedFiles = ref<Set<string>>(new Set())

// Mobile detection
const isMobile = ref(false)

const checkMobile = () => {
  isMobile.value = window.innerWidth < 768
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  loadCommitFiles()
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

// Watch for commitHash changes to reload
watch(() => props.commitHash, () => {
  fileDiffs.value.clear()
  expandedFiles.value.clear()
  loadingFiles.value.clear()
  currentPage.value = 1
  loadCommitFiles()
})

async function loadCommitFiles(page: number = 1) {
  loadingCommit.value = true
  commitError.value = ''
  try {
    commitInfo.value = await gitApi.getCommitDiff(props.taskId, props.commitHash, page, pageSize)
    files.value = commitInfo.value.files
    currentPage.value = commitInfo.value.page
  } catch (err: any) {
    commitError.value = err.message || 'Failed to load commit files'
  }
  loadingCommit.value = false
}

async function toggleFile(filePath: string) {
  if (expandedFiles.value.has(filePath)) {
    expandedFiles.value.delete(filePath)
    return
  }

  expandedFiles.value.add(filePath)

  // Load diff if not cached
  if (!fileDiffs.value.has(filePath) && !loadingFiles.value.has(filePath)) {
    loadingFiles.value.add(filePath)
    try {
      const diff = await gitApi.getFileDiff(props.taskId, props.commitHash, filePath)
      fileDiffs.value.set(filePath, diff)
    } catch (err: any) {
      console.error('Failed to load file diff:', err)
      fileDiffs.value.set(filePath, {
        path: filePath,
        status: 'M',
        original: '',
        modified: `[Error loading diff: ${err.message || 'Unknown error'}]`
      })
    }
    loadingFiles.value.delete(filePath)
  }
}

function isExpanded(path: string) {
  return expandedFiles.value.has(path)
}

function isLoading(path: string) {
  return loadingFiles.value.has(path)
}

function getFileDiff(path: string): FileDiff | undefined {
  return fileDiffs.value.get(path)
}

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'A': return '+'
    case 'M': return '~'
    case 'D': return '×'
    default: return '?'
  }
}

function handlePageChange(page: number) {
  loadCommitFiles(page)
}
</script>

<template>
  <div class="commit-diff-view h-full flex flex-col overflow-hidden bg-main">
    <!-- Loading state -->
    <div v-if="loadingCommit" class="flex items-center justify-center h-full">
      <div class="spinner"></div>
    </div>

    <!-- Error state -->
    <div v-else-if="commitError" class="flex items-center justify-center h-full text-red-600 dark:text-red-400 p-4">
      {{ commitError }}
    </div>

    <!-- Commit header -->
    <div v-else-if="commitInfo" class="border-b border-main px-4 py-2 bg-sub">
      <div class="flex items-center gap-2 text-sm text-main">
        <code class="font-mono text-accent">{{ commitInfo.hash }}</code>
        <span class="text-sub">-</span>
        <span class="text-sub truncate">{{ commitInfo.message }}</span>
      </div>
      <div class="text-xs text-muted mt-1">
        {{ commitInfo.total_files }} file(s) changed
      </div>
    </div>

    <!-- File diffs list -->
    <div v-if="commitInfo" class="flex-1 overflow-y-auto p-4 space-y-2">
      <div
        v-for="file in files"
        :key="file.path"
        class="file-diff-item"
      >
        <!-- File header -->
        <div
          @click="toggleFile(file.path)"
          class="file-header flex items-center justify-between p-2 bg-sub cursor-pointer hover:bg-tertiary"
        >
          <div class="flex items-center gap-2">
            <span class="file-status">{{ getStatusIcon(file.status) }}</span>
            <span class="file-path text-sm text-main truncate">
              {{ file.path }}
            </span>
            <span class="text-xs ml-auto shrink-0">
              <span v-if="file.additions > 0" class="text-green-600">+{{ file.additions }}</span>
              <span v-if="file.deletions > 0" class="text-red-600"> -{{ file.deletions }}</span>
            </span>
          </div>
          <div class="flex items-center gap-2">
            <span v-if="isLoading(file.path)" class="spinner-xs"></span>
            <span class="text-xs text-sub">
              {{ isExpanded(file.path) ? '▼' : '▶' }}
            </span>
          </div>
        </div>

        <!-- Diff content (collapsible) -->
        <div v-show="isExpanded(file.path)" class="file-diff-content border border-main rounded-b">
          <div v-if="isLoading(file.path)" class="flex items-center justify-center p-8">
            <div class="spinner"></div>
          </div>
          <div v-else-if="getFileDiff(file.path)" class="editor-wrapper">
            <MonacoDiffEditor
              :original="getFileDiff(file.path)!.original"
              :modified="getFileDiff(file.path)!.modified"
              :path="file.path"
              :is-mobile="isMobile"
            />
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-if="files.length === 0" class="flex items-center justify-center py-12 text-sub">
        No files changed in this commit
      </div>

      <!-- Pagination -->
      <Pagination
        v-if="commitInfo && commitInfo.total_pages > 1"
        :total="commitInfo.total_files"
        :page="commitInfo.page"
        :page-size="commitInfo.page_size"
        :total-pages="commitInfo.total_pages"
        @page-change="handlePageChange"
      />
    </div>
  </div>
</template>

<style scoped>
.commit-diff-view {
  font-size: 12px;
}

.file-diff-item {
  border: 1px solid var(--border-color);
  border-radius: 4px;
}

.file-header {
  user-select: none;
  border-top-left-radius: 4px;
  border-top-right-radius: 4px;
}

.file-status {
  display: inline-block;
  width: 12px;
  text-align: center;
  font-weight: bold;
}

.file-path {
  flex: 1;
  min-width: 0;
}

.file-diff-content {
  margin-top: 0;
}

.editor-wrapper {
  height: 600px;
  min-height: 400px;
}
</style>

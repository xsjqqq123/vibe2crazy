<script setup lang="ts">
import { watch, nextTick, ref } from 'vue'
import type { CommitInfo } from '@/api/git'

interface Props {
  commits: CommitInfo[]
  loading?: boolean
  error?: string
  lastMergeCommitHash?: string
  newCommitHashes?: Set<string>
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  error: '',
  lastMergeCommitHash: '',
  newCommitHashes: () => new Set<string>()
})

const emit = defineEmits<{
  select: [commitHash: string]
  showContextMenu: [event: { x: number; y: number; commit: CommitInfo }]
}>()

const isLastMergeCommit = (hash: string) => {
  return props.lastMergeCommitHash === hash
}

const isNewCommit = (hash: string) => {
  return props.newCommitHashes?.has(hash) || false
}

// Scroll position tracking
const commitsListRef = ref<HTMLElement | null>(null)
const savedScrollTop = ref(0)

const saveScrollPos = () => {
  if (commitsListRef.value) {
    savedScrollTop.value = commitsListRef.value.scrollTop
  }
}

const restoreScrollPos = () => {
  nextTick(() => {
    if (commitsListRef.value && savedScrollTop.value > 0) {
      commitsListRef.value.scrollTop = savedScrollTop.value
    }
  })
}

// Watch for commits changes to preserve scroll position
watch(() => props.commits, async (newCommits, oldCommits) => {
  // Save scroll position before update (only if we had content before)
  if (oldCommits && oldCommits.length > 0) {
    saveScrollPos()
  }

  // Restore after update (only if we have content now)
  if (newCommits && newCommits.length > 0) {
    await nextTick()
    restoreScrollPos()
  }
}, { deep: true })


const formatLocalDateTime = (dateStr: string) => {
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) {
    return 'Invalid date'
  }
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

const handleContextMenu = (e: MouseEvent, commit: CommitInfo) => {
  e.preventDefault()
  e.stopPropagation()
  emit('showContextMenu', {
    x: e.clientX,
    y: e.clientY,
    commit
  })
}
</script>

<template>
  <div ref="commitsListRef" class="commits-list">
    <!-- Loading state -->
    <div v-if="loading" class="flex items-center justify-center py-4">
      <div class="spinner"></div>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="text-xs text-red-600 py-2">
      {{ error }}
    </div>

    <!-- Empty state -->
    <div v-else-if="commits.length === 0" class="text-xs text-muted py-2">
      No commits yet
    </div>

    <!-- Commits list -->
    <div v-else class="space-y-2">
      <div
        v-for="commit in commits"
        :key="commit.hash"
        :class="{
          'commit-item': true,
          'p-2 bg-sub rounded cursor-pointer hover:bg-accent/10': true,
          'new-commit': isNewCommit(commit.hash)
        }"
        @click="emit('select', commit.hash)"
        @contextmenu.prevent.stop="handleContextMenu($event, commit)"
      >
        <!-- Header: Hash and Date -->
        <div class="flex items-center justify-between mb-1">
          <div class="flex items-center gap-2">
            <!-- Green checkmark for last merge commit -->
            <span v-if="isLastMergeCommit(commit.hash)" class="merge-badge">
              ✓
            </span>
            <code class="text-xs font-mono text-accent">
              {{ commit.hash.slice(0, 8) }}
            </code>
          </div>
          <span class="text-xs text-muted">
            {{ formatLocalDateTime(commit.date) }}
          </span>
        </div>

        <!-- Title: Commit message -->
        <p class="text-sm text-main">
          {{ commit.message || 'No message' }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.commits-list {
  font-size: 12px;
}

.file-status {
  display: inline-block;
  width: 12px;
  text-align: center;
}

.merge-badge {
  display: inline-block;
  width: 14px;
  height: 14px;
  background-color: #238636;
  color: white;
  border-radius: 50%;
  text-align: center;
  line-height: 14px;
  font-weight: bold;
  font-size: 10px;
  flex-shrink: 0;
  box-shadow: 0 0 8px rgba(35, 134, 54, 0.4);
}

@keyframes highlight-flash {
  0% {
    background-color: rgba(250, 204, 21, 0.3);
  }
  100% {
    background-color: transparent;
  }
}

.commit-item.new-commit {
  animation: highlight-flash 1.5s ease-out;
}
</style>

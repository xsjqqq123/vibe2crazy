<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { marked } from 'marked'
import { useTheme } from '@/composables/useTheme'

interface DownloadInfo {
  id: string
  platform: string
  download_url: string
  file_size: number | null
  file_hash: string | null
}

interface VersionInfo {
  version: string
  title: string
  description: string
  published_at: string
  downloads: DownloadInfo[]
}

interface Props {
  visible: boolean
  versionInfo: VersionInfo | null
  currentVersion: string
  currentPlatform: string
}

const props = defineProps<Props>()
const emit = defineEmits(['close'])

const { isDark } = useTheme()

// Configure marked for safe rendering
marked.setOptions({
  breaks: true,
  gfm: true
})

function close() {
  emit('close')
}

const renderedDescription = computed(() => {
  if (!props.versionInfo?.description) return ''
  return marked.parse(props.versionInfo.description) as string
})

function getPlatformLabel(platform: string): string {
  const labels: Record<string, string> = {
    'linux-x64': 'Linux (x64)',
    'linux-arm64': 'Linux (ARM64)',
    'windows-x64': 'Windows (x64)',
    'windows-arm64': 'Windows (ARM64)',
    'macos-x64': 'macOS (Intel)',
    'macos-arm64': 'macOS (Apple Silicon)'
  }
  return labels[platform] || platform
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return ''
  const mb = bytes / (1024 * 1024)
  if (mb >= 1) {
    return `${mb.toFixed(1)} MB`
  }
  const kb = bytes / 1024
  return `${kb.toFixed(1)} KB`
}

// Keyboard handler
const handleKeyDown = (e: KeyboardEvent) => {
  if (!props.visible) return

  // ESC to close
  if (e.key === 'Escape') {
    close()
    return
  }
}

// Lifecycle
onMounted(() => {
  document.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyDown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="visible" class="update-modal-overlay" @click.self="close">
        <div class="update-modal-container" :class="{ 'update-dark': isDark }">
          <!-- Header -->
          <div class="update-modal-header">
            <h3>{{ versionInfo?.title || `v${versionInfo?.version}` }}</h3>
            <button class="update-close-btn" @click="close" title="Close (ESC)">
              ✕
            </button>
          </div>

          <!-- Body -->
          <div class="update-modal-body">
            <!-- Version badges -->
            <div class="update-version-info">
              <span class="update-badge update-badge-new">
                New: v{{ versionInfo?.version }}
              </span>
              <span class="update-badge update-badge-current">
                Current: v{{ currentVersion }}
              </span>
            </div>

            <!-- Release notes -->
            <div class="update-description">
              <h4>Release Notes</h4>
              <div
                class="update-markdown-content"
                :class="{ 'update-dark': isDark }"
                v-html="renderedDescription"
              ></div>
            </div>

            <!-- Downloads -->
            <div class="update-downloads">
              <h4>Downloads</h4>
              <div class="update-download-list">
                <div
                  v-for="download in versionInfo?.downloads"
                  :key="download.id"
                  class="update-download-item"
                  :class="{ 'update-current-platform': download.platform === currentPlatform }"
                >
                  <span class="update-platform-name">{{ getPlatformLabel(download.platform) }}</span>
                  <span class="update-file-info">
                    {{ formatFileSize(download.file_size) }}
                  </span>
                  <a
                    :href="download.download_url"
                    class="update-download-btn"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Download
                  </a>
                </div>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="update-modal-footer">
            <button class="update-btn update-btn-secondary" @click="close">
              Close
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.update-modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgb(0 0 0 / 0.6);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.update-modal-container {
  background-color: rgb(255 255 255);
  border-radius: 0.75rem;
  max-width: 600px;
  width: 100%;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 25px 50px -12px rgb(0 0 0 / 0.25);
}

.update-dark.update-modal-container {
  background-color: rgb(31 41 55); /* gray-800 */
}

/* Header */
.update-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid rgb(229 231 235); /* gray-200 */
}

.update-dark .update-modal-header {
  border-bottom-color: rgb(55 65 81); /* gray-700 */
}

.update-modal-header h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: rgb(17 24 39); /* gray-900 */
}

.update-dark .update-modal-header h3 {
  color: rgb(229 231 235); /* gray-200 */
}

.update-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  padding: 0;
  background-color: rgb(255 255 255);
  color: rgb(55 65 81); /* gray-700 */
  border: 1px solid rgb(229 231 235); /* gray-200 */
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  transition: all 0.15s ease;
}

.update-dark .update-close-btn {
  background-color: rgb(55 65 81); /* gray-700 */
  color: rgb(209 213 219); /* gray-300 */
  border-color: rgb(75 85 99); /* gray-600 */
}

@media (hover: hover) {
.update-close-btn:hover {
  background-color: rgb(220 38 38); /* red-600 */
  color: rgb(255 255 255);
  border-color: rgb(220 38 38);
}
}

/* Body */
.update-modal-body {
  padding: 1.5rem;
}

/* Version info badges */
.update-version-info {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.update-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.update-badge-new {
  background-color: rgb(34 197 94); /* green-500 */
  color: rgb(255 255 255);
}

.update-badge-current {
  background-color: rgb(243 244 246); /* gray-100 */
  color: rgb(107 114 128); /* gray-500 */
}

.update-dark .update-badge-current {
  background-color: rgb(55 65 81); /* gray-700 */
  color: rgb(156 163 175); /* gray-400 */
}

/* Description / Release Notes */
.update-description {
  margin-bottom: 1.5rem;
}

.update-description h4 {
  margin: 0 0 0.5rem 0;
  font-size: 1rem;
  font-weight: 600;
  color: rgb(17 24 39); /* gray-900 */
}

.update-dark .update-description h4 {
  color: rgb(229 231 235); /* gray-200 */
}

.update-markdown-content {
  background-color: rgb(243 244 246); /* gray-100 */
  padding: 1rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  line-height: 1.6;
}

.update-dark.update-markdown-content {
  background-color: rgb(55 65 81); /* gray-700 */
  color: rgb(209 213 219); /* gray-300 */
}

.update-markdown-content :deep(h1),
.update-markdown-content :deep(h2),
.update-markdown-content :deep(h3),
.update-markdown-content :deep(h4),
.update-markdown-content :deep(h5),
.update-markdown-content :deep(h6) {
  margin-top: 1em;
  margin-bottom: 0.5em;
  font-weight: 600;
  color: rgb(17 24 39); /* gray-900 */
}

.update-dark .update-markdown-content :deep(h1),
.update-dark .update-markdown-content :deep(h2),
.update-dark .update-markdown-content :deep(h3),
.update-dark .update-markdown-content :deep(h4),
.update-dark .update-markdown-content :deep(h5),
.update-dark .update-markdown-content :deep(h6) {
  color: rgb(229 231 235); /* gray-200 */
}

.update-markdown-content :deep(p) {
  margin: 0 0 1em;
}

.update-markdown-content :deep(ul),
.update-markdown-content :deep(ol) {
  margin: 0 0 1em;
  padding-left: 1.5em;
}

.update-markdown-content :deep(li) {
  margin: 0.25em 0;
}

.update-markdown-content :deep(code) {
  padding: 0.2em 0.4em;
  background-color: rgb(229 231 235); /* gray-200 */
  border-radius: 0.25rem;
  font-size: 0.8em;
}

.update-dark .update-markdown-content :deep(code) {
  background-color: rgb(75 85 99); /* gray-600 */
}

.update-markdown-content :deep(pre) {
  margin: 1em 0;
  padding: 0.75em;
  background-color: rgb(229 231 235); /* gray-200 */
  border-radius: 0.375rem;
  overflow-x: auto;
}

.update-dark .update-markdown-content :deep(pre) {
  background-color: rgb(31 41 55); /* gray-800 */
}

.update-markdown-content :deep(pre code) {
  padding: 0;
  background-color: transparent;
}

.update-markdown-content :deep(a) {
  color: rgb(59 130 246); /* blue-500 */
  text-decoration: underline;
}

/* Downloads */
.update-downloads h4 {
  margin: 0 0 0.5rem 0;
  font-size: 1rem;
  font-weight: 600;
  color: rgb(17 24 39); /* gray-900 */
}

.update-dark .update-downloads h4 {
  color: rgb(229 231 235); /* gray-200 */
}

.update-download-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.update-download-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background-color: rgb(243 244 246); /* gray-100 */
  border-radius: 0.5rem;
  border: 1px solid transparent;
}

.update-dark .update-download-item {
  background-color: rgb(55 65 81); /* gray-700 */
}

.update-download-item.update-current-platform {
  background-color: rgb(220 252 231); /* green-100 */
  border-color: rgb(34 197 94); /* green-500 */
}

.update-dark .update-download-item.update-current-platform {
  background-color: rgb(20 83 45); /* green-900 */
  border-color: rgb(34 197 94); /* green-500 */
}

.update-platform-name {
  font-weight: 500;
  min-width: 140px;
  color: rgb(17 24 39); /* gray-900 */
}

.update-dark .update-platform-name {
  color: rgb(229 231 235); /* gray-200 */
}

.update-file-info {
  color: rgb(107 114 128); /* gray-500 */
  font-size: 0.875rem;
}

.update-dark .update-file-info {
  color: rgb(156 163 175); /* gray-400 */
}

.update-download-btn {
  margin-left: auto;
  padding: 0.375rem 0.75rem;
  background-color: rgb(59 130 246); /* blue-500 */
  color: rgb(255 255 255);
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  text-decoration: none;
  transition: background-color 0.15s ease;
}

@media (hover: hover) {
.update-download-btn:hover {
  background-color: rgb(37 99 235); /* blue-600 */
}
}

/* Footer */
.update-modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid rgb(229 231 235); /* gray-200 */
  display: flex;
  justify-content: flex-end;
}

.update-dark .update-modal-footer {
  border-top-color: rgb(55 65 81); /* gray-700 */
}

.update-btn {
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.update-btn-secondary {
  background-color: rgb(243 244 246); /* gray-100 */
  color: rgb(55 65 81); /* gray-700 */
  border: 1px solid rgb(229 231 235); /* gray-200 */
}

.update-dark .update-btn-secondary {
  background-color: rgb(55 65 81); /* gray-700 */
  color: rgb(209 213 219); /* gray-300 */
  border-color: rgb(75 85 99); /* gray-600 */
}

@media (hover: hover) {
.update-btn-secondary:hover {
  background-color: rgb(229 231 235); /* gray-200 */
}

.update-dark .update-btn-secondary:hover {
  background-color: rgb(75 85 99); /* gray-600 */
}
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Mobile responsive */
@media (max-width: 640px) {
  .update-modal-overlay {
    padding: 0.5rem;
  }

  .update-modal-header {
    padding: 0.75rem 1rem;
  }

  .update-modal-header h3 {
    font-size: 1rem;
  }

  .update-modal-body {
    padding: 1rem;
  }

  .update-version-info {
    flex-direction: column;
    gap: 0.5rem;
  }

  .update-download-item {
    flex-wrap: wrap;
    gap: 0.5rem;
    padding: 0.75rem;
  }

  .update-platform-name {
    min-width: auto;
  }

  .update-download-btn {
    margin-left: 0;
    width: 100%;
    text-align: center;
  }

  .update-modal-footer {
    padding: 0.75rem 1rem;
  }
}
</style>
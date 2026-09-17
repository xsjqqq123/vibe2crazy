<script setup lang="ts">
/**
 * Full-screen markdown preview overlay.
 *
 * Rendering and outline live in MarkdownPane; this component only owns the
 * modal chrome (toolbar, ESC handling, copy button).
 */
import { onMounted, onUnmounted } from 'vue'
import MarkdownPane from './MarkdownPane.vue'

interface Props {
  taskId: string
  filePath: string
  content: string
  show: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
  contentChange: [content: string]
}>()

const copyMarkdown = async () => {
  try {
    await navigator.clipboard.writeText(props.content)
  } catch (e) {
    console.error('Failed to copy:', e)
  }
}

const handleKeyDown = (e: KeyboardEvent) => {
  if (!props.show) return
  if (e.key === 'Escape') {
    emit('close')
  }
}

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
      <div v-if="show" class="md-modal-overlay" @click.self="$emit('close')">
        <div class="md-modal-container">
          <!-- Toolbar -->
          <div class="md-toolbar">
            <div class="md-toolbar-section md-file-name">
              <span class="md-icon">📝</span>
              <span class="truncate">{{ filePath }}</span>
            </div>

            <div class="md-toolbar-section">
              <button @click="copyMarkdown" class="md-toolbar-btn" title="Copy markdown content">
                📋
              </button>
            </div>

            <button @click="$emit('close')" class="md-close-btn" title="Close (ESC)">
              ✕
            </button>
          </div>

          <!-- Markdown viewer -->
          <MarkdownPane :content="content" />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.md-modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgb(0 0 0 / 0.9);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.md-modal-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-primary);
  color: var(--text-primary);
}

/* Toolbar */
.md-toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background-color: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}

.md-toolbar-section {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.md-file-name {
  max-width: 400px;
  min-width: 150px;
}

.md-file-name span {
  color: var(--text-primary);
  font-size: 0.875rem;
}

.md-icon {
  flex-shrink: 0;
}

.md-toolbar-btn,
.md-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  padding: 0;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.md-close-btn {
  margin-left: auto;
  font-size: 1rem;
  line-height: 1;
}

@media (hover: hover) {
  .md-toolbar-btn:hover {
    background-color: var(--bg-tertiary);
  }
  .md-close-btn:hover {
    background-color: rgb(220 38 38);
    color: rgb(255 255 255);
    border-color: rgb(220 38 38);
  }
}

.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

@media (max-width: 768px) {
  .md-toolbar {
    gap: 0.5rem;
    padding: 0.5rem;
  }

  .md-file-name {
    max-width: 150px;
    min-width: 100px;
  }

  .md-toolbar-btn,
  .md-close-btn {
    width: 1.75rem;
    height: 1.75rem;
    font-size: 0.875rem;
  }
}
</style>

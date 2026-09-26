<script setup lang="ts">
/**
 * Full-screen markdown preview overlay.
 *
 * Rendering and outline live in MarkdownPane; this component only owns the
 * modal chrome (toolbar, ESC handling, copy button).
 */
import { onMounted, onUnmounted, watch } from 'vue'
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

const handlePrint = () => {
  window.print()
}

const handleKeyDown = (e: KeyboardEvent) => {
  if (!props.show) return
  if (e.key === 'Escape') {
    emit('close')
  }
}

// While the modal is open, a body class tells @media print to hide the rest of
// the app and render only the rendered markdown (also covers native Ctrl+P).
watch(
  () => props.show,
  (open) => {
    if (open) document.body.classList.add('md-printing-modal')
    else document.body.classList.remove('md-printing-modal')
  }
)

onMounted(() => {
  document.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyDown)
  document.body.classList.remove('md-printing-modal')
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
              <button @click="handlePrint" class="md-toolbar-btn" title="Print (Ctrl+P)">
                🖨️
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

<style>
/* ---------------------------------------------------------------------------
 * Print styles.
 *
 * Deliberately GLOBAL (non-scoped): this needs to reach #app, which lives
 * outside the component, plus the internals of MarkdownPane/MarkdownRenderer
 * (child components with their own scoped data-v attrs). A scoped block
 * compiles to `#app[data-v-x]` / `body[data-v-x] .md-content` which matches
 * nothing, silently disabling every override.
 *
 * Everything is gated on body.md-printing-modal, which the component adds on
 * mount/open and removes on close/unmount, so normal page printing is
 * untouched.
 * ------------------------------------------------------------------------- */
@media print {
  body.md-printing-modal #app {
    display: none !important;
  }

  body.md-printing-modal .md-modal-overlay {
    position: static;
    display: block;
    background: none !important;
    padding: 0;
  }

  body.md-printing-modal .md-modal-container {
    height: auto;
    flex: none;
    background-color: #ffffff;
  }

  body.md-printing-modal .md-toolbar,
  body.md-printing-modal .md-close-btn,
  body.md-printing-modal .md-outline {
    display: none !important;
  }

  body.md-printing-modal .md-pane {
    display: block;
    overflow: visible;
  }

  body.md-printing-modal .md-scroll-content {
    overflow: visible !important;
    padding: 0;
  }

  /* Override theme CSS variables so the rendered doc is light-on-white no
     matter which app theme is active in the preview. */
  body.md-printing-modal .md-content {
    max-width: none;
    color: #111111;
    --bg-primary: #ffffff;
    --bg-secondary: #f6f6f7;
    --bg-tertiary: #ececef;
    --text-primary: #111111;
    --text-secondary: #333333;
    --text-muted: #666666;
    --border-color: #cfcfd4;
    --border-secondary: #9a9aa2;
    --accent-color: #1a56db;
    --accent-hover: #1a56db;
    --md-code-keyword: #a01cad;
    --md-code-string: #3f6206;
    --md-code-number: #8a5a00;
    --md-code-function: #1d4ed8;
    --md-code-variable: #b91c1c;
  }

  body.md-printing-modal .md-content a {
    color: #1a56db;
  }

  body.md-printing-modal .md-content h1,
  body.md-printing-modal .md-content h2,
  body.md-printing-modal .md-content h3,
  body.md-printing-modal .md-content h4 {
    break-after: avoid;
  }

  body.md-printing-modal .md-content pre,
  body.md-printing-modal .md-content table,
  body.md-printing-modal .md-content blockquote {
    break-inside: avoid;
  }
}
</style>

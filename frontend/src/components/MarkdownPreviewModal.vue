<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { useTheme } from '@/composables/useTheme'

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

const { isDark } = useTheme()

// State
const contentRef = ref<HTMLElement>()
const mermaidRef = ref<any>(null)
const mermaidRenderError = ref(false)
const mermaidLoading = ref(false)

// Initialize markdown-it with syntax highlighting
const md: MarkdownIt = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  highlight: (str, lang) => {
    if (lang === 'mermaid') {
      return `<div class="mermaid">${md.utils.escapeHtml(str)}</div>`
    }
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(str, { language: lang }).value}</code></pre>`
      } catch (__) {}
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(str)}</code></pre>`
  }
})

// Render markdown
const renderedMarkdown = computed(() => {
  if (!props.content) return '<p class="md-empty">No content</p>'
  try {
    return md.render(props.content)
  } catch (e) {
    return `<p class="md-error">Failed to render markdown: ${e}</p>`
  }
})

// Copy markdown content
const copyMarkdown = async () => {
  try {
    await navigator.clipboard.writeText(props.content)
  } catch (e) {
    console.error('Failed to copy:', e)
  }
}

// Keyboard handler
const handleKeyDown = (e: KeyboardEvent) => {
  if (!props.show) return

  // ESC to close
  if (e.key === 'Escape') {
    emit('close')
    return
  }
}

// Lifecycle
onMounted(() => {
  document.addEventListener('keydown', handleKeyDown)
  loadMermaid()
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyDown)
})

// Dynamic import and initialize mermaid
const loadMermaid = async () => {
  try {
    mermaidLoading.value = true
    const mermaidModule = await import('mermaid')
    mermaidRef.value = mermaidModule.default
    mermaidRef.value.initialize({
      startOnLoad: false,
      theme: isDark.value ? 'dark' : 'default',
      securityLevel: 'loose',
    })
  } catch (e) {
    console.error('Failed to load mermaid:', e)
    mermaidRenderError.value = true
  } finally {
    mermaidLoading.value = false
  }
}

// Render mermaid diagrams after DOM updates
watch([() => props.show, renderedMarkdown], async ([show]) => {
  if (!show || !mermaidRef.value) return
  await nextTick()
  const elements = contentRef.value?.querySelectorAll('.mermaid')
  if (!elements || elements.length === 0) return
  try {
    await mermaidRef.value.run({ nodes: [...elements] })
  } catch (e) {
    console.error('Mermaid render error:', e)
  }
}, { flush: 'post' })

// Re-render mermaid on theme change
watch(isDark, async (dark) => {
  if (!mermaidRef.value) return
  mermaidRef.value.initialize({
    startOnLoad: false,
    theme: dark ? 'dark' : 'default',
    securityLevel: 'loose',
  })
  await nextTick()
  const elements = contentRef.value?.querySelectorAll('.mermaid')
  if (!elements || elements.length === 0) return
  try {
    await mermaidRef.value.run({ nodes: [...elements] })
  } catch (e) {
    console.error('Mermaid re-render error:', e)
  }
})

// --- Heading / Outline ---
interface HeadingItem {
  level: number
  text: string
  anchorId: string
}

const slugify = (text: string): string => {
  return text
    .toLowerCase()
    .replace(/<[^>]*>/g, '')
    .replace(/[^\w\u4e00-\u9fff\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '')
}

const extractHeadingText = (raw: string): string => {
  return raw
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`(.+?)`/g, '$1')
    .replace(/\[(.+?)\]\(.+?\)/g, '$1')
    .replace(/<[^>]*>/g, '')
    .trim()
}

const headings = computed<HeadingItem[]>(() => {
  if (!props.content) return []
  const lines = props.content.split('\n')
  const result: HeadingItem[] = []
  for (const line of lines) {
    const match = line.match(/^(#{1,6})\s+(.+)/)
    if (match) {
      const level = match[1].length
      const rawText = match[2].trim()
      const text = extractHeadingText(rawText)
      const anchorId = slugify(text)
      result.push({ level, text, anchorId })
    }
  }
  return result
})

// Add anchor IDs to rendered headings for scroll-to navigation
md.renderer.rules.heading_open = (tokens, idx, options, _env, self) => {
  const token = tokens[idx]
  const inlineToken = tokens[idx + 1]
  if (inlineToken && inlineToken.type === 'inline') {
    const text = extractHeadingText(inlineToken.content)
    token.attrSet('id', slugify(text))
  }
  return self.renderToken(tokens, idx, options)
}

const activeHeading = ref<string>('')

const scrollToHeading = (anchorId: string) => {
  const container = contentRef.value
  if (!container) return
  const el = container.querySelector(`#${CSS.escape(anchorId)}`)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

const handleOutlineScroll = () => {
  const container = contentRef.value
  if (!container) return
  const headingEls = container.querySelectorAll<HTMLElement>('h1, h2, h3, h4, h5, h6')
  const containerTop = container.getBoundingClientRect().top
  let current = ''
  for (const el of headingEls) {
    if (el.getBoundingClientRect().top - containerTop <= 80) {
      current = el.id
    }
  }
  activeHeading.value = current
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="show" class="md-modal-overlay" @click.self="$emit('close')">
        <div class="md-modal-container" :class="{ 'md-dark': isDark }">
          <!-- Toolbar -->
          <div class="md-toolbar">
            <!-- File name -->
            <div class="md-toolbar-section md-file-name">
              <span class="md-icon">📝</span>
              <span class="truncate">{{ filePath }}</span>
            </div>

            <!-- Actions -->
            <div class="md-toolbar-section">
              <button
                @click="copyMarkdown"
                class="md-toolbar-btn"
                title="Copy markdown content"
              >
                📋
              </button>
            </div>

            <!-- Close button -->
            <button
              @click="$emit('close')"
              class="md-close-btn"
              title="Close (ESC)"
            >
              ✕
            </button>
          </div>

          <!-- Markdown viewer -->
          <div class="md-viewer" :class="{ 'has-outline': headings.length > 0 }">
            <!-- Outline sidebar -->
            <div v-if="headings.length > 0" class="md-outline" :class="{ 'md-dark': isDark }">
              <div class="md-outline-title">大纲</div>
              <div class="md-outline-items">
                <div
                  v-for="h in headings"
                  :key="h.anchorId"
                  class="md-outline-item"
                  :class="{
                    'is-active': activeHeading === h.anchorId,
                    [`level-${h.level}`]: true
                  }"
                  :style="{ paddingLeft: 12 + (h.level - 1) * 14 + 'px' }"
                  @click="scrollToHeading(h.anchorId)"
                >{{ h.text }}</div>
              </div>
            </div>
            <!-- Scrollable content -->
            <div class="md-scroll-content" ref="contentRef" @scroll="handleOutlineScroll">
              <div
                class="md-content"
                :class="{ 'md-dark': isDark }"
                v-html="renderedMarkdown"
              ></div>
            </div>
          </div>
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
  background-color: rgb(255 255 255);
}

.md-modal-container .md-dark {
  background-color: rgb(17 24 39); /* gray-900 */
  color: rgb(229 231 235); /* gray-200 */
}

/* Toolbar */
.md-toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background-color: rgb(243 244 246); /* gray-100 */
  border-bottom: 1px solid rgb(229 231 235); /* gray-200 */
}

.md-dark .md-toolbar {
  background-color: rgb(31 41 55); /* gray-800 */
  border-bottom-color: rgb(55 65 81); /* gray-700 */
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
  color: rgb(55 65 81); /* gray-700 */
  font-size: 0.875rem;
}

.md-dark .md-file-name span {
  color: rgb(209 213 219); /* gray-300 */
}

.md-icon {
  flex-shrink: 0;
}

.md-toolbar-btn {
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
  transition: all 0.15s ease;
}

.md-dark .md-toolbar-btn {
  background-color: rgb(55 65 81); /* gray-700 */
  color: rgb(209 213 219); /* gray-300 */
  border-color: rgb(75 85 99); /* gray-600 */
}

@media (hover: hover) {
  .md-toolbar-btn:hover {
    background-color: rgb(243 244 246); /* gray-100 */
  }
  .md-dark .md-toolbar-btn:hover {
    background-color: rgb(75 85 99); /* gray-600 */
    color: rgb(255 255 255);
  }
}

.md-close-btn {
  margin-left: auto;
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

.md-dark .md-close-btn {
  background-color: rgb(55 65 81); /* gray-700 */
  color: rgb(209 213 219); /* gray-300 */
  border-color: rgb(75 85 99); /* gray-600 */
}

@media (hover: hover) {
  .md-close-btn:hover {
    background-color: rgb(220 38 38); /* red-600 */
    color: rgb(255 255 255);
    border-color: rgb(220 38 38);
  }
  .md-dark .md-close-btn:hover {
    background-color: rgb(220 38 38); /* red-600 */
    color: rgb(255 255 255);
    border-color: rgb(220 38 38);
  }
}

/* Markdown Viewer */
.md-viewer {
  flex: 1;
  display: flex;
  flex-direction: row;
  overflow: hidden;
  background-color: rgb(255 255 255);
}

.md-dark .md-viewer {
  background-color: rgb(17 24 39); /* gray-900 */
}

/* Outline sidebar */
.md-outline {
  width: 220px;
  min-width: 220px;
  border-right: 1px solid rgb(229 231 235); /* gray-200 */
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.md-dark .md-outline {
  border-right-color: rgb(55 65 81); /* gray-700 */
}

.md-outline-title {
  padding: 12px 16px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgb(156 163 175); /* gray-400 */
  border-bottom: 1px solid rgb(229 231 235); /* gray-200 */
}

.md-dark .md-outline-title {
  color: rgb(107 114 128); /* gray-500 */
  border-bottom-color: rgb(55 65 81); /* gray-700 */
}

.md-outline-items {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.md-outline-item {
  padding: 4px 12px;
  font-size: 0.8125rem;
  line-height: 1.5;
  color: rgb(107 114 128); /* gray-500 */
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  border-left: 2px solid transparent;
  transition: all 0.12s ease;
}

.md-dark .md-outline-item {
  color: rgb(156 163 175); /* gray-400 */
}

@media (hover: hover) {
  .md-outline-item:hover {
    color: rgb(31 41 55); /* gray-800 */
    background-color: rgb(243 244 246); /* gray-100 */
  }
  .md-dark .md-outline-item:hover {
    color: rgb(229 231 235); /* gray-200 */
    background-color: rgb(31 41 55); /* gray-800 */
  }
}

.md-outline-item.level-1 {
  font-weight: 600;
}

.md-outline-item.is-active {
  color: rgb(59 130 246); /* blue-500 */
  background-color: rgb(239 246 255); /* blue-50 */
  border-left-color: rgb(59 130 246); /* blue-500 */
}

.md-dark .md-outline-item.is-active {
  color: rgb(96 165 250); /* blue-400 */
  background-color: rgb(30 58 138 / 0.3); /* blue-900/30 */
  border-left-color: rgb(96 165 250); /* blue-400 */
}

/* Scrollable content area */
.md-scroll-content {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
}

.md-content {
  max-width: 800px;
  margin: 0 auto;
  line-height: 1.8;
  color: rgb(31 41 55); /* gray-800 */
}

.md-dark .md-content {
  color: rgb(209 213 219); /* gray-300 */
}

.md-content :deep(h1),
.md-content :deep(h2),
.md-content :deep(h3),
.md-content :deep(h4),
.md-content :deep(h5),
.md-content :deep(h6) {
  margin-top: 1.5em;
  margin-bottom: 0.5em;
  font-weight: 600;
  line-height: 1.3;
  color: rgb(17 24 39); /* gray-900 */
}

.md-dark .md-content :deep(h1),
.md-dark .md-content :deep(h2),
.md-dark .md-content :deep(h3),
.md-dark .md-content :deep(h4),
.md-dark .md-content :deep(h5),
.md-dark .md-content :deep(h6) {
  color: rgb(229 231 235); /* gray-200 */
}

.md-content :deep(h1) {
  font-size: 2.25rem;
  border-bottom: 1px solid;
  padding-bottom: 0.3em;
}

.md-dark .md-content :deep(h1) {
  border-bottom-color: rgb(75 85 99); /* gray-600 */
}

.md-content :deep(h2) {
  font-size: 1.875rem;
  border-bottom: 1px solid;
  padding-bottom: 0.3em;
}

.md-dark .md-content :deep(h2) {
  border-bottom-color: rgb(75 85 99); /* gray-600 */
}

.md-content :deep(h3) {
  font-size: 1.5rem;
}

.md-content :deep(h4) {
  font-size: 1.25rem;
}

.md-content :deep(strong),
.md-content :deep(b) {
  color: rgb(17 24 39); /* gray-900 */
  font-weight: 700;
}

.md-dark .md-content :deep(strong),
.md-dark .md-content :deep(b) {
  color: rgb(255 255 255);
  font-weight: 700;
}

.md-content :deep(em),
.md-content :deep(i) {
  color: rgb(31 41 55); /* gray-800 */
  font-style: italic;
}

.md-dark .md-content :deep(em),
.md-dark .md-content :deep(i) {
  color: rgb(209 213 219); /* gray-300 */
  font-style: italic;
}

.md-content :deep(p) {
  margin: 0 0 1em;
  color: rgb(31 41 55); /* gray-800 */
}

.md-dark .md-content :deep(p) {
  color: rgb(209 213 219); /* gray-300 */
}

.md-content :deep(a) {
  color: rgb(59 130 246); /* blue-500 */
  text-decoration: underline;
}

.md-content :deep(a:hover) {
  color: rgb(37 99 235); /* blue-600 */
}

.md-content :deep(code) {
  padding: 0.2em 0.4em;
  background-color: rgb(243 244 246); /* gray-100 */
  border-radius: 0.25rem;
  font-family: ui-monospace, monospace;
  font-size: 0.875em;
}

.md-dark .md-content :deep(code) {
  background-color: rgb(55 65 81); /* gray-700 */
}

.md-content :deep(pre) {
  margin: 1em 0;
  padding: 1em;
  overflow-x: auto;
  background-color: rgb(243 244 246); /* gray-100 */
  border-radius: 0.375rem;
}

.md-dark .md-content :deep(pre) {
  background-color: rgb(31 41 55); /* gray-800 */
}

.md-content :deep(pre code) {
  padding: 0;
  background-color: transparent !important;
}

.md-content :deep(blockquote) {
  margin: 1em 0;
  padding: 0.5em 1em;
  border-left: 4px solid rgb(156 163 175); /* gray-400 */
  background-color: rgb(243 244 246); /* gray-100 */
  color: rgb(75 85 99); /* gray-600 */
}

.md-dark .md-content :deep(blockquote) {
  border-left-color: rgb(75 85 99); /* gray-600 */
  background-color: rgb(31 41 55); /* gray-800 */
  color: rgb(156 163 175); /* gray-400 */
}

.md-content :deep(ul),
.md-content :deep(ol) {
  margin: 1em 0;
  padding-left: 2em;
}

.md-content :deep(li) {
  margin: 0.25em 0;
  color: rgb(31 41 55); /* gray-800 */
}

.md-dark .md-content :deep(li) {
  color: rgb(209 213 219); /* gray-300 */
}

.md-content :deep(table) {
  margin: 1em 0;
  border-collapse: collapse;
  width: 100%;
}

.md-content :deep(th),
.md-content :deep(td) {
  padding: 0.5em 1em;
  border: 1px solid rgb(229 231 235); /* gray-200 */
}

.md-dark .md-content :deep(th),
.md-dark .md-content :deep(td) {
  border-color: rgb(75 85 99); /* gray-600 */
}

.md-content :deep(th) {
  background-color: rgb(243 244 246); /* gray-100 */
  font-weight: 600;
  color: rgb(17 24 39); /* gray-900 */
}

.md-dark .md-content :deep(th) {
  background-color: rgb(31 41 55); /* gray-800 */
  color: rgb(229 231 235); /* gray-200 */
}

.md-content :deep(td) {
  color: rgb(31 41 55); /* gray-800 */
}

.md-dark .md-content :deep(td) {
  color: rgb(209 213 219); /* gray-300 */
}

.md-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 0.375rem;
}

.md-content :deep(hr) {
  margin: 2em 0;
  border: none;
  border-top: 1px solid rgb(229 231 235); /* gray-200 */
}

.md-dark .md-content :deep(hr) {
  border-top-color: rgb(75 85 99); /* gray-600 */
}

/* Highlight.js styles */
.md-content :deep(.hljs) {
  background-color: rgb(243 244 246); /* gray-100 */
  color: rgb(31 41 55); /* gray-800 */
  padding: 1em;
  border-radius: 0.375rem;
  overflow-x: auto;
}

.md-dark .md-content :deep(.hljs) {
  background-color: rgb(31 41 55); /* gray-800 */
  color: rgb(229 231 235); /* gray-200 */
}

.md-content :deep(.hljs-keyword),
.md-content :deep(.hljs-built_in) {
  color: rgb(244 114 182); /* pink-400 */
}

.md-content :deep(.hljs-string),
.md-content :deep(.hljs-title) {
  color: rgb(163 230 53); /* green-400 */
}

.md-content :deep(.hljs-comment),
.md-content :deep(.hljs-meta) {
  color: rgb(107 114 128); /* gray-500 */
}

.md-content :deep(.hljs-number) {
  color: rgb(250 204 21); /* yellow-400 */
}

.md-content :deep(.hljs-function) {
  color: rgb(147 197 253); /* blue-400 */
}

.md-content :deep(.hljs-variable) {
  color: rgb(248 113 113); /* red-400 */
}

/* Mermaid diagram styles */
.md-content :deep(.mermaid) {
  margin: 1em 0;
  text-align: center;
  overflow-x: auto;
}

.md-content :deep(.mermaid svg) {
  max-width: 100%;
  height: auto;
}

/* Empty and error states */
.md-content :deep(.md-empty),
.md-content :deep(.md-error) {
  padding: 2rem;
  text-align: center;
  color: rgb(107 114 128); /* gray-500 */
}

.md-content :deep(.md-error) {
  color: rgb(248 113 113); /* red-400 */
}

/* Truncate text */
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

/* Mobile responsive */
@media (max-width: 768px) {
  .md-toolbar {
    gap: 0.5rem;
    padding: 0.5rem;
  }

  .md-file-name {
    max-width: 150px;
    min-width: 100px;
  }

  .md-toolbar-btn {
    width: 1.75rem;
    height: 1.75rem;
    font-size: 0.875rem;
  }

  .md-viewer {
    flex-direction: column;
  }

  .md-outline {
    width: 100%;
    min-width: unset;
    max-height: 160px;
    border-right: none;
    border-bottom: 1px solid rgb(229 231 235); /* gray-200 */
  }

  .md-dark .md-outline {
    border-bottom-color: rgb(55 65 81); /* gray-700 */
  }

  .md-scroll-content {
    padding: 1rem;
  }

  .md-content :deep(h1) {
    font-size: 1.75rem;
  }

  .md-content :deep(h2) {
    font-size: 1.5rem;
  }

  .md-content :deep(h3) {
    font-size: 1.25rem;
  }
}
</style>
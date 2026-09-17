<script setup lang="ts">
/**
 * Pure markdown -> HTML renderer.
 *
 * Deliberately stateless: it owns no scrolling, no outline and no mermaid
 * scheduling, so it can be dropped into a modal, a split pane or a preview.
 * Colours come from the theme CSS variables in main.css, so all four themes
 * (light/dark/green/parchment) are correct without a per-component switch.
 */
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { installHeadingAnchors } from '@/utils/markdownHeadings'

interface Props {
  content: string
}

const props = defineProps<Props>()

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

installHeadingAnchors(md)

const renderedMarkdown = computed(() => {
  if (!props.content) return '<p class="md-empty">No content</p>'
  try {
    return md.render(props.content)
  } catch (e) {
    return `<p class="md-error">Failed to render markdown: ${e}</p>`
  }
})
</script>

<template>
  <div class="md-content" v-html="renderedMarkdown"></div>
</template>

<style scoped>
.md-content {
  max-width: 800px;
  margin: 0 auto;
  line-height: 1.8;
  color: var(--text-primary);
  overflow-wrap: break-word;
  word-break: break-word;
}

@media (max-width: 768px) {
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
  color: var(--text-primary);
}

.md-content :deep(h1) {
  font-size: 2.25rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0.3em;
}

.md-content :deep(h2) {
  font-size: 1.875rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0.3em;
}

.md-content :deep(h3) {
  font-size: 1.5rem;
}

.md-content :deep(h4) {
  font-size: 1.25rem;
}

.md-content :deep(strong),
.md-content :deep(b) {
  color: var(--text-primary);
  font-weight: 700;
}

.md-content :deep(em),
.md-content :deep(i) {
  color: var(--text-primary);
  font-style: italic;
}

.md-content :deep(p) {
  margin: 0 0 1em;
  color: var(--text-primary);
}

.md-content :deep(a) {
  color: var(--accent-color);
  text-decoration: underline;
}

.md-content :deep(a:hover) {
  color: var(--accent-hover);
}

.md-content :deep(code) {
  padding: 0.2em 0.4em;
  background-color: var(--bg-secondary);
  border-radius: 0.25rem;
  font-family: ui-monospace, monospace;
  font-size: 0.875em;
}

.md-content :deep(pre) {
  margin: 1em 0;
  padding: 1em;
  overflow-x: auto;
  background-color: var(--bg-secondary);
  border-radius: 0.375rem;
}

.md-content :deep(pre code) {
  padding: 0;
  background-color: transparent !important;
}

.md-content :deep(blockquote) {
  margin: 1em 0;
  padding: 0.5em 1em;
  border-left: 4px solid var(--border-secondary);
  background-color: var(--bg-secondary);
  color: var(--text-secondary);
}

.md-content :deep(ul),
.md-content :deep(ol) {
  margin: 1em 0;
  padding-left: 2em;
}

.md-content :deep(li) {
  margin: 0.25em 0;
  color: var(--text-primary);
}

.md-content :deep(table) {
  margin: 1em 0;
  border-collapse: collapse;
  width: 100%;
}

.md-content :deep(th),
.md-content :deep(td) {
  padding: 0.5em 1em;
  border: 1px solid var(--border-color);
}

.md-content :deep(th) {
  background-color: var(--bg-secondary);
  font-weight: 600;
  color: var(--text-primary);
}

.md-content :deep(td) {
  color: var(--text-primary);
}

.md-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 0.375rem;
}

.md-content :deep(hr) {
  margin: 2em 0;
  border: none;
  border-top: 1px solid var(--border-color);
}

/* Highlight.js styles.
   Syntax tokens need two palettes: the saturated 400-level colours that read
   well on a dark background wash out on the light/green/parchment ones. */
.md-content {
  --md-code-keyword: #c026d3; /* fuchsia-600 */
  --md-code-string: #4d7c0f; /* lime-700 */
  --md-code-number: #a16207; /* yellow-700 */
  --md-code-function: #1d4ed8; /* blue-700 */
  --md-code-variable: #b91c1c; /* red-700 */
}

:global(.theme-dark) .md-content {
  --md-code-keyword: #f472b6; /* pink-400 */
  --md-code-string: #a3e635; /* green-400 */
  --md-code-number: #facc15; /* yellow-400 */
  --md-code-function: #93c5fd; /* blue-400 */
  --md-code-variable: #f87171; /* red-400 */
}

.md-content :deep(.hljs) {
  background-color: var(--bg-secondary);
  color: var(--text-primary);
  padding: 1em;
  border-radius: 0.375rem;
  overflow-x: auto;
}

.md-content :deep(.hljs-keyword),
.md-content :deep(.hljs-built_in) {
  color: var(--md-code-keyword);
}

.md-content :deep(.hljs-string),
.md-content :deep(.hljs-title) {
  color: var(--md-code-string);
}

.md-content :deep(.hljs-comment),
.md-content :deep(.hljs-meta) {
  color: var(--text-muted);
}

.md-content :deep(.hljs-number) {
  color: var(--md-code-number);
}

.md-content :deep(.hljs-function) {
  color: var(--md-code-function);
}

.md-content :deep(.hljs-variable) {
  color: var(--md-code-variable);
}

/* Mermaid diagrams */
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
  color: var(--text-muted);
}

.md-content :deep(.md-error) {
  color: #dc2626;
}
</style>

<script setup lang="ts">
/**
 * Scrollable markdown preview: outline sidebar + rendered body + mermaid.
 *
 * Used both inside the full-screen modal and as the notebook's preview pane.
 * The outline and mermaid scheduling live here rather than in MarkdownRenderer
 * because they depend on a scrolling container, which the renderer deliberately
 * does not have.
 */
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
import { extractHeadings } from '@/utils/markdownHeadings'
import { useTheme } from '@/composables/useTheme'

interface Props {
  content: string
  showOutline?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showOutline: true
})

const { isDark } = useTheme()

const contentRef = ref<HTMLElement>()
const mermaidRef = ref<any>(null)
const activeHeading = ref<string>('')

const headings = computed(() => extractHeadings(props.content))

// -- mermaid ---------------------------------------------------------------

// Live preview re-renders on every keystroke, so mermaid runs behind a short
// debounce rather than once per character.
const MERMAID_DEBOUNCE_MS = 200
let mermaidTimer: ReturnType<typeof setTimeout> | null = null

const initMermaid = async () => {
  try {
    const module = await import('mermaid')
    mermaidRef.value = module.default
    mermaidRef.value.initialize({
      startOnLoad: false,
      theme: isDark.value ? 'dark' : 'default',
      securityLevel: 'loose'
    })
  } catch (e) {
    console.error('Failed to load mermaid:', e)
  }
}

/** Wait until the pane has a real box, or give up after ~10 frames. */
const waitForLayout = async (): Promise<boolean> => {
  for (let frame = 0; frame < 10; frame++) {
    await new Promise((resolve) => requestAnimationFrame(resolve))
    const element = contentRef.value
    if (element && element.offsetWidth > 0 && element.offsetHeight > 0) return true
  }
  return false
}

// Mermaid mutates the nodes in place, so two overlapping runs corrupt each
// other. Runs are serialised and a request arriving mid-run is coalesced into
// a single follow-up.
let mermaidInFlight = false
let mermaidQueued = false

// mermaid.run() cannot be cancelled. A run started shortly before this pane is
// destroyed (mode switch, note switch) finishes against detached nodes and
// throws inside mermaid's layout code. That is teardown noise rather than a
// rendering failure - the replacement pane renders from scratch - so errors
// raised after unmount are dropped instead of logged.
let mounted = true

const runMermaid = async (): Promise<void> => {
  if (!mermaidRef.value || mermaidInFlight) {
    if (mermaidInFlight) mermaidQueued = true
    return
  }
  mermaidInFlight = true
  try {
    await nextTick()
    const element = contentRef.value
    if (!element) return

    // Mermaid measures label text with getBBox, which throws when the pane has
    // not been laid out yet (mode switch, first paint after a note switch).
    if (element.offsetWidth === 0 || element.offsetHeight === 0) {
      if (!(await waitForLayout())) return
    }

    const elements = element.querySelectorAll('.mermaid')
    if (elements.length === 0) return
    await mermaidRef.value.run({ nodes: [...elements] })
  } catch (e) {
    if (mounted) console.error('Mermaid render error:', e)
  } finally {
    mermaidInFlight = false
    if (mermaidQueued) {
      mermaidQueued = false
      void runMermaid()
    }
  }
}

const scheduleMermaid = () => {
  if (mermaidTimer) clearTimeout(mermaidTimer)
  mermaidTimer = setTimeout(() => {
    mermaidTimer = null
    void runMermaid()
  }, MERMAID_DEBOUNCE_MS)
}

watch(() => props.content, scheduleMermaid)

watch(isDark, async (dark) => {
  if (!mermaidRef.value) return
  mermaidRef.value.initialize({
    startOnLoad: false,
    theme: dark ? 'dark' : 'default',
    securityLevel: 'loose'
  })
  await runMermaid()
})

onMounted(async () => {
  await initMermaid()
  await runMermaid()
})

onUnmounted(() => {
  mounted = false
  mermaidQueued = false
  if (mermaidTimer) clearTimeout(mermaidTimer)
})

// -- outline ---------------------------------------------------------------

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

defineExpose({ scrollToHeading })
</script>

<template>
  <div class="md-pane" :class="{ 'has-outline': showOutline && headings.length > 0 }">
    <div v-if="showOutline && headings.length > 0" class="md-outline">
      <div class="md-outline-title">Outline</div>
      <div class="md-outline-items">
        <div
          v-for="h in headings"
          :key="h.anchorId"
          class="md-outline-item"
          :class="{ 'is-active': activeHeading === h.anchorId, [`level-${h.level}`]: true }"
          :style="{ paddingLeft: 12 + (h.level - 1) * 14 + 'px' }"
          @click="scrollToHeading(h.anchorId)"
        >{{ h.text }}</div>
      </div>
    </div>

    <div ref="contentRef" class="md-scroll-content" @scroll="handleOutlineScroll">
      <MarkdownRenderer :content="content" />
    </div>
  </div>
</template>

<style scoped>
.md-pane {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: row;
  overflow: hidden;
  background-color: var(--bg-primary);
}

.md-outline {
  width: 220px;
  min-width: 220px;
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.md-outline-title {
  padding: 12px 16px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-color);
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
  color: var(--text-secondary);
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  border-left: 2px solid transparent;
  transition: all 0.12s ease;
}

@media (hover: hover) {
  .md-outline-item:hover {
    color: var(--text-primary);
    background-color: var(--bg-secondary);
  }
}

.md-outline-item.level-1 {
  font-weight: 600;
}

.md-outline-item.is-active {
  color: var(--accent-color);
  background-color: color-mix(in srgb, var(--accent-color) 12%, transparent);
  border-left-color: var(--accent-color);
}

.md-scroll-content {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 2rem;
}

/* Narrow containers drop the outline above the content instead of beside it. */
@media (max-width: 768px) {
  .md-pane {
    flex-direction: column;
  }

  .md-outline {
    width: 100%;
    min-width: unset;
    max-height: 160px;
    border-right: none;
    border-bottom: 1px solid var(--border-color);
  }

  .md-scroll-content {
    padding: 1rem;
  }
}
</style>

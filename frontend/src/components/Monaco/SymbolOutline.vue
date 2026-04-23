<!-- frontend/src/components/Monaco/SymbolOutline.vue -->
<script setup lang="ts">
import { ref, watch, computed, onUnmounted } from 'vue'
import type { SymbolInfo } from '@/composables/useSymbolOutline'
import { symbolsApi, type IndexResponse, type SymbolDefinitionResponse, type SymbolMatchItem } from '@/api/symbols'
import { isLanMode } from '@/api/client'

interface Props {
  symbols: SymbolInfo[]
  collapsed: boolean
  previewCollapsed: boolean
  taskId?: string
  currentFilePath?: string
}

interface Emits {
  (e: 'select', symbol: SymbolInfo): void
  (e: 'toggle'): void
  (e: 'previewToggle'): void
  (e: 'navigate', filePath: string, lineNumber: number): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const currentIndex = ref(-1)

// Indexing state
const isIndexing = ref(false)
const indexStatus = ref<IndexResponse | null>(null)
const indexError = ref<string | null>(null)

// Preview state
const previewSymbol = ref<SymbolInfo | null>(null)
const previewData = ref<SymbolDefinitionResponse | null>(null)
const previewLoading = ref(false)
const previewError = ref<string | null>(null)
const currentMatchKey = ref<string | null>(null)
const locationsExpanded = ref(false)

// Polling for index status
let pollInterval: ReturnType<typeof setInterval> | null = null

// Reset index when symbols change
watch(() => props.symbols, () => {
  currentIndex.value = -1
})

// Cleanup polling on unmount
onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
})

function handleSymbolClick(symbol: SymbolInfo, index: number) {
  currentIndex.value = index
  emit('select', symbol)
  loadPreview(symbol)
}

function handleToggle() {
  emit('toggle')
}

function handleNext() {
  if (props.symbols.length === 0) return
  currentIndex.value = (currentIndex.value + 1) % props.symbols.length
  emit('select', props.symbols[currentIndex.value])
}

async function handleIndexClick() {
  if (!props.taskId) return

  indexError.value = null
  isIndexing.value = true

  try {
    const response = await symbolsApi.startIndexJob(props.taskId, false)
    indexStatus.value = response

    if (response.cached) {
      // Already indexed
      isIndexing.value = false
      return
    }

    if (response.status === 'failed') {
      indexError.value = response.error || 'Indexing failed'
      isIndexing.value = false
      return
    }

    // Start polling for status
    pollInterval = setInterval(async () => {
      if (!isLanMode()) return  // 非局域网跳过本次轮询
      try {
        const status = await symbolsApi.getIndexStatus(response.job_id)
        indexStatus.value = status

        if (status.status === 'completed' || status.status === 'failed') {
          if (pollInterval) {
            clearInterval(pollInterval)
            pollInterval = null
          }
          isIndexing.value = false
          if (status.status === 'failed') {
            indexError.value = status.error || 'Indexing failed'
          }
        }
      } catch (e) {
        console.error('Failed to poll index status:', e)
      }
    }, 2000)
  } catch (e) {
    indexError.value = e instanceof Error ? e.message : 'Failed to start indexing'
    isIndexing.value = false
  }
}

async function loadPreview(symbol: SymbolInfo) {
  // Skip API call if preview panel is collapsed
  if (props.previewCollapsed) {
    return
  }

  if (!props.taskId) {
    previewData.value = {
      found: false,
      reason: 'no_task',
      message: 'No task selected'
    }
    return
  }

  previewSymbol.value = symbol
  previewLoading.value = true
  previewError.value = null
  previewData.value = null
  currentMatchKey.value = null

  try {
    const response = await symbolsApi.getSymbolDefinition(
      symbol.name,
      props.currentFilePath || '',
      props.taskId
    )
    previewData.value = response
    // Set current match key to the main symbol's location
    if (response.found && response.file_path && response.line_number) {
      currentMatchKey.value = getMatchKey(response.file_path, response.line_number)
    }
  } catch (e) {
    previewError.value = e instanceof Error ? e.message : 'Failed to load preview'
  } finally {
    previewLoading.value = false
  }
}

async function handleLoadMatchPreview(match: SymbolMatchItem) {
  // Skip API call if preview panel is collapsed
  if (props.previewCollapsed) return
  if (!props.taskId) return

  // Set current match key before loading
  currentMatchKey.value = getMatchKey(match.file_path, match.line_number)

  previewLoading.value = true
  try {
    // Use the new getSymbolDetail API to get exact symbol at that location
    const response = await symbolsApi.getSymbolDetail(
      match.file_path,
      match.line_number,
      props.taskId
    )
    previewData.value = response
  } catch (e) {
    previewError.value = e instanceof Error ? e.message : 'Failed to load preview'
  } finally {
    previewLoading.value = false
  }
}

function getSymbolClass(kind: SymbolInfo['kind']): string {
  return `symbol-${kind}`
}

function getSymbolIcon(kind: SymbolInfo['kind']): string {
  switch (kind) {
    case 'function': return 'ƒ'
    case 'class': return '◼'
    case 'variable': return 'v'
    case 'import': return '📥'
    case 'constant': return 'C'
    default: return '•'
  }
}

function formatFilePath(filePath: string): string {
  // Show only the last 2-3 path segments
  const parts = filePath.split('/')
  if (parts.length <= 3) return filePath
  return '.../' + parts.slice(-3).join('/')
}

function isFunctionKind(kind: string | undefined): boolean {
  return kind === 'function' || kind === 'method'
}

function getMatchKey(filePath: string, lineNumber: number): string {
  return `${filePath}:${lineNumber}`
}

function isCurrentMatch(match: SymbolMatchItem): boolean {
  return currentMatchKey.value === getMatchKey(match.file_path, match.line_number)
}

const indexButtonText = computed(() => {
  if (isIndexing.value && indexStatus.value?.progress) {
    const { files_scanned } = indexStatus.value.progress
    return `${files_scanned} files`
  }
  return 'Index'
})

const indexButtonTitle = computed(() => {
  if (isIndexing.value) {
    return 'Indexing in progress...'
  }
  if (indexStatus.value?.cached) {
    return `Indexed: ${indexStatus.value.indexed_files} files, ${indexStatus.value.indexed_symbols} symbols`
  }
  return 'Index project for symbol preview'
})

// Expose method for external preview loading (e.g., from MonacoEditor cursor events)
defineExpose({
  loadPreviewBySymbolName: (symbolName: string) => {
    loadPreview({ name: symbolName, kind: 'variable', lineNumber: 0 })
  }
})
</script>

<template>
  <div class="symbol-outline-container">
    <!-- SYMBOLS Panel -->
    <div class="symbol-outline" :class="{ 'is-collapsed': collapsed }">
      <!-- Header -->
      <div class="outline-header" @click="handleToggle">
        <span class="outline-toggle">{{ collapsed ? '▶' : '▼' }}</span>
        <span class="outline-title">SYMBOLS</span>
        <span v-if="symbols.length > 0" class="outline-count">({{ symbols.length }})</span>
        <button
          v-if="symbols.length > 0"
          class="outline-next"
          @click.stop="handleNext"
          title="Go to next symbol"
        >
          ↓
        </button>
      </div>

      <!-- Content -->
      <div v-if="!collapsed" class="outline-content">
        <!-- Index error -->
        <div v-if="indexError" class="index-error">
          {{ indexError }}
          <button @click="indexError = null" class="error-dismiss">×</button>
        </div>

        <!-- Symbol list -->
        <div v-if="symbols.length === 0" class="no-symbols">
          No symbols found
        </div>
        <div v-else class="symbol-tags">
          <button
            v-for="(symbol, index) in symbols"
            :key="`${symbol.kind}-${symbol.name}-${index}`"
            class="symbol-tag"
            :class="[getSymbolClass(symbol.kind), { 'is-active': index === currentIndex }]"
            @click="handleSymbolClick(symbol, index)"
            :title="`${symbol.name} (line ${symbol.lineNumber})`"
          >
            <span class="symbol-icon">{{ getSymbolIcon(symbol.kind) }}</span>
            <span class="symbol-name">{{ symbol.name }}</span>
            <span class="symbol-line">{{ symbol.lineNumber }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Preview Panel (sibling to SYMBOLS) - always visible -->
    <div class="preview-panel" :class="{ 'is-collapsed': previewCollapsed }">
      <div class="preview-header" @click="emit('previewToggle')">
        <span class="preview-toggle">{{ previewCollapsed ? '▶' : '▼' }}</span>
        <span class="preview-title">Symbol Preview</span>
        <span v-if="previewSymbol" class="preview-name">{{ previewSymbol.name }}</span>
        <button
          v-if="taskId"
          class="outline-index"
          :class="{ 'is-indexing': isIndexing }"
          @click.stop="handleIndexClick"
          :disabled="isIndexing"
          :title="indexButtonTitle"
        >
          {{ indexButtonText }}
        </button>
      </div>

      <div v-if="!previewCollapsed" class="preview-content">
        <!-- No symbol selected -->
        <div v-if="!previewSymbol && !previewLoading" class="preview-empty">
          Select a symbol to preview
        </div>

        <!-- Loading state -->
        <div v-else-if="previewLoading" class="preview-loading">
          Loading...
        </div>

        <!-- Error state -->
        <div v-else-if="previewError" class="preview-error">
          {{ previewError }}
        </div>

        <!-- Not indexed -->
        <div v-else-if="previewData?.reason === 'not_indexed'" class="preview-not-indexed">
          {{ previewData.message }}
        </div>

        <!-- Not found -->
        <div v-else-if="previewData?.found === false" class="preview-not-found">
          <span>Symbol not found</span>
          <div v-if="previewData.similar_symbols?.length" class="similar-symbols">
            <span>Similar:</span>
            <button
              v-for="name in previewData.similar_symbols"
              :key="name"
              class="similar-btn"
              @click="loadPreview({ name, kind: 'variable', lineNumber: 0 })"
            >
              {{ name }}
            </button>
          </div>
        </div>

        <!-- Single match - show details (handles all cases now) -->
        <template v-else-if="previewData?.found">
          <!-- All matches section - MOVED TO TOP with collapse -->
          <div v-if="previewData?.matches?.length" class="preview-all-matches">
            <div class="matches-list-compact" :class="{ 'is-collapsed': !locationsExpanded && previewData.matches.length > 2 }">
              <button
                v-for="match in previewData.matches"
                :key="`${match.file_path}-${match.line_number}`"
                class="match-compact-btn"
                :class="{ 'is-current': isCurrentMatch(match) }"
                :title="`${match.kind} - ${match.file_path}:${match.line_number}`"
                @click="handleLoadMatchPreview(match)"
              >
                <span class="match-kind-small">{{ match.kind }}</span>
                <span class="match-file-small">{{ formatFilePath(match.file_path) }}:{{ match.line_number }}</span>
              </button>
            </div>
            <button
              v-if="previewData.matches.length > 2"
              class="matches-expand-btn"
              @click="locationsExpanded = !locationsExpanded"
            >
              {{ locationsExpanded ? 'Show less' : `Show all ${previewData.matches.length}` }}
            </button>
          </div>

          <!-- Definition snippet - for functions: comments + full body; for others: context snippet -->
          <div v-if="previewData?.definition_snippet?.length" class="preview-snippet" :class="{ 'context-snippet': !isFunctionKind(previewData.kind) }">
            <pre><code
              v-for="(line, idx) in previewData.definition_snippet"
              :key="idx"
              :class="{ 'highlight-line': !isFunctionKind(previewData.kind) && idx === previewData.snippet_highlight_index }"
            >{{ line }}
</code></pre>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Container for both SYMBOLS and PREVIEW panels */
.symbol-outline-container {
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}

.symbol-outline {
  border-top: 1px solid var(--border-color);
  font-size: 12px;
}

.outline-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  user-select: none;
}

@media (hover: hover) {
  .outline-header:hover {
    background: var(--bg-secondary);
  }
}

.outline-toggle {
  font-size: 10px;
  color: var(--text-muted);
  width: 16px;
}

.outline-title {
  color: var(--text-primary);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.outline-count {
  color: var(--text-muted);
  font-size: 11px;
}

.outline-index {
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 3px;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 2px 6px;
  font-size: 11px;
  line-height: 1;
  transition: all 0.15s ease;
  margin-left: 4px;
  touch-action: manipulation;
}

.outline-index:hover:not(:disabled) {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: white;
}

.outline-index.is-indexing {
  opacity: 0.6;
  cursor: wait;
}

.outline-next {
  margin-left: auto;
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 3px;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 2px 6px;
  font-size: 11px;
  line-height: 1;
  transition: all 0.15s ease;
  touch-action: manipulation;
}

@media (hover: hover) {
  .outline-next:hover {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
  }
}

.outline-content {
  padding: 8px 12px;
  height: 140px;
  overflow-y: auto;
}

/* Custom scrollbar for outline content */
.outline-content::-webkit-scrollbar {
  width: 6px;
}

.outline-content::-webkit-scrollbar-track {
  background: transparent;
}

.outline-content::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.outline-content::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

.index-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--conflict-error-bg);
  color: var(--conflict-error-text);
  padding: 4px 8px;
  border-radius: 4px;
  margin-bottom: 8px;
  font-size: 11px;
}

.error-dismiss {
  background: none;
  border: none;
  color: var(--conflict-error-text);
  cursor: pointer;
  font-size: 14px;
  padding: 0 4px;
}

.no-symbols {
  color: var(--text-muted);
  font-style: italic;
  font-size: 11px;
}

.symbol-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.symbol-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 11px;
  transition: background 0.15s ease, border-color 0.15s ease;
  touch-action: manipulation;
}

@media (hover: hover) {
  .symbol-tag:hover {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
  }

  .symbol-tag:hover .symbol-icon,
  .symbol-tag:hover .symbol-name,
  .symbol-tag:hover .symbol-line {
    color: white;
  }
}

.symbol-tag.is-active {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: white;
}

.symbol-tag.is-active .symbol-icon,
.symbol-tag.is-active .symbol-name,
.symbol-tag.is-active .symbol-line {
  color: white;
}

.symbol-icon {
  font-size: 10px;
  opacity: 0.8;
}

.symbol-name {
  font-family: monospace;
  color: var(--text-primary);
}

.symbol-line {
  color: var(--text-muted);
  font-size: 10px;
  margin-left: 2px;
}

/* Preview Panel - now sibling to symbol-outline */
.preview-panel {
  background: var(--bg-primary);
  border-top: 1px solid var(--border-color);
  font-size: 12px;
}

.preview-panel.is-collapsed .preview-content {
  display: none;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  user-select: none;
}

@media (hover: hover) {
  .preview-header:hover {
    background: var(--bg-secondary);
  }
}

.preview-toggle {
  font-size: 10px;
  color: var(--text-muted);
  width: 16px;
}

.preview-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.preview-name {
  font-family: monospace;
  font-size: 11px;
  color: var(--text-primary);
  margin-left: auto;
}

.preview-content {
  padding: 8px 12px;
  height: 250px;
  overflow-y: auto;
}

/* Custom scrollbar for preview content */
.preview-content::-webkit-scrollbar {
  width: 6px;
}

.preview-content::-webkit-scrollbar-track {
  background: transparent;
}

.preview-content::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.preview-content::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

.preview-loading,
.preview-error,
.preview-not-indexed,
.preview-not-found,
.preview-empty {
  color: var(--text-muted);
  font-size: 11px;
  font-style: italic;
}

.preview-error {
  color: var(--conflict-error-text);
}

.similar-symbols {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.similar-btn {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 3px;
  padding: 2px 6px;
  font-size: 10px;
  cursor: pointer;
  font-family: monospace;
}

@media (hover: hover) {
  .similar-btn:hover {
    background: var(--accent-color);
    color: white;
  }
}

/* Preview snippet */
.preview-snippet {
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 8px;
  margin-top: 8px;
  overflow-x: auto;
}

.preview-snippet pre {
  margin: 0;
  font-family: monospace;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-primary);
}

.preview-snippet code {
  background: none;
}

/* Preview snippet scrollbar */
.preview-snippet::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.preview-snippet::-webkit-scrollbar-track {
  background: transparent;
}

.preview-snippet::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.preview-snippet::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

.preview-snippet::-webkit-scrollbar-corner {
  background: transparent;
}

/* Context snippet - distinct styling for non-function symbols */
.preview-snippet.context-snippet {
  border: 1px solid var(--border-color);
  position: relative;
}

/* Context snippet highlight line */
.preview-snippet .highlight-line {
  background: color-mix(in srgb, var(--accent-color) 15%, transparent);
  display: block;
  margin: 0 -8px;
  padding: 0 8px;
  border-radius: 2px;
  border-left: 2px solid var(--accent-color);
  position: relative;
}

/* Preview location */
.preview-location {
  margin-bottom: 8px;
}

.location-text {
  font-size: 11px;
  color: var(--text-secondary);
}

/* All matches section (compact) */
.preview-all-matches {
  margin-bottom: 8px;
}

.matches-list-compact {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.matches-list-compact.is-collapsed {
  max-height: calc(2 * 24px);
  overflow: hidden;
}

.matches-expand-btn {
  display: block;
  margin-top: 4px;
  padding: 0;
  background: transparent;
  border: none;
  font-size: 10px;
  color: var(--text-secondary);
  cursor: pointer;
  text-align: left;
}

@media (hover: hover) {
  .matches-expand-btn:hover {
    color: var(--accent-color);
  }
}

.match-compact-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 3px;
  padding: 2px 6px;
  cursor: pointer;
  font-size: 10px;
  transition: all 0.15s ease;
  touch-action: manipulation;
}

@media (hover: hover) {
  .match-compact-btn:hover {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
  }
}

@media (hover: hover) {
  .match-compact-btn:hover .match-kind-small,
  .match-compact-btn:hover .match-file-small {
    color: white;
  }
}

.match-compact-btn.is-current {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: white;
}

.match-compact-btn.is-current .match-kind-small,
.match-compact-btn.is-current .match-file-small {
  color: white;
}

.match-kind-small {
  font-size: 9px;
  color: var(--text-muted);
  text-transform: uppercase;
}

.match-file-small {
  font-family: monospace;
  font-size: 10px;
  color: var(--text-primary);
}

/* Symbol type colors - theme-aware */
.symbol-function {
  color: var(--symbol-function);
}

.symbol-class {
  color: var(--symbol-class);
}

.symbol-variable {
  color: var(--symbol-variable);
}

.symbol-import {
  color: var(--symbol-import);
}

.symbol-constant {
  color: var(--symbol-constant);
}

.is-collapsed .outline-content {
  display: none;
}
</style>

<style>
/* Theme-specific symbol colors - must be non-scoped to access parent theme class */
/* Dark theme */
.theme-dark .symbol-outline .symbol-function {
  color: #dcdcaa;
}

.theme-dark .symbol-outline .symbol-class {
  color: #4ec9b0;
}

.theme-dark .symbol-outline .symbol-variable {
  color: #9cdcfe;
}

.theme-dark .symbol-outline .symbol-import {
  color: #c586c0;
}

.theme-dark .symbol-outline .symbol-constant {
  color: #ce9178;
}

/* Green theme */
.theme-green .symbol-outline .symbol-function {
  color: #2d5a3d;
}

.theme-green .symbol-outline .symbol-class {
  color: #1a5276;
}

.theme-green .symbol-outline .symbol-variable {
  color: #1e8449;
}

.theme-green .symbol-outline .symbol-import {
  color: #7b1fa2;
}

.theme-green .symbol-outline .symbol-constant {
  color: #bf360c;
}

/* Parchment theme */
.theme-parchment .symbol-outline .symbol-function {
  color: #8b6914;
}

.theme-parchment .symbol-outline .symbol-class {
  color: #1565c0;
}

.theme-parchment .symbol-outline .symbol-variable {
  color: #2e7d32;
}

.theme-parchment .symbol-outline .symbol-import {
  color: #7b1fa2;
}

.theme-parchment .symbol-outline .symbol-constant {
  color: #d84315;
}

/* Light theme */
.theme-light .symbol-outline .symbol-function {
  color: #795e26;
}

.theme-light .symbol-outline .symbol-class {
  color: #267f99;
}

.theme-light .symbol-outline .symbol-variable {
  color: #001080;
}

.theme-light .symbol-outline .symbol-import {
  color: #af00db;
}

.theme-light .symbol-outline .symbol-constant {
  color: #a31515;
}
</style>
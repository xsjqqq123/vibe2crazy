<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted, watch, nextTick, provide, type Ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useTheme } from '@/composables/useTheme'
import { useConfirm } from '@/composables/useConfirm'
import { useMainStore } from '@/store'
import filesApi from '@/api/files'
import tasksApi, { type Task, type TaskStatusType, type CodeStatusType } from '@/api/tasks'
import projectsApi from '@/api/projects'
import { gitApi, type CommitInfo, type PaginatedCommitsResponse } from '@/api/git'
import { type ChangedFileInfo, type PaginatedChangedFilesResponse } from '@/api/files'
import { isLanMode } from '@/api/client'
import FileCacheService from '@/services/FileCacheService'
import { Splitpanes, Pane } from 'splitpanes'
import { useFileTree, provideFileTree } from '@/composables/useFileTree'
import FileTreeItem from '@/components/FileTreeItem.vue'
import ContextMenu from '@/components/ContextMenu.vue'
import MarkdownPreviewModal from '@/components/MarkdownPreviewModal.vue'
import FileQuickJumpModal from '@/components/FileQuickJumpModal.vue'
import type { MenuItem } from '@/components/ContextMenu.vue'
import SymbolOutline from '@/components/Monaco/SymbolOutline.vue'
import ConflictEditor from '@/components/Monaco/ConflictEditor.vue'
import TaskSettingsModal from '@/components/TaskSettingsModal.vue'
import RefererSearch from '@/components/RefererSearch.vue'
import { useSymbolOutline, type SymbolInfo } from '@/composables/useSymbolOutline'
import { detectLanguage, supportsSymbolExtraction } from '@/utils/languageDetection'
import GlobalTerminalIcon from '@/components/GlobalTerminalIcon.vue'
import { closePersistentConnection } from '@/composables/useWebSocket'
import MonacoEditor from '@/components/Monaco/MonacoEditor.vue'
import MonacoDiffEditor from '@/components/Monaco/MonacoDiffEditor.vue'
import Terminal from '@/components/Terminal/Terminal.vue'
import EditorView from '@/components/Monaco/EditorView.vue'
import CommitsList from '@/components/CommitsList.vue'
import CommitDiffView from '@/components/CommitDiffView.vue'
import Pagination from '@/components/Pagination.vue'
import { type HistoryEntry, type EditorViewState } from '@/types/editor'


interface Layout {
  sidebar: number
  filesPane: number      // File tree height
  tabbedPane: number     // Changes/Commits middle pane
  tasksPane: number      // Task list at bottom
  terminalPx: number     // Terminal width in pixels (not percentage)
}

const router = useRouter()
const route = useRoute()
const { theme, cycleTheme } = useTheme()
const { showConfirm } = useConfirm()
const store = useMainStore()

// New computed for projectId from route params
const projectId = computed(() => route.params.id as string)
const taskId = computed(() => route.query.task as string)
const task = computed(() => store.currentTask)

// Task list state (new)
const tasks = ref<Task[]>([])
const tasksLoading = ref(false)
const activeTab = ref<'changes' | 'commits'>('changes')
const activeFilesTab = ref<'files' | 'referer'>('files')

// Referer search state (lifted to preserve across tab switches)
const refererQuery = ref('')
const refererResults = ref<{ file: string; line: number; content: string }[]>([])
const refererTotal = ref(0)
const refererTotalMatches = ref(0)
const refererPage = ref(1)
const refererExpandedFiles = ref<Set<string>>(new Set())

// Changed files
const changedFiles = ref<ChangedFileInfo[]>([])
// Changed files pagination
const changedFilesPage = ref(1)
const changedFilesData = ref<PaginatedChangedFilesResponse | null>(null)
const initialLoading = ref(true)

// Commits
const commits = ref<CommitInfo[]>([])
const loadingCommits = ref(false)
const commitsError = ref('')
const lastCommitsHash = ref<string>('')
const newCommitHashes = ref<Set<string>>(new Set())

// Pagination
const currentPage = ref(1)
const commitsData = ref<PaginatedCommitsResponse | null>(null)

// Context menu
const contextMenu = ref({
  show: false,
  x: 0,
  y: 0,
  path: '',
  type: '',
  source: 'files' as 'files' | 'changedFiles' | 'commits',  // Track which list the menu is from
  commit: null as CommitInfo | null
})

// Commit diff view
const selectedCommitHash = ref<string | null>(null)
const selectedCommitMessage = ref('')
const loadingCommitDiff = ref(false)
const commitDiffError = ref('')

// Check if current file is a markdown file
const isMarkdownFile = computed(() => {
  return currentFile.value?.toLowerCase().endsWith('.md') || false
})
const currentFile = ref<string | null>(null)
const fileContent = ref('')
const originalContent = ref('')
const loadingContent = ref(false)
const savingContent = ref(false)
const saveError = ref('')
const editorMode = ref<'editor' | 'diff' | 'commit-diff' | 'deleted' | 'conflict'>('editor')
const isFileDeleted = ref(false)

// Multi-view editor state (for preview panes)
const mainEditorState = ref<EditorViewState>({
  filePath: null,
  fileContent: '',
  originalContent: '',
  editorMode: 'editor',
  history: [],
  cursorPosition: null,
  scrollPosition: null,
  isFileDeleted: false
})
const preview1State = ref<EditorViewState>({
  filePath: null,
  fileContent: '',
  originalContent: '',
  editorMode: 'editor',
  history: [],
  cursorPosition: null,
  scrollPosition: null,
  isFileDeleted: false
})
const preview2State = ref<EditorViewState>({
  filePath: null,
  fileContent: '',
  originalContent: '',
  editorMode: 'editor',
  history: [],
  cursorPosition: null,
  scrollPosition: null,
  isFileDeleted: false
})

// Layout state for multi-view
const showPreviews = ref(false)  // Combined toggle for both previews
const activeView = ref<'main' | 'preview1' | 'preview2'>('main')
const previewCycle = ref<'preview1' | 'preview2'>('preview1')  // Tracks which preview to use next

// Computed helpers for multi-view (used by subsequent tasks)
const currentPreviewState = computed(() => {
  if (activeView.value === 'preview1') return preview1State.value
  if (activeView.value === 'preview2') return preview2State.value
  return null
})
const hasMainEditorContent = computed(() => {
  return mainEditorState.value.filePath !== null
})

// Watch for preview toggle changes (will sync with terminal visibility in subsequent tasks)
watch(showPreviews, (show) => {
  // Mutual exclusivity: hide terminal when previews are shown
  if (show && !isMobile.value) {
    showTerminal.value = false
  }
  // When previews are hidden, reset preview states
  if (!show) {
    previewCycle.value = 'preview1'
    // Save preview positions before clearing (if file was open)
    if (preview1State.value.filePath && preview1Ref.value) {
      updatePreviewHistoryEntry(preview1State.value, preview1Ref.value)
    }
    if (preview2State.value.filePath && preview2Ref.value) {
      updatePreviewHistoryEntry(preview2State.value, preview2Ref.value)
    }
    // Clear preview content when hiding
    preview1State.value.filePath = null
    preview2State.value.filePath = null
  }
})

// Watch activeView to track focus (will be used for keyboard shortcuts)
watch(activeView, (view) => {
  // Log current preview state for debugging (will be replaced with actual logic)
  if (view !== 'main' && currentPreviewState.value) {
    console.debug('Active preview:', view, currentPreviewState.value.filePath)
  }
  // Also log main editor state when switching back
  if (view === 'main' && hasMainEditorContent.value) {
    console.debug('Main editor active:', mainEditorState.value.filePath)
  }
})

// Watch currentFile to save/restore position using mainEditorState
watch(currentFile, (newFile, oldFile) => {
  // Save position for previous file (update existing history entry)
  if (oldFile && mainEditorState.value.filePath === oldFile) {
    updateHistoryEntry(mainEditorState.value)
  }
  // Update mainEditorState to track current file
  if (newFile) {
    mainEditorState.value.filePath = newFile
    // Find and restore position from history
    const historyEntry = mainEditorState.value.history.find(h => h.filePath === newFile)
    if (historyEntry) {
      restoreEditorPosition(mainEditorState.value, historyEntry)
    } else {
      // New file not in history - add entry with default position
      addHistoryEntry(mainEditorState.value, newFile)
    }
  }
})

// Mobile state
const showFileList = ref(false)
const isMobile = ref(window.innerWidth < 768)

// Terminal - show terminal first on both mobile and desktop
const showTerminal = ref(true)

// Direct on branch banner - hide after 5s or when closed
const hideDirectBranchBanner = ref(false)
let directBranchBannerTimer: ReturnType<typeof setTimeout> | null = null

// Watch for direct_on_branch to start 5s auto-hide timer
watch(() => task.value?.direct_on_branch, (direct) => {
  if (direct) {
    hideDirectBranchBanner.value = false
    if (directBranchBannerTimer) clearTimeout(directBranchBannerTimer)
    directBranchBannerTimer = setTimeout(() => {
      hideDirectBranchBanner.value = true
    }, 5000)
  }
})

// Merge
const mergeError = ref('')
const mergeSuccess = ref(false)
const mergeExecutionLog = ref<any[] | null>(null)  // Store execution log for errors

// Accept
const accepting = ref(false)
const acceptError = ref('')
const createError = ref('')
const showCreateDialog = ref(false)
const newTaskName = ref('')
const newTaskDirectOnBranch = ref(false)
const creatingTask = ref(false)
const showDeleteConfirm = ref(false)
const deleteTargetTask = ref<{ id: string; name: string } | null>(null)

const createTask = async () => {
  if (!newTaskName.value.trim()) {
    createError.value = 'Please enter a task name'
    return
  }
  creatingTask.value = true
  createError.value = ''
  try {
    const created = await tasksApi.create(projectId.value, {
      name: newTaskName.value,
      direct_on_branch: newTaskDirectOnBranch.value
    })
    tasks.value.unshift(created)
    showCreateDialog.value = false
    newTaskName.value = ''
    newTaskDirectOnBranch.value = false
    await switchTask(created.id)
  } catch (err: any) {
    createError.value = err.message || 'Failed to create task'
  }
  creatingTask.value = false
}

const acceptSuccess = ref(false)

// Sync state
const syncing = ref(false)          // Sync in progress
const syncStep = ref('')            // Current sync step message
const hasConflicts = ref(false)     // Conflicts detected from sync
const conflictedFiles = ref<string[]>([])  // List of conflicted files
const syncNeedsResolution = ref(false)  // Backend returned needs_resolution=true

// PDF prompt state
const pdfPromptFile = ref<string | null>(null)
const openingPdf = ref(false)
const pdfError = ref<string | null>(null)
const pdfDownloadProgress = ref<{ loaded: number; total: number } | null>(null)

// Image preview state
const imagePreviewFile = ref<string | null>(null)
const imagePreviewUrl = ref<string | null>(null)
const loadingImage = ref(false)
const imageError = ref<string | null>(null)

// Symbol outline
const { symbols, extractSymbols } = useSymbolOutline()
const outlineCollapsed = ref(localStorage.getItem('v2c-outline-collapsed') === 'true')
const previewCollapsed = ref(localStorage.getItem('v2c-preview-collapsed') === 'true')
const editorRef = ref<InstanceType<typeof MonacoEditor> | null>(null)
const outlineRef = ref<InstanceType<typeof SymbolOutline> | null>(null)
const preview1Ref = ref<InstanceType<typeof EditorView> | null>(null)
const preview2Ref = ref<InstanceType<typeof EditorView> | null>(null)

const restoreEditorPosition = (viewState: EditorViewState, entry: HistoryEntry) => {
  // entry contains the actual position data to restore
  setTimeout(() => {
    if (!editorRef.value || !viewState.filePath) return

    // Restore scroll first (instant)
    editorRef.value.setScrollPosition({
      scrollTop: entry.scrollPosition.top,
      scrollLeft: entry.scrollPosition.left
    })

    // Restore cursor position
    editorRef.value.setPosition({
      lineNumber: entry.cursorPosition.line,
      column: entry.cursorPosition.column
    })

    // Reveal line in center
    editorRef.value.revealLineInCenter(entry.cursorPosition.line)
  }, 100)
}

/**
 * Add a new history entry for a file
 * Called when a file is opened for the first time
 * Enforces 50-file limit by removing oldest entry
 */
const addHistoryEntry = (viewState: EditorViewState, filePath: string) => {
  // Check if entry already exists
  const existingEntry = viewState.history.find(h => h.filePath === filePath)
  if (existingEntry) {
    // Entry exists, update timestamp to mark as recently accessed
    existingEntry.timestamp = Date.now()
    return
  }

  // Create new entry with default position
  const newEntry: HistoryEntry = {
    filePath,
    cursorPosition: { line: 1, column: 1 },
    scrollPosition: { top: 0, left: 0 },
    timestamp: Date.now()
  }

  // Add to history
  viewState.history.push(newEntry)

  // Enforce 50-file limit: remove oldest entries if exceeding
  while (viewState.history.length > 50) {
    // Find and remove the entry with the oldest timestamp
    const oldestIndex = viewState.history.reduce((minIdx, entry, idx, arr) =>
      entry.timestamp < arr[minIdx].timestamp ? idx : minIdx, 0)
    viewState.history.splice(oldestIndex, 1)
  }
}

/**
 * Update existing history entry with current position
 * Called when switching away from a file
 */
const updateHistoryEntry = (viewState: EditorViewState) => {
  if (!viewState.filePath || !editorRef.value) return

  const position = editorRef.value.getPosition()
  if (!position) return

  const scrollTop = editorRef.value.getScrollTop()
  const scrollLeft = editorRef.value.getScrollLeft()

  // Update history entry for current file
  const historyEntry = viewState.history.find(h => h.filePath === viewState.filePath)
  if (historyEntry) {
    historyEntry.cursorPosition = { line: position.lineNumber, column: position.column }
    historyEntry.scrollPosition = { top: scrollTop, left: scrollLeft }
    // Update timestamp to mark as recently accessed
    historyEntry.timestamp = Date.now()
  }
}

/**
 * Update existing preview history entry with current position
 * Uses EditorView's savePosition method for preview panes
 */
const updatePreviewHistoryEntry = (viewState: EditorViewState, previewRef: InstanceType<typeof EditorView> | null) => {
  if (!viewState.filePath || !previewRef) return

  const savedPos = previewRef.savePosition()
  if (!savedPos.cursorPosition) return

  // Update history entry for current file
  const historyEntry = viewState.history.find(h => h.filePath === viewState.filePath)
  if (historyEntry) {
    // Convert lineNumber to line (EditorView uses lineNumber, HistoryEntry uses line)
    historyEntry.cursorPosition = {
      line: savedPos.cursorPosition.lineNumber,
      column: savedPos.cursorPosition.column
    }
    historyEntry.scrollPosition = savedPos.scrollPosition || { top: 0, left: 0 }
    // Update timestamp to mark as recently accessed
    historyEntry.timestamp = Date.now()
  }
}

/**
 * Handle file preview opening via middle-click
 * Cycles between preview1 and preview2 panes
 */
const handleFilePreview = async (filePath: string) => {
  // Determine which preview to use based on cycle
  const currentPreviewKey = previewCycle.value
  const nextPreviewKey: 'preview1' | 'preview2' = currentPreviewKey === 'preview1' ? 'preview2' : 'preview1'

  // Get the current preview state and ref for position saving
  const currentPreviewState = currentPreviewKey === 'preview1' ? preview1State : preview2State
  const currentPreviewRef = currentPreviewKey === 'preview1' ? preview1Ref.value : preview2Ref.value

  // Save current preview's position before switching (if file was open)
  if (currentPreviewState.value.filePath) {
    updatePreviewHistoryEntry(currentPreviewState.value, currentPreviewRef)
  }

  // Show preview windows (hide terminal on desktop)
  showPreviews.value = true
  if (!isMobile.value) {
    showTerminal.value = false
  }

  // Load file content using FileCacheService (similar to loadFile)
  const targetState = currentPreviewKey === 'preview1' ? preview1State : preview2State

  try {
    // Step 1: Get hash from server
    const hashResult = await filesApi.getHash(taskId.value, filePath)
    const serverHash = hashResult.hash

    // Step 2: Check local cache
    const cached = FileCacheService.get(taskId.value, filePath)

    if (cached && cached.hash === serverHash) {
      // Cache hit - use cached content
      targetState.value.fileContent = cached.content
    } else {
      // Cache miss or stale - fetch from server
      const result = await filesApi.read(taskId.value, filePath)
      targetState.value.fileContent = result.content

      // Update cache if we have a hash
      if (result.hash) {
        FileCacheService.set(taskId.value, filePath, result.hash, result.content)
      }
    }

    // Update preview state
    targetState.value.filePath = filePath
    targetState.value.editorMode = 'editor'  // Previews are always in editor mode (read-only)

    // Add entry to preview history
    addHistoryEntry(targetState.value, filePath)

    // Find and restore position from history if available
    const historyEntry = targetState.value.history.find(h => h.filePath === filePath)
    if (historyEntry && (currentPreviewKey === 'preview1' ? preview1Ref.value : preview2Ref.value)) {
      // Restore position after content loads (EditorView handles this via props)
      // Position restoration happens when EditorView receives new history
    }
  } catch (err: any) {
    console.error('Failed to load file for preview:', err.message)
    // On error, still show preview with empty content
    targetState.value.filePath = filePath
    targetState.value.fileContent = ''
  }

  // Toggle previewCycle for next click
  previewCycle.value = nextPreviewKey
}

/**
 * Handle file preview with line number (from RefererSearch middle-click)
 * Opens file in preview and jumps to the specified line
 */
const handleFilePreviewWithLine = async (filePath: string, lineNumber: number) => {
  // Determine which preview to use based on cycle
  const currentPreviewKey = previewCycle.value
  const nextPreviewKey: 'preview1' | 'preview2' = currentPreviewKey === 'preview1' ? 'preview2' : 'preview1'

  // Get the current preview state and ref for position saving
  const currentPreviewState = currentPreviewKey === 'preview1' ? preview1State : preview2State
  const currentPreviewRef = currentPreviewKey === 'preview1' ? preview1Ref.value : preview2Ref.value

  // Save current preview's position before switching (if file was open)
  if (currentPreviewState.value.filePath) {
    updatePreviewHistoryEntry(currentPreviewState.value, currentPreviewRef)
  }

  // Show preview windows (hide terminal on desktop)
  showPreviews.value = true
  if (!isMobile.value) {
    showTerminal.value = false
  }

  // Load file content using FileCacheService
  const targetState = currentPreviewKey === 'preview1' ? preview1State : preview2State
  const targetRef = currentPreviewKey === 'preview1' ? preview1Ref.value : preview2Ref.value

  try {
    // Step 1: Get hash from server
    const hashResult = await filesApi.getHash(taskId.value, filePath)
    const serverHash = hashResult.hash

    // Step 2: Check local cache
    const cached = FileCacheService.get(taskId.value, filePath)

    if (cached && cached.hash === serverHash) {
      // Cache hit - use cached content
      targetState.value.fileContent = cached.content
    } else {
      // Cache miss or stale - fetch from server
      const result = await filesApi.read(taskId.value, filePath)
      targetState.value.fileContent = result.content

      // Update cache if we have a hash
      if (result.hash) {
        FileCacheService.set(taskId.value, filePath, result.hash, result.content)
      }
    }

    // Update preview state
    targetState.value.filePath = filePath
    targetState.value.editorMode = 'editor'  // Previews are always in editor mode (read-only)

    // Add entry to preview history
    addHistoryEntry(targetState.value, filePath)

    // Jump to line after content loads
    // Wait for EditorView to render, then call goToLine
    setTimeout(() => {
      if (targetRef) {
        targetRef.goToLine(lineNumber)
      }
    }, 150)
  } catch (err: any) {
    console.error('Failed to load file for preview:', err.message)
    // On error, still show preview with empty content
    targetState.value.filePath = filePath
    targetState.value.fileContent = ''
  }

  // Toggle previewCycle for next click
  previewCycle.value = nextPreviewKey
}

// Settings modal
const showSettingsModal = ref(false)

// Commit message modal
const showCommitMessageModal = ref(false)
const commitMessage = ref('')

// File type support check for symbol outline (only languages with extraction patterns)
const isSupportedFileType = computed(() => {
  if (!currentFile.value) return false
  const language = detectLanguage(currentFile.value)
  return supportsSymbolExtraction(language)
})

// Simple debounce utility (no VueUse dependency needed)
function debounce<T extends (...args: any[]) => any>(fn: T, delay: number): T {
  let timeoutId: ReturnType<typeof setTimeout> | null = null
  return ((...args: Parameters<T>) => {
    if (timeoutId) clearTimeout(timeoutId)
    timeoutId = setTimeout(() => fn(...args), delay)
  }) as T
}

// Debounced symbol extraction (300ms)
const debouncedExtractSymbols = debounce((content: string, path: string) => {
  if (outlineCollapsed.value) return // Lazy extraction - only when expanded
  extractSymbols(content, detectLanguage(path))
}, 300)

// Image file extensions
const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico']

function isImageFile(filePath: string): boolean {
  const lower = filePath.toLowerCase()
  return IMAGE_EXTENSIONS.some(ext => lower.endsWith(ext))
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function openPdfInBrowser() {
  if (!pdfPromptFile.value) return
  openingPdf.value = true
  pdfError.value = null
  pdfDownloadProgress.value = null
  try {
    const blob = await filesApi.getRawFile(taskId.value, pdfPromptFile.value, (progress: { loaded: number; total: number }) => {
      pdfDownloadProgress.value = progress
    })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
    // Revoke URL after delay to allow browser to load it
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (err) {
    pdfError.value = 'Failed to open PDF. Please try again.'
    console.error('Failed to open PDF:', err)
  } finally {
    openingPdf.value = false
    pdfDownloadProgress.value = null
  }
}

function closePdfPrompt() {
  pdfPromptFile.value = null
  pdfError.value = null
  pdfDownloadProgress.value = null
}

// Load and display image in the editor area
async function loadImagePreview(filePath: string) {
  imagePreviewFile.value = filePath
  loadingImage.value = true
  imageError.value = null

  // Clean up previous image URL
  if (imagePreviewUrl.value) {
    URL.revokeObjectURL(imagePreviewUrl.value)
    imagePreviewUrl.value = null
  }

  try {
    const blob = await filesApi.getRawFile(taskId.value, filePath)
    imagePreviewUrl.value = URL.createObjectURL(blob)
  } catch (err) {
    imageError.value = 'Failed to load image. Please try again.'
    console.error('Failed to load image:', err)
  } finally {
    loadingImage.value = false
  }
}

function closeImagePreview() {
  if (imagePreviewUrl.value) {
    URL.revokeObjectURL(imagePreviewUrl.value)
    imagePreviewUrl.value = null
  }
  imagePreviewFile.value = null
  imageError.value = null
}

// Markdown preview state
const showMarkdownPreview = ref(false)
const markdownPreviewPath = ref('')
const markdownPreviewContent = ref('')

// File quick jump state
const showFileQuickJump = ref(false)

// Resizable panels state
const layout = ref<Layout>({
  sidebar: 25,
  filesPane: 55,
  tabbedPane: 30,
  tasksPane: 15,
  terminalPx: 600    // Terminal width in pixels
})

// Track the editor+terminal container width to calculate terminal percentage
const editorContainerWidth = ref(0)

// Calculate terminal percentage from pixel width
const terminalPercent = computed(() => {
  // Hide terminal when previews are shown (mutual exclusivity)
  if (showPreviews.value) return 0
  if (!showTerminal.value || editorContainerWidth.value <= 0) return 0
  const percent = (layout.value.terminalPx / editorContainerWidth.value) * 100
  // Clamp between 10% and 90%
  const result = Math.max(10, Math.min(90, percent))
  console.log('[Layout Debug] terminalPercent computed', {
    terminalPx: layout.value.terminalPx,
    editorContainerWidth: editorContainerWidth.value,
    percent: percent,
    result: result
  })
  return result
})

// Computed properties for preview layout (70% main, 30% previews)
const mainEditorPercent = computed(() => {
  // When previews shown on desktop: 70% main editor
  // When previews hidden or on mobile: calculate based on terminal visibility
  if (isMobile.value) return 100
  if (showPreviews.value) return 70
  return showTerminal.value ? (100 - terminalPercent.value) : 100
})

const previewPercent = computed(() => {
  // When previews shown on desktop: 30% for preview area
  // When previews hidden or on mobile: 0%
  if (isMobile.value) return 0
  if (showPreviews.value) return 30
  return 0
})

// Nested preview split: Preview2 (top) 50%, Preview1 (bottom) 50%
const preview2Percent = 50
const preview1Percent = 50

// Splitpanes refs for programmatic control
const mainSplitpanesRef = ref<any>(null)
const sidebarSplitpanesRef = ref<any>(null)
const editorSplitpanesRef = ref<any>(null)

// Flag to prevent saving while loading
const isLoadingLayout = ref(false)

// Flag to track when layout is loaded (used to delay rendering)
const layoutLoaded = ref(false)

const STORAGE_KEY = computed(() => `vibe2crazy-layout-${taskId.value}`)
let saveTimeout: number | null = null

// File tree with lazy loading
const {
  nodes,
  rootPaths,
  loading: loadingFiles,
  loadingPaths,
  expandedDirs,
  loadRoot,
  expandDir,
  collapseDir,
  getNode
} = useFileTree(taskId)

// Provide file tree to child components
provideFileTree({ nodes, expandedDirs, loadingPaths } as any)

const saveLayout = () => {
  // Don't save if we're currently loading a saved layout
  if (isLoadingLayout.value) {
    console.log('[Layout Debug] Skipping save during layout loading')
    return
  }

  console.log('[Layout Debug] saveLayout called', {
    storageKey: STORAGE_KEY.value,
    layout: layout.value
  })
  if (saveTimeout) clearTimeout(saveTimeout)
  saveTimeout = window.setTimeout(() => {
    const layoutJson = JSON.stringify(layout.value)
    console.log('[Layout Debug] Saving to localStorage', {
      key: STORAGE_KEY.value,
      value: layoutJson
    })
    localStorage.setItem(STORAGE_KEY.value, layoutJson)
    // Verify it was saved
    const saved = localStorage.getItem(STORAGE_KEY.value)
    console.log('[Layout Debug] Verified saved value', saved)
  }, 100)
}

const loadLayout = (taskIdParam?: string) => {
  // Use provided taskId or fall back to computed taskId
  const effectiveTaskId = taskIdParam || taskId.value
  const storageKey = `vibe2crazy-layout-${effectiveTaskId}`

  console.log('[Layout Debug] loadLayout called', {
    storageKey,
    taskId: effectiveTaskId,
    providedParam: taskIdParam
  })

  try {
    const saved = localStorage.getItem(storageKey)
    console.log('[Layout Debug] Raw value from localStorage', saved)
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        console.log('[Layout Debug] Parsed layout', parsed)

        // Validate parsed layout has all required fields
        // Support both old format (terminal) and new format (terminalPx)
        const hasTerminalPx = typeof parsed.terminalPx === 'number'
        const hasOldTerminal = typeof parsed.terminal === 'number'
        if (typeof parsed.sidebar === 'number' &&
            typeof parsed.filesPane === 'number' &&
            typeof parsed.tabbedPane === 'number' &&
            typeof parsed.tasksPane === 'number' &&
            (hasTerminalPx || hasOldTerminal)) {

          console.log('[Layout Debug] Applying parsed layout to layout.value')

          // Set flag to prevent saving while loading
          isLoadingLayout.value = true

          // Handle backward compatibility: old format had 'terminal' (percentage), new format has 'terminalPx' (pixels)
          if (!hasTerminalPx && hasOldTerminal) {
            // Old format - clear the terminal field and use default pixel width
            // We can't convert percentage to pixels without knowing the container width at load time
            parsed.terminalPx = 600  // Default
            delete parsed.terminal
            console.log('[Layout Debug] Converted old terminal format to terminalPx=600')
          }

          // Update the reactive layout value
          layout.value = parsed
          console.log('[Layout Debug] Layout after applying', layout.value)

          // Programmatically set splitpanes sizes to match loaded layout
          // Wait for next tick to ensure components are mounted
          nextTick(() => {
            // The splitpanes ref exposes internal panes array
            const mainPanes = (mainSplitpanesRef.value as any)?.panes
            const sidebarPanes = (sidebarSplitpanesRef.value as any)?.panes
            const editorPanes = (editorSplitpanesRef.value as any)?.panes

            console.log('[Layout Debug] Splitpanes refs', {
              main: mainSplitpanesRef.value,
              sidebar: sidebarSplitpanesRef.value,
              editor: editorSplitpanesRef.value,
              mainPanes,
              sidebarPanes,
              editorPanes
            })

            if (mainPanes && mainPanes.length >= 2) {
              console.log('[Layout Debug] Setting main splitpanes sizes', [parsed.sidebar, 100 - parsed.sidebar])
              mainPanes[0].size = parsed.sidebar
              mainPanes[1].size = 100 - parsed.sidebar
            }
            if (sidebarPanes && sidebarPanes.length >= 3) {
              console.log('[Layout Debug] Setting sidebar splitpanes sizes', [parsed.filesPane, parsed.tabbedPane, parsed.tasksPane])
              sidebarPanes[0].size = parsed.filesPane
              sidebarPanes[1].size = parsed.tabbedPane
              sidebarPanes[2].size = parsed.tasksPane
            }
            // Editor panes sizes are controlled by terminalPercent computed property
            // Don't set them programmatically - the template binding handles it

            // Clear flag after a delay to allow splitpanes to process changes
            setTimeout(() => {
              isLoadingLayout.value = false
              layoutLoaded.value = true
              console.log('[Layout Debug] Layout loading complete')
            }, 200)
          })
        } else {
          console.warn('[Layout Debug] Parsed layout missing required fields', parsed)
        }
      } catch (e) {
        console.error('[Layout Debug] Failed to parse layout from localStorage', e)
      }
    } else {
      console.log('[Layout Debug] No saved layout found in localStorage')
    }
  } catch (e) {
    // Catch any localStorage access errors (e.g., privacy mode, cross-origin restrictions)
    console.error('[Layout Debug] Failed to access localStorage, using defaults', e)
  }

  // Always mark layout as loaded, even if using defaults or localStorage failed
  // This ensures the UI renders even if localStorage is inaccessible
  layoutLoaded.value = true
}

// Navigate back to tasks list with full page reload
const goBackToTasks = () => {
  router.push('/projects')
}

// Check if device is mobile
const checkMobile = () => {
  isMobile.value = window.innerWidth < 768
}

type LayoutEvent = any[]

const handleSidebarResize = (event: LayoutEvent) => {
  const panes = (event as any).panes
  if (!panes || panes.length < 3) return

  layout.value.filesPane = Math.round(panes[0].size)
  layout.value.tabbedPane = Math.round(panes[1].size)
  layout.value.tasksPane = Math.round(panes[2].size)
}

const handleEditorResize = (event: LayoutEvent) => {
  console.log('[Layout Debug] handleEditorResize called', { event, showTerminal: showTerminal.value, editorContainerWidth: editorContainerWidth.value })
  const panes = (event as any).panes
  if (showTerminal.value && panes && panes.length >= 2 && editorContainerWidth.value > 0) {
    // Convert percentage back to pixels
    const terminalPercentValue = panes[1].size
    layout.value.terminalPx = Math.round((terminalPercentValue / 100) * editorContainerWidth.value)
    console.log('[Layout Debug] Updated terminal size', { percent: terminalPercentValue, pixels: layout.value.terminalPx })
  }
}

const handleMainResize = (event: LayoutEvent) => {
  console.log('[Layout Debug] handleMainResize called', event)
  const panes = (event as any).panes
  if (panes && panes.length >= 2) {
    layout.value.sidebar = Math.round(panes[0].size)
    console.log('[Layout Debug] Updated sidebar size', layout.value.sidebar)
  }
}

// Diff editor ref
const diffEditorRef = ref<any>(null)

// Conflict editor ref
const conflictEditorRef = ref<any>(null)

// Merge dialog state
const showMergeDialog = ref(false)
const mergeMessage = ref('')
const mergeInputRef = ref<HTMLInputElement>()

// Auto-focus input when dialog opens
watch(showMergeDialog, (isOpen) => {
  if (isOpen && mergeInputRef.value) {
    nextTick(() => {
      mergeInputRef.value?.focus()
      mergeInputRef.value?.select()
    })
  }
})

watch(showTerminal, (isShown) => {
  // Mutual exclusivity: hide previews when terminal is shown
  if (isShown) {
    showPreviews.value = false
    if (layout.value.terminalPx === 0) {
      layout.value.terminalPx = 600  // Default terminal width in pixels
    }
  }
})


watch(layout, (newLayout, oldLayout) => {
  console.log('[Layout Debug] layout watcher triggered', {
    old: oldLayout,
    new: newLayout
  })
  saveLayout()
}, { deep: true })

// Reset to page 1 when task changes and cleanup old terminal connection
// Skip when oldId is empty - onMounted handles initial load to avoid duplicate requests
watch(taskId, async (_newId, oldId) => {
  // Skip if this is the initial load (no oldId) - onMounted already handles this
  if (!oldId) return

  // Close old task's terminal connection when switching tasks
  closePersistentConnection(oldId)
  currentPage.value = 1
  changedFilesPage.value = 1
  await loadTask()
  await Promise.all([
    loadChangedFiles(),
    loadCommits(),
    refreshCurrentTaskStatus(),
    loadFileTree()
  ])
})

// Also watch individual layout properties to see which ones change
watch(() => layout.value.sidebar, (newVal, oldVal) => {
  console.log('[Layout Debug] sidebar changed', { old: oldVal, new: newVal })
})
watch(() => layout.value.filesPane, (newVal, oldVal) => {
  console.log('[Layout Debug] filesPane changed', { old: oldVal, new: newVal })
})
watch(() => layout.value.tabbedPane, (newVal, oldVal) => {
  console.log('[Layout Debug] tabbedPane changed', { old: oldVal, new: newVal })
})
watch(() => layout.value.tasksPane, (newVal, oldVal) => {
  console.log('[Layout Debug] tasksPane changed', { old: oldVal, new: newVal })
})
watch(() => layout.value.terminalPx, (newVal, oldVal) => {
  console.log('[Layout Debug] terminalPx changed', { old: oldVal, new: newVal })
})

watch(editorContainerWidth, (newVal, oldVal) => {
  console.log('[Layout Debug] editorContainerWidth changed', { old: oldVal, new: newVal })
})

// Update markdown preview content in real-time
watch(fileContent, (newContent) => {
  if (showMarkdownPreview.value && currentFile.value?.toLowerCase().endsWith('.md')) {
    markdownPreviewContent.value = newContent
  }
})

const goToNextDiff = () => {
  if (diffEditorRef.value) {
    diffEditorRef.value.goToNextDiff()
  }
}

const goToPrevDiff = () => {
  if (diffEditorRef.value) {
    diffEditorRef.value.goToPrevDiff()
  }
}

// Mobile view toggle methods
const toggleFileList = () => {
  if (isMobile.value) {
    showFileList.value = !showFileList.value
    if (showFileList.value) {
      showTerminal.value = false
    }
  }
}

const toggleTerminal = () => {
  if (isMobile.value) {
    // Close file list first if it's open
    if (showFileList.value) {
      showFileList.value = false
    }
    showTerminal.value = !showTerminal.value
  } else {
    // Desktop: just toggle terminal
    showTerminal.value = !showTerminal.value
  }
}

const loadFileTree = async () => {
  if (!taskId.value) return

  try {
    await loadRoot()
    console.log('[CodeReviewView] loadFileTree: rootPaths =', rootPaths.value, 'nodes size =', nodes.value.size)
  } catch (err: any) {
    console.error('Failed to load file tree:', err)
  }
}

const handleSearchSelect = async (filePath: string, lineNumber: number) => {
  console.log('[handleSearchSelect] filePath:', filePath, 'lineNumber:', lineNumber)
  if (currentFile.value !== filePath) {
    pendingLineJump.value = lineNumber
    await loadFile(filePath)
    console.log('[handleSearchSelect] loadFile done, currentFile:', currentFile.value)
  } else {
    // Same file, just jump to line
    nextTick(() => {
      if (editorRef.value) {
        editorRef.value.goToLine(lineNumber)
        console.log('[handleSearchSelect] goToLine called (same file)')
      }
    })
  }
}

const handleFindReferences = (selectedText: string) => {
  refererQuery.value = selectedText
  activeFilesTab.value = 'referer'
  // Trigger search after tab switches to 'referer'
  nextTick(() => {
    const searchBtn = document.querySelector('.referer-search .search-btn') as HTMLButtonElement
    if (searchBtn) searchBtn.click()
  })
}

const loadTask = async (taskIdOverride?: string) => {
  const id = taskIdOverride || taskId.value
  try {
    const taskData = await tasksApi.get(id)
    store.setCurrentTask(taskData)
    store.setCurrentProject({ id: taskData.project_id })
    // Also load all tasks for the sidebar list
    tasksLoading.value = true
    try {
      tasks.value = await tasksApi.list(projectId.value)
    } finally {
      tasksLoading.value = false
    }
  } catch (err: any) {
    console.error('Failed to load task:', err)
    router.push('/projects')
  }
}

const loadChangedFiles = async (page: number = 1) => {
  // Guard against navigation/unmounting - don't make API calls if taskId is undefined
  if (!taskId.value) return

  // Don't show loading spinner during auto-refresh to prevent jitter
  // initialLoading handles the first load only
  try {
    changedFilesData.value = await filesApi.getChangedFiles(taskId.value, page, 20)
    changedFiles.value = changedFilesData.value.files
    changedFilesPage.value = page
  } catch (err: any) {
    console.error('Failed to load changed files:', err)
  }
}

const handleChangedFilesPageChange = (page: number) => {
  loadChangedFiles(page)
  // Scroll to top of changed files list
  const changedFilesPane = document.querySelector('.changed-files-list')
  if (changedFilesPane) {
    changedFilesPane.scrollTop = 0
  }
}

const loadFile = async (filePath: string | null, mode: 'editor' | 'diff' = 'editor') => {
  console.log('[CodeReviewView] loadFile called, filePath:', filePath, 'mode:', mode)
  if (!filePath) {
    // Just closing sidebar on mobile
    if (isMobile.value) {
      showFileList.value = false
      showTerminal.value = false
    }
    return
  }

  console.log('[CodeReviewView] loadFile: proceeding to load file', filePath)

  // CHECK FOR PDF: If file is PDF, show prompt to open in browser
  if (filePath.endsWith('.pdf')) {
    pdfPromptFile.value = filePath
    pdfError.value = null
    closeImagePreview() // Close any image preview

    // Close sidebar on mobile
    if (isMobile.value) {
      showFileList.value = false
      showTerminal.value = false
    }
    return
  }

  // CHECK FOR IMAGE: If file is an image, show preview in editor area
  if (isImageFile(filePath)) {
    closePdfPrompt() // Close any PDF prompt
    loadImagePreview(filePath)

    // Close sidebar on mobile
    if (isMobile.value) {
      showFileList.value = false
      showTerminal.value = false
    }
    return
  }

  // Reset PDF prompt and image preview state when loading other files
  pdfPromptFile.value = null
  closeImagePreview()

  currentFile.value = filePath
  editorMode.value = mode
  loadingContent.value = true
  saveError.value = ''
  isFileDeleted.value = false  // RESET: Clear any previous deleted state

  // Close sidebar and show editor on mobile
  if (isMobile.value) {
    showFileList.value = false
    showTerminal.value = false
  }

  // CHECK IF DELETED: Check if file is deleted
  const fileStatus = changedFiles.value.find(f => f.path === filePath)?.status
  if (fileStatus === 'D') {
    isFileDeleted.value = true
    editorMode.value = 'deleted'

    // Load original content from git (no caching for deleted files)
    try {
      const originalResult = await filesApi.getOriginal(taskId.value, filePath)
      fileContent.value = originalResult.content
      originalContent.value = originalResult.content
    } catch (err: any) {
      saveError.value = 'This file was deleted and has no history to display'
    }
    loadingContent.value = false
    return
  }

  // CHECK IF CONFLICT: Check if file has merge conflict
  if (fileStatus === 'U') {
    editorMode.value = 'conflict'

    // Load current file content (with conflict markers)
    try {
      const result = await filesApi.read(taskId.value, filePath)
      fileContent.value = result.content
      // Load original content from git for the base version
      try {
        const originalResult = await filesApi.getOriginal(taskId.value, filePath)
        originalContent.value = originalResult.content
      } catch (origErr: any) {
        originalContent.value = ''
      }
    } catch (err: any) {
      saveError.value = err.message || 'Failed to load file with conflicts'
    }
    loadingContent.value = false
    return
  }

  // === CACHE LOGIC START ===
  try {
    // Step 1: Get hash from server
    const hashResult = await filesApi.getHash(taskId.value, filePath)
    const serverHash = hashResult.hash

    // Step 2: Check local cache
    const cached = FileCacheService.get(taskId.value, filePath)

    if (cached && cached.hash === serverHash) {
      // Cache hit - use cached content
      fileContent.value = cached.content

      // If diff mode, still need to load original content from git
      if (mode === 'diff') {
        try {
          const originalResult = await filesApi.getOriginal(taskId.value, filePath)
          originalContent.value = originalResult.content
        } catch (origErr: any) {
          originalContent.value = ''
        }
      } else {
        originalContent.value = cached.content
      }

      // Extract symbols for supported file types (both editor and diff mode)
      if (isSupportedFileType.value) {
        extractSymbols(cached.content, detectLanguage(filePath))
      }

      loadingContent.value = false
      return
    }

    // Cache miss or stale - fetch from server
    const result = await filesApi.read(taskId.value, filePath)
    fileContent.value = result.content

    // Update cache
    if (result.hash) {
      FileCacheService.set(taskId.value, filePath, result.hash, result.content)
    }

    // If diff mode, load original content from git
    if (mode === 'diff') {
      try {
        const originalResult = await filesApi.getOriginal(taskId.value, filePath)
        originalContent.value = originalResult.content
      } catch (origErr: any) {
        // If getting original fails (new file), use empty string
        originalContent.value = ''
      }
    } else {
      originalContent.value = result.content
    }
  } catch (err: any) {
    // Hash endpoint failed or other error - fall back to direct fetch
    console.warn('Cache check failed, fetching directly:', err.message)
    try {
      const result = await filesApi.read(taskId.value, filePath)
      fileContent.value = result.content

      // Cache the result if we have a hash
      if (result.hash) {
        FileCacheService.set(taskId.value, filePath, result.hash, result.content)
      }

      if (mode === 'diff') {
        try {
          const originalResult = await filesApi.getOriginal(taskId.value, filePath)
          originalContent.value = originalResult.content
        } catch (origErr: any) {
          originalContent.value = ''
        }
      } else {
        originalContent.value = result.content
      }
    } catch (readErr: any) {
      fileContent.value = ''  // Clear previous content
      originalContent.value = ''  // Clear original content too
      saveError.value = readErr.message || 'Failed to load file'
    }
  }
  // === CACHE LOGIC END ===

  // Extract symbols for supported file types (both editor and diff mode)
  if (currentFile.value && fileContent.value && isSupportedFileType.value) {
    extractSymbols(fileContent.value, detectLanguage(currentFile.value))
  }

  loadingContent.value = false
}

const saveFile = async () => {
  if (!currentFile.value) return

  savingContent.value = true
  saveError.value = ''

  try {
    await filesApi.write(taskId.value, currentFile.value, fileContent.value)
    originalContent.value = fileContent.value
    // Refresh changed files list after save
    await loadChangedFiles()
  } catch (err: any) {
    saveError.value = err.message || 'Failed to save file'
  }

  savingContent.value = false
}

// Conflict editor handlers
const handleConflictContentUpdate = (newContent: string) => {
  fileContent.value = newContent
}

const handleConflictResolved = () => {
  // All conflicts resolved - just update UI state
  // The user still needs to save the file manually
  // When they save, saveConflictFile will handle git add if no conflicts remain
}

// Save conflict file (partial save - doesn't require all conflicts resolved)
const saveConflictFile = async () => {
  if (!currentFile.value) return

  savingContent.value = true
  saveError.value = ''

  try {
    await filesApi.write(taskId.value, currentFile.value, fileContent.value)
    originalContent.value = fileContent.value

    // Check if all conflicts resolved - if so, stage the file
    const unresolvedCount = conflictEditorRef.value?.unresolvedCount ?? 0
    if (unresolvedCount === 0) {
      await filesApi.stageFile(taskId.value, currentFile.value)
      editorMode.value = 'editor'  // Switch back to normal editor mode
    }

    // Refresh changed files list after save
    await loadChangedFiles()
  } catch (err: any) {
    saveError.value = err.message || 'Failed to save file'
  }

  savingContent.value = false
}

const openMarkdownPreview = () => {
  if (!currentFile.value || !currentFile.value.toLowerCase().endsWith('.md')) {
    return
  }
  markdownPreviewPath.value = currentFile.value
  markdownPreviewContent.value = fileContent.value
  showMarkdownPreview.value = true
}

// Symbol outline handlers
function handleSymbolSelect(symbol: SymbolInfo) {
  if (editorMode.value === 'diff' && diffEditorRef.value) {
    // For diff editor, navigate to line in the modified editor
    const diffEditor = diffEditorRef.value.getDiffEditor()
    if (diffEditor) {
      const modifiedEditor = diffEditor.getModifiedEditor()
      modifiedEditor.revealLineInCenter(symbol.lineNumber)
      modifiedEditor.setSelection({
        startLineNumber: symbol.lineNumber,
        startColumn: 1,
        endLineNumber: symbol.lineNumber,
        endColumn: 1
      })
      modifiedEditor.focus()
    }
  } else if (editorRef.value) {
    editorRef.value.goToLine(symbol.lineNumber)
  }
}

function handleCursorWord(word: string, _position: { lineNumber: number; column: number }) {
  if (outlineRef.value) {
    outlineRef.value.loadPreviewBySymbolName(word)
  }
}

// Pending line jump after file loads
const pendingLineJump = ref<number | null>(null)

// Watch for file content changes to execute pending line jumps
watch(fileContent, () => {
  if (pendingLineJump.value !== null) {
    const line = pendingLineJump.value
    pendingLineJump.value = null
    // Wait for Monaco to render the new content
    setTimeout(() => {
      if (editorRef.value) {
        editorRef.value.goToLine(line)
        console.log('[handleSearchSelect] goToLine called, line:', line)
      }
    }, 100)
  }
})

async function handleSymbolNavigate(filePath: string, lineNumber: number) {
  // If the file is different from current, load it first
  if (currentFile.value !== filePath) {
    pendingLineJump.value = lineNumber
    await loadFile(filePath, 'editor')
  } else {
    // Same file, just jump to line
    nextTick(() => {
      if (editorRef.value) {
        editorRef.value.goToLine(lineNumber)
      }
    })
  }
}

function handleOutlineToggle() {
  outlineCollapsed.value = !outlineCollapsed.value
  localStorage.setItem('v2c-outline-collapsed', String(outlineCollapsed.value))

  // When SYMBOLS expands, collapse Preview (accordion behavior)
  if (!outlineCollapsed.value) {
    previewCollapsed.value = true
    localStorage.setItem('v2c-preview-collapsed', 'true')
  }

  // Extract symbols when expanding if not already done
  if (!outlineCollapsed.value && currentFile.value && fileContent.value && isSupportedFileType.value) {
    extractSymbols(fileContent.value, detectLanguage(currentFile.value))
  }
}

function handlePreviewToggle() {
  previewCollapsed.value = !previewCollapsed.value
  localStorage.setItem('v2c-preview-collapsed', String(previewCollapsed.value))

  // When Preview expands, collapse SYMBOLS (accordion behavior)
  if (!previewCollapsed.value) {
    outlineCollapsed.value = true
    localStorage.setItem('v2c-outline-collapsed', 'true')
  }
}

// Toggle multi-view preview panes (mutual exclusivity with terminal)
function handleTogglePreviewPanes() {
  if (isMobile.value) return  // Don't show previews on mobile
  showPreviews.value = !showPreviews.value
}

function handleContentChange() {
  if (currentFile.value && fileContent.value && isSupportedFileType.value) {
    debouncedExtractSymbols(fileContent.value, currentFile.value)
  }
}

// Handle file selection from quick jump modal
const handleQuickJumpFileSelect = (filePath: string) => {
  loadFile(filePath, 'editor')
}

const openMergeDialog = () => {
  mergeMessage.value = task.value?.name || ''
  showMergeDialog.value = true
}

const mergeTask = () => {
  openMergeDialog()
}

const confirmMerge = async () => {
  showMergeDialog.value = false

  // Check for uncommitted changes first
  if (changedFiles.value.length > 0) {
    mergeError.value = `Please accept changes first. Found ${changedFiles.value.length} uncommitted file(s).`
    return
  }

  syncing.value = true
  syncStep.value = 'Fetching latest changes...'
  mergeError.value = ''
  mergeSuccess.value = false
  mergeExecutionLog.value = null

  try {
    syncStep.value = 'Merging main into worktree...'
    // Use custom message from dialog
    const response = await tasksApi.merge(taskId.value, mergeMessage.value)

    if (response.conflicts) {
      // Handle conflicts
      syncing.value = false
      mergeError.value = response.message || 'Merge failed due to conflicts'
      mergeExecutionLog.value = response.execution_log || null
      return
    }

    if (!response.success) {
      // Handle merge failure
      syncing.value = false
      mergeError.value = response.message || 'Merge failed'
      mergeExecutionLog.value = response.execution_log || null
      return
    }

    // Success
    syncing.value = false
    mergeSuccess.value = true
    await loadTask()
    await loadChangedFiles()
    await loadCommits(true)  // Refresh commits after merge

  } catch (err: any) {
    syncing.value = false
    mergeError.value = err.message || 'Merge failed'
  }
}

const loadConflictedFile = async (filePath: string) => {
  try {
    // Load the conflicted file in diff mode
    await loadFile(filePath, 'diff')
    // Close the conflict modal and clear error (after file loads successfully)
    hasConflicts.value = false
    syncNeedsResolution.value = false
    mergeError.value = ''  // Clear error to prevent error dialog from showing
    mergeExecutionLog.value = null  // Clear execution log
  } catch (err: any) {
    // Keep modal open on error, don't reset state
    console.error('Failed to load conflicted file:', err)
  }
}

const dismissConflictModal = () => {
  hasConflicts.value = false
  syncNeedsResolution.value = false
  mergeError.value = ''  // Clear error to prevent dialog from showing
  mergeExecutionLog.value = null  // Clear execution log
}

const copyExecutionLog = () => {
  if (!mergeExecutionLog.value) return

  const logText = mergeExecutionLog.value.map(cmd => {
    let text = `$ ${cmd.command}\n`
    if (cmd.exit_code !== 0) {
      text += `✗ Exit code: ${cmd.exit_code}\n`
    }
    if (cmd.stdout) {
      text += `${cmd.stdout}\n`
    }
    if (cmd.stderr) {
      text += `${cmd.stderr}\n`
    }
    return text
  }).join('\n')

  navigator.clipboard.writeText(logText).catch(err => {
    console.error('Failed to copy execution log:', err)
  })
}

const openCommitMessageModal = () => {
  commitMessage.value = `Accept changes for ${task.value?.name || 'task'}`
  showCommitMessageModal.value = true
}

const acceptChanges = async () => {
  showCommitMessageModal.value = false
  accepting.value = true
  acceptError.value = ''
  acceptSuccess.value = false

  try {
    await tasksApi.accept(taskId.value, commitMessage.value)
    acceptSuccess.value = true
    // Reload changed files to update the list
    await loadChangedFiles()
    // Reload commits to show the new commit
    await loadCommits(true)
    // Auto-hide success message after 2 seconds
    setTimeout(() => {
      acceptSuccess.value = false
    }, 2000)
  } catch (err: any) {
    acceptError.value = err.message || 'Accept failed'
  }

  accepting.value = false
}

const refreshCurrentTaskStatus = async () => {
  // Guard against navigation/unmounting - don't make API calls if taskId is undefined
  if (!taskId.value) return

  try {
    const status = await tasksApi.getStatus(taskId.value)
    if (task.value) {
      task.value.task_status = status.task_status
      task.value.code_status = status.code_status
      task.value.last_task_status_check = status.last_task_status_check
      task.value.last_code_status_check = status.last_code_status_check
    }
  } catch (err: any) {
    console.error('Failed to refresh current task status:', err)
  }
}

const refreshAllTasksStatus = async () => {
  if (!tasks.value.length) return

  try {
    const results = await Promise.all(
      tasks.value.map(t => tasksApi.getStatus(t.id))
    )
    results.forEach((status: { task_status: TaskStatusType; code_status: CodeStatusType }, index: number) => {
      tasks.value[index].task_status = status.task_status
      tasks.value[index].code_status = status.code_status
    })
  } catch (err: any) {
    console.error('Failed to refresh all tasks status:', err)
  }
}

const switchTask = async (newTaskId: string) => {
  if (newTaskId === taskId.value) return

  // 1. Update URL without page reload
  router.replace({ query: { task: newTaskId } })

  // 2. Load new task data
  const taskData = await tasksApi.get(newTaskId)
  store.setCurrentTask(taskData)

  // 3. Reload all dependent data in parallel
  await Promise.all([
    loadChangedFiles(),
    loadCommits(true),
    refreshCurrentTaskStatus(),
    loadFileTree()
  ])

  // 4. Reset editor state
  currentFile.value = null
  fileContent.value = ''
  originalContent.value = ''
  editorMode.value = 'editor'

  // 5. Reset pagination
  currentPage.value = 1
  changedFilesPage.value = 1

  // 6. Hide sidebar on mobile
  if (isMobile.value) {
    showFileList.value = false
  }
}

const toggleDir = async (path: string) => {
  const node = getNode(path)
  if (!node) return

  if (expandedDirs.value.has(path)) {
    collapseDir(path)
  } else {
    await expandDir(path)
  }
}

const deleteTask = async (id: string, event: Event) => {
  event.stopPropagation()
  const task = tasks.value.find(t => t.id === id)
  if (!task || task.direct_on_branch) return
  deleteTargetTask.value = { id: task.id, name: task.name }
  showDeleteConfirm.value = true
}

const confirmDeleteTask = async () => {
  if (!deleteTargetTask.value) return
  try {
    await tasksApi.delete(deleteTargetTask.value.id)
    tasks.value = tasks.value.filter(t => t.id !== deleteTargetTask.value!.id)
    if (deleteTargetTask.value.id === taskId.value && tasks.value.length > 0) {
      await switchTask(tasks.value[0].id)
    }
  } catch (err: any) {
    console.error('Failed to delete task:', err)
  } finally {
    showDeleteConfirm.value = false
    deleteTargetTask.value = null
  }
}

const cancelDeleteTask = () => {
  showDeleteConfirm.value = false
  deleteTargetTask.value = null
}

// Helper functions for FileTreeItem
const isChanged = (path: string) => changedFiles.value.some(f => f.path === path)
const isSelected = (path: string) => currentFile.value === path && editorMode.value === 'editor'
const isLoading = (path: string) => loadingPaths.value.has(path)
const getFileStatus = (path: string) => changedFiles.value.find(f => f.path === path)?.status

// Provide helper functions to child components
provide('isChanged', isChanged)
provide('isSelected', isSelected)
provide('isLoading', isLoading)
provide('getFileStatus', getFileStatus)

const loadCommits = async (silent: boolean = false) => {
  // Guard against navigation/unmounting - don't make API calls if taskId is undefined
  if (!taskId.value) return

  if (!silent) {
    loadingCommits.value = true
  }
  commitsError.value = ''

  try {
    commitsData.value = await gitApi.getWorktreeCommits(taskId.value, currentPage.value)
    console.log('[DEBUG] API Response:', commitsData.value)
    const newCommits = commitsData.value?.items
    console.log('[DEBUG] newCommits:', newCommits)

    // Always update commits list
    if (newCommits) {
      commits.value = newCommits
      console.log('[DEBUG] commits.value set to:', commits.value.length, 'commits')

      // Check if commit data has changed for highlighting
      if (isNewCommitData(newCommits)) {
        // Get hashes of new commits for highlighting
        newCommitHashes.value = getNewCommitHashes(newCommits)
        console.log('New commits detected:', Array.from(newCommitHashes.value))
      }
    } else {
      console.log('[DEBUG] newCommits is falsy, not updating commits.value')
    }
  } catch (err: any) {
    console.error('[DEBUG] Failed to load commits:', err)
    console.error('[DEBUG] Error details:', err.message, err.stack)
    if (!silent) {
      commitsError.value = err.message || 'Failed to load commits'
    }
  }

  if (!silent) {
    loadingCommits.value = false
  }
}

const handlePageChange = (page: number) => {
  // Prevent concurrent requests
  if (loadingCommits.value) return

  currentPage.value = page
  loadingCommits.value = true

  gitApi.getWorktreeCommits(taskId.value, page)
    .then((data: PaginatedCommitsResponse | null) => {
      commitsData.value = data
      commits.value = data?.items || []
    })
    .catch((error: any) => {
      if (error.status === 422) {
        // Validation error - reset to page 1
        currentPage.value = 1
        loadCommits()
      } else {
        commitsError.value = 'Failed to load commits'
      }
    })
    .finally(() => {
      loadingCommits.value = false
    })

  // Scroll to top of commits list with better selector
  const commitsPane = document.querySelector('.commits-list')
  if (commitsPane) {
    commitsPane.scrollTop = 0
  } else {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

const handleShowContextMenu = (event: {
  x: number
  y: number
  path: string
  type: string
  source?: 'files' | 'changedFiles'
}) => {
  contextMenu.value = {
    show: true,
    x: event.x,
    y: event.y,
    path: event.path,
    type: event.type,
    source: event.source || 'files',  // default to 'files'
    commit: null
  }
}

const handleCommitContextMenu = (event: { x: number; y: number; commit: CommitInfo }) => {
  contextMenu.value = {
    show: true,
    x: event.x,
    y: event.y,
    path: '',
    type: '',
    source: 'commits',
    commit: event.commit
  }
}

// Close context menu when clicking anywhere in the view
const closeContextMenuOnClick = () => {
  if (contextMenu.value.show) {
    closeContextMenu()
  }
}

const closeContextMenu = () => {
  contextMenu.value.show = false
}

// Upload state
const fileInputRef = ref<HTMLInputElement>()
const uploadProgress = ref({
  show: false,
  current: 0,
  total: 0,
  currentFile: '',
  cancelled: false
})

// Upload handlers
const handleUploadFiles = () => {
  closeContextMenu()
  fileInputRef.value?.click()
}

const handleFileSelect = async (e: Event) => {
  const target = e.target as HTMLInputElement
  const files = target.files
  if (!files || files.length === 0) return

  // Determine target path
  const path = contextMenu.value.path
  const type = contextMenu.value.type
  let targetPath = ''

  if (type === 'directory') {
    targetPath = path
  } else {
    // For files, upload to parent directory
    targetPath = path.split('/').slice(0, -1).join('/')
  }

  // Reset and show progress
  uploadProgress.value = {
    show: true,
    current: 0,
    total: files.length,
    currentFile: files[0]?.name || '',
    cancelled: false
  }

  try {
    // Upload files sequentially
    for (let i = 0; i < files.length; i++) {
      if (uploadProgress.value.cancelled) {
        break
      }

      uploadProgress.value.current = i
      uploadProgress.value.currentFile = files[i].name

      // Upload single file
      const formData = new FormData()
      formData.append('files', files[i])
      formData.append('target_path', targetPath)

      const token = localStorage.getItem('auth_token')
      const response = await fetch(`${import.meta.env.VITE_API_BASE || '/api'}/tasks/${taskId.value}/files/upload`, {
        method: 'POST',
        headers: {
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: formData
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
        console.error(`Failed to upload ${files[i].name}:`, error.detail || error.message)
      }
    }

    // Reload files to show new uploads
    await loadFileTree()
    await loadChangedFiles()
  } catch (error) {
    console.error('Upload error:', error)
  } finally {
    uploadProgress.value.show = false
    target.value = '' // Reset file input
  }
}

const cancelUpload = () => {
  uploadProgress.value.cancelled = true
}

// Download handler
const handleDownloadFile = () => {
  closeContextMenu()
  const path = contextMenu.value.path
  try {
    filesApi.downloadFile(taskId.value, path)
  } catch (error) {
    console.error('Download failed:', error)
  }
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const items: MenuItem[] = [
    {
      label: 'Copy Path',
      icon: '📋',
      action: () => {
        console.log('[ContextMenu] Copy Path clicked, path:', contextMenu.value.path)
        copyPathToClipboard(contextMenu.value.path)
      }
    }
  ]

  // Add different menu items based on source
  if (contextMenu.value.source === 'files') {
    items.push({
      label: 'Upload Files',
      icon: '⬆️',
      action: () => handleUploadFiles(),
      disabled: uploadProgress.value.show
    })
    items.push({
      label: contextMenu.value.type === 'directory' ? 'Download (ZIP)' : 'Download',
      icon: contextMenu.value.type === 'directory' ? '📦' : '⬇️',
      action: () => handleDownloadFile(),
      disabled: false
    })
    items.push({
      label: 'Delete',
      icon: '🗑️',
      action: async () => {
        const path = contextMenu.value.path
        const confirmed = await showConfirm({
          title: 'Delete Item',
          message: `Are you sure you want to delete ${path}?`,
          confirmText: 'Delete',
          danger: true
        })

        if (!confirmed) {
          closeContextMenu()
          return
        }

        closeContextMenu()
        try {
          await filesApi.deleteFile(taskId.value, path)
          await loadChangedFiles()
        } catch (error) {
          console.error('Failed to delete file:', error)
        }
      },
      danger: true
    })
  } else if (contextMenu.value.source === 'changedFiles') {
    items.push({
      label: 'Revert',
      icon: '↩️',
      action: async () => {
        const path = contextMenu.value.path

        // Check if file is tracked for appropriate confirmation message
        const file = changedFiles.value.find(f => f.path === path)
        const isUntracked = file?.status === '?'

        const confirmed = await showConfirm({
          title: 'Revert Changes',
          message: isUntracked
            ? `This file is untracked and will be deleted: ${path}`
            : `Revert all changes to: ${path}`,
          confirmText: 'Revert',
          danger: true
        })

        if (!confirmed) {
          closeContextMenu()
          return
        }

        closeContextMenu()
        try {
          const result = await filesApi.revertFile(taskId.value, path)
          if (result.success) {
            // Show appropriate success message based on tracking
            if (result.is_tracked) {
              console.log('[Revert] File reverted successfully')
            } else {
              console.log('[Revert] Untracked file deleted')
            }
            await loadChangedFiles()
            // If the reverted file was the current file, clear it
            if (currentFile.value === path) {
              currentFile.value = null
            }
          }
        } catch (error: any) {
          console.error('Failed to revert file:', error)
        }
      },
      danger: true
    })
  } else if (contextMenu.value.source === 'commits' && contextMenu.value.commit) {
    const commit = contextMenu.value.commit
    const commitIndex = commits.value.findIndex(c => c.hash === commit.hash)
    const commitsToUndo = commitIndex >= 0 ? commitIndex : 0

    items.push({
      label: 'Reset to this commit',
      icon: '↩️',
      action: async () => {
        const confirmed = await showConfirm({
          title: `Reset to commit ${commit.hash.slice(0, 8)}?`,
          message: `This will undo ${commitsToUndo} commit(s).\nChanges will be kept in working directory.`,
          confirmText: 'Reset',
          cancelText: 'Cancel',
          danger: true
        })

        if (!confirmed) {
          closeContextMenu()
          return
        }

        closeContextMenu()
        try {
          const result = await gitApi.resetToCommit(taskId.value, commit.hash)
          if (result.success) {
            await loadCommits()
            await loadChangedFiles()
          } else {
            console.error('Reset failed:', result.message)
          }
        } catch (error) {
          console.error('Failed to reset:', error)
        }
      },
      danger: true
    })

    // Add "Reset to this commit (include it)" option
    items.push({
      label: 'Reset to this commit (include it)',
      icon: '↩️',
      action: async () => {
        const confirmed = await showConfirm({
          title: `Reset to before commit ${commit.hash.slice(0, 8)}?`,
          message: `This will undo ${commitsToUndo + 1} commit(s).\nChanges will be kept in working directory.`,
          confirmText: 'Reset',
          cancelText: 'Cancel',
          danger: true
        })

        if (!confirmed) {
          closeContextMenu()
          return
        }

        closeContextMenu()
        try {
          const result = await gitApi.resetToCommit(taskId.value, commit.hash, true)
          if (result.success) {
            await loadCommits()
            await loadChangedFiles()
          } else {
            console.error('Reset failed:', result.message)
          }
        } catch (error) {
          console.error('Failed to reset:', error)
        }
      },
      danger: true
    })
  }

  return items
})

const copyPathToClipboard = async (path: string) => {
  try {
    await navigator.clipboard.writeText(path)
    console.log('Copied to clipboard:', path)
  } catch {
    const textArea = document.createElement('textarea')
    textArea.value = path
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
    console.log('Copied to clipboard (fallback):', path)
  }
}

// Touch handlers for Changed Files context menu
let changedFilesTouchTimer: ReturnType<typeof setTimeout> | null = null

const handleChangedFilesTouchStart = (e: TouchEvent, filePath: string) => {
  changedFilesTouchTimer = setTimeout(() => {
    handleShowContextMenu({
      x: e.touches[0].clientX,
      y: e.touches[0].clientY,
      path: filePath,
      type: 'file',
      source: 'changedFiles'
    })
  }, 500)
}

const handleChangedFilesTouchEnd = () => {
  if (changedFilesTouchTimer) {
    clearTimeout(changedFilesTouchTimer)
    changedFilesTouchTimer = null
  }
}

const handleChangedFilesTouchMove = () => {
  if (changedFilesTouchTimer) {
    clearTimeout(changedFilesTouchTimer)
    changedFilesTouchTimer = null
  }
}

const loadCommitDiff = async (commitHash: string) => {
  loadingCommitDiff.value = true
  commitDiffError.value = ''
  selectedCommitHash.value = commitHash
  currentFile.value = null  // Clear file context

  // Find commit message from commits list for header display
  const commitInfo = commits.value.find(c => c.hash === commitHash)
  selectedCommitMessage.value = commitInfo?.message || ''

  try {
    console.log('[DEBUG] Loading commit diff for:', commitHash)
    console.log('[DEBUG] taskId:', taskId.value)
    // The CommitDiffView component handles lazy loading internally
    editorMode.value = 'commit-diff'

    // Close sidebar on mobile
    if (isMobile.value) {
      showFileList.value = false
    }
  } catch (err: any) {
    console.error('[DEBUG] Failed to load commit diff:', err)
    console.error('[DEBUG] Error details:', err.message, err.stack)
    commitDiffError.value = err.message || 'Failed to load commit diff'
  }

  loadingCommitDiff.value = false
}

const closeCommitDiff = () => {
  selectedCommitHash.value = null
  selectedCommitMessage.value = ''
  commitDiffError.value = ''
  editorMode.value = 'editor'
}

const computeCommitsHash = (commits: CommitInfo[]): string => {
  return commits.map(c => c.hash).sort().join(',')
}

const isNewCommitData = (newCommits: CommitInfo[]): boolean => {
  const newHash = computeCommitsHash(newCommits)
  const changed = newHash !== lastCommitsHash.value
  lastCommitsHash.value = newHash
  return changed
}

const getNewCommitHashes = (newCommits: CommitInfo[]): Set<string> => {
  if (!lastCommitsHash.value) {
    return new Set()  // First load, no highlights
  }
  const oldHashes = lastCommitsHash.value.split(',')
  return new Set(newCommits.map(c => c.hash).filter(h => !oldHashes.includes(h)))
}

// Auto-refresh
let refreshTimer: number | null = null
let refreshAllTasksTimer: number | null = null

const startRefresh = () => {
  refreshTimer = window.setInterval(() => {
    if (!isLanMode()) return  // 非局域网跳过本次刷新
    loadChangedFiles()
    refreshCurrentTaskStatus()  // Update current task status display
    loadCommits(true)   // Silent refresh, no loading spinner
  }, 15000)  // Changed from 5000 to 15000 (15 seconds)

  // Refresh all tasks status every 30 seconds
  refreshAllTasksTimer = window.setInterval(() => {
    if (!isLanMode()) return
    refreshAllTasksStatus()
  }, 30000)
}

const stopRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  if (refreshAllTasksTimer) {
    clearInterval(refreshAllTasksTimer)
    refreshAllTasksTimer = null
  }
}

onMounted(async () => {
  console.log('[Layout Debug] onMounted started')
  checkMobile()
  window.addEventListener('resize', checkMobile)
  window.addEventListener('keydown', handleGlobalKeydown)

  // Load project
  const project = await projectsApi.get(projectId.value)
  store.setCurrentProject(project)

  // Determine task: from URL query or default Direct task
  let targetTaskId = route.query.task as string

  if (!targetTaskId) {
    // Auto-select: load tasks, find Direct task
    tasksLoading.value = true
    try {
      tasks.value = await tasksApi.list(projectId.value)
      const directTask = tasks.value.find(t => t.direct_on_branch)
      const fallbackTask = tasks.value[0]
      targetTaskId = directTask?.id || fallbackTask?.id
      if (targetTaskId) {
        router.replace({ query: { task: targetTaskId } })
      }
    } finally {
      tasksLoading.value = false
    }
  }

  if (targetTaskId) {
    loadLayout(targetTaskId)
    await loadTask(targetTaskId)
    loadFileTree()
    loadChangedFiles().then(() => { initialLoading.value = false })
    loadCommits()
    refreshCurrentTaskStatus()
    refreshAllTasksStatus()
    startRefresh()
  }

  // Setup ResizeObserver after layout is loaded (splitpanes are rendered)
  // This allows us to calculate terminal percentage from pixel width
  const setupResizeObserver = () => {
    if (editorSplitpanesRef.value?.$el) {
      let isFirstMeasurement = true

      const updateEditorContainerWidth = () => {
        if (editorSplitpanesRef.value?.$el) {
          const oldWidth = editorContainerWidth.value
          editorContainerWidth.value = editorSplitpanesRef.value.$el.offsetWidth
          console.log('[Layout Debug] Editor container width updated', editorContainerWidth.value)

          // On first measurement with saved terminal size, apply it to splitpanes
          // This fixes the timing issue where terminalPercent was 0 when editorContainerWidth was 0
          if (isFirstMeasurement && oldWidth === 0 && editorContainerWidth.value > 0 && layout.value.terminalPx > 0) {
            isFirstMeasurement = false
            const editorPanes = (editorSplitpanesRef.value as any)?.panes
            if (editorPanes && editorPanes.length >= 2 && showTerminal.value) {
              const terminalPercentValue = Math.max(10, Math.min(90, (layout.value.terminalPx / editorContainerWidth.value) * 100))
              editorPanes[0].size = 100 - terminalPercentValue
              editorPanes[1].size = terminalPercentValue
              console.log('[Layout Debug] Applied saved terminal size on first measurement', {
                terminalPx: layout.value.terminalPx,
                percent: terminalPercentValue
              })
            }
          }
        }
      }

      // Initial measurement
      updateEditorContainerWidth()

      // Setup ResizeObserver for continuous tracking
      const resizeObserver = new ResizeObserver(() => {
        updateEditorContainerWidth()
      })
      resizeObserver.observe(editorSplitpanesRef.value.$el)
      // Store observer for cleanup
      window.__editorResizeObserver = resizeObserver
      console.log('[Layout Debug] ResizeObserver setup complete')
    } else {
      // Retry after a short delay if splitpanes not ready
      console.log('[Layout Debug] editorSplitpanesRef not ready, retrying...')
      setTimeout(setupResizeObserver, 100)
    }
  }

  // Start setting up ResizeObserver after a delay to ensure layout is loaded
  setTimeout(setupResizeObserver, 300)

  console.log('[Layout Debug] onMounted completed')
})

// Global keyboard handler for Ctrl+P, Ctrl+S, and Alt+Left/Right for history navigation
const handleGlobalKeydown = (e: KeyboardEvent) => {
  // Alt+Left/Right for history navigation
  if (e.altKey && e.key === 'ArrowLeft') {
    e.preventDefault()
    navigateHistory('backward')
    return
  }
  if (e.altKey && e.key === 'ArrowRight') {
    e.preventDefault()
    navigateHistory('forward')
    return
  }

  // Ctrl+P for quick jump
  if (e.ctrlKey && e.key === 'p') {
    e.preventDefault()
    showFileQuickJump.value = true
    return
  }
  // Ctrl+S for conflict mode save
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    if (editorMode.value === 'conflict' && fileContent.value !== originalContent.value) {
      e.preventDefault()
      saveConflictFile()
    }
  }
}

/**
 * Get the view state for the currently active view
 * Returns the appropriate EditorViewState based on activeView
 */
const getActiveViewState = (): Ref<EditorViewState> => {
  if (activeView.value === 'preview1') return preview1State
  if (activeView.value === 'preview2') return preview2State
  return mainEditorState
}

/**
 * Navigate through file history in the active view
 * @param direction 'backward' or 'forward'
 */
const navigateHistory = (direction: 'backward' | 'forward') => {
  const viewState = getActiveViewState()

  // Need at least one file in history to navigate
  if (!viewState.value.filePath || viewState.value.history.length === 0) {
    return
  }

  // Find current index in history
  const currentIndex = viewState.value.history.findIndex(h => h.filePath === viewState.value.filePath)

  // If current file not in history, cannot navigate
  if (currentIndex === -1) {
    return
  }

  // Calculate target index with wrap-around
  let targetIndex: number
  if (direction === 'backward') {
    targetIndex = currentIndex > 0 ? currentIndex - 1 : viewState.value.history.length - 1
  } else {
    targetIndex = currentIndex < viewState.value.history.length - 1 ? currentIndex + 1 : 0
  }

  // Get the target entry and load it
  const entry = viewState.value.history[targetIndex]
  if (entry) {
    loadFileInView(entry.filePath, viewState, entry)
  }
}

/**
 * Load a file in the specified view and restore position
 * @param filePath The file path to load
 * @param viewState The view state to update
 * @param entry The history entry with position to restore
 */
const loadFileInView = async (filePath: string, viewState: Ref<EditorViewState>, entry: HistoryEntry) => {
  // For main view, use the existing loadFile function
  if (activeView.value === 'main') {
    await loadFile(filePath, 'editor')
    // Position will be restored by the watch on currentFile
    return
  }

  // For preview views, load file content directly into the preview state
  try {
    const result = await filesApi.read(taskId.value, filePath)
    viewState.value.filePath = filePath
    viewState.value.fileContent = result.content
    viewState.value.originalContent = result.content

    // Add to history if not already present
    addHistoryEntry(viewState.value, filePath)

    // Set the position data in viewState
    viewState.value.cursorPosition = entry.cursorPosition
    viewState.value.scrollPosition = entry.scrollPosition

    // Wait for EditorView to load the content, then restore position
    await nextTick()
    // Determine which preview ref to use based on viewState
    const previewRef = viewState === preview1State ? preview1Ref.value :
                       viewState === preview2State ? preview2Ref.value : null
    if (previewRef && viewState.value.cursorPosition) {
      // Convert 'line' to 'lineNumber' for EditorView.restorePosition
      previewRef.restorePosition({
        cursorPosition: {
          lineNumber: viewState.value.cursorPosition.line,
          column: viewState.value.cursorPosition.column
        },
        scrollPosition: viewState.value.scrollPosition
      })
    }
  } catch (err: any) {
    console.error('Failed to load file in preview:', err.message)
  }
}

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  window.removeEventListener('keydown', handleGlobalKeydown)
  stopRefresh()
  // Clean up ResizeObserver
  if (window.__editorResizeObserver) {
    window.__editorResizeObserver.disconnect()
    delete window.__editorResizeObserver
  }
  // Clean up banner timer
  if (directBranchBannerTimer) clearTimeout(directBranchBannerTimer)
  // Clean up image preview URL
  if (imagePreviewUrl.value) {
    URL.revokeObjectURL(imagePreviewUrl.value)
  }
  // Close persistent terminal connection when leaving the page
  if (taskId.value) {
    closePersistentConnection(taskId.value)
  }
})
</script>

<template>
  <div class="h-dvh flex flex-col overflow-hidden">
    <!-- Full-screen loading overlay -->
    <div v-if="!layoutLoaded" class="fixed inset-0 z-50 flex items-center justify-center bg-main">
      <div class="spinner w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- Header -->
    <header class="bg-main border-b border-main">
      <div class="max-w-full mx-auto px-3 sm:px-4 lg:px-6 py-1 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <button @click="goBackToTasks()" class="text-gray-500 hover:text-gray-700 dark:text-dark-500 dark:hover:text-dark-300">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h1 class="text-lg font-semibold text-main hidden md:block">{{ task?.name || 'Task' }}</h1>
        </div>
        <div class="flex items-center gap-2">
          <!-- File list button (mobile only) -->
          <button
            @click="toggleFileList"
            class="md:hidden p-1.5 rounded-lg hover:bg-sub"
            title="Files"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          </button>
          <button
            @click="toggleTerminal"
            class="p-1.5 rounded-lg hover:bg-sub"
            title="Terminal"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </button>
          <button @click="cycleTheme" class="p-1.5 rounded-lg hover:bg-sub" title="Cycle theme">
            <!-- Sun icon for light theme -->
            <svg v-if="theme === 'light'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            <!-- Moon icon for dark theme -->
            <svg v-else-if="theme === 'dark'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
            <!-- Leaf icon for green theme -->
            <svg v-else-if="theme === 'green'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
            </svg>
            <!-- Document icon for parchment theme -->
            <svg v-else-if="theme === 'parchment'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-amber-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </button>
          <GlobalTerminalIcon />
          <button @click="showSettingsModal = true" class="p-1.5 rounded-lg hover:bg-sub" title="Settings">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
        </div>
      </div>
    </header>

    <!-- Main content -->
    <splitpanes v-if="layoutLoaded" ref="mainSplitpanesRef" class="default-theme flex-1 min-h-0 flex" @resize="handleMainResize">
      <!-- Sidebar pane -->
      <pane v-if="!isMobile || showFileList" :size="isMobile && showFileList ? 100 : layout.sidebar" :min-size="isMobile && showFileList ? 100 : 10">
        <splitpanes ref="sidebarSplitpanesRef" horizontal class="default-theme h-full" @resize="handleSidebarResize">
          <!-- File tree -->
          <pane :size="layout.filesPane" :min-size="5" class="flex flex-col min-h-0 bg-main border-r border-main">
            <div class="flex-[1] p-4 border-b border-main min-h-0 flex flex-col">
              <div class="flex items-center justify-between mb-2">
                <div class="flex gap-1">
                  <button
                    @click="activeFilesTab = 'files'"
                    :class="activeFilesTab === 'files' ? 'tab-active' : 'border-transparent text-sub hover:text-main'"
                    class="text-sm font-medium px-2 py-1 border-b-2"
                  >
                    Files
                  </button>
                  <button
                    @click="activeFilesTab = 'referer'"
                    :class="activeFilesTab === 'referer' ? 'tab-active' : 'border-transparent text-sub hover:text-main'"
                    class="text-sm font-medium px-2 py-1 border-b-2"
                  >
                    Refer
                  </button>
                </div>
                <button v-if="activeFilesTab === 'files'" @click="loadFileTree()" class="text-gray-500 hover:text-gray-700 dark:text-dark-500 dark:hover:text-dark-300" title="Refresh">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </button>
              </div>
              <div class="relative flex-1 min-h-0">
                <div v-if="loadingFiles && activeFilesTab === 'files'" class="flex items-center justify-center py-4 absolute inset-0 z-10 bg-main">
                  <div class="spinner"></div>
                </div>
                <div class="file-tree text-sm absolute inset-0 overflow-y-auto" v-show="activeFilesTab === 'files'" @click="closeContextMenuOnClick">
                  <FileTreeItem
                    v-for="path in rootPaths"
                    :key="path"
                    :path="path"
                    :level="0"
                    @toggle="toggleDir"
                    @select-file="loadFile"
                    @preview-file="handleFilePreview"
                    @show-context-menu="handleShowContextMenu"
                  />
                  <div v-if="rootPaths.length === 0" class="text-xs text-sub py-2">No files found (rootPaths empty)</div>
                </div>
                <div class="absolute inset-0 overflow-y-auto" v-show="activeFilesTab === 'referer'">
                  <RefererSearch
                    :task-id="taskId"
                    :worktree-path="task?.worktree_path || ''"
                    :current-file="currentFile || ''"
                    :query="refererQuery"
                    :results="refererResults"
                    :total="refererTotal"
                    :total-matches="refererTotalMatches"
                    :page="refererPage"
                    :expanded-files="refererExpandedFiles"
                    @update:query="refererQuery = $event"
                    @update:results="refererResults = $event"
                    @update:total="refererTotal = $event"
                    @update:total-matches="refererTotalMatches = $event"
                    @update:page="refererPage = $event"
                    @update:expanded-files="refererExpandedFiles = $event"
                    @select-file="handleSearchSelect"
                    @preview-file="handleFilePreviewWithLine"
                  />
                </div>
              </div>
            </div>
          </pane>

          <!-- Changes / Commits tabbed pane -->
          <pane :size="layout.tabbedPane" :min-size="15" class="flex flex-col min-h-0 bg-main border-r border-main">
            <!-- Tab bar: tabs left, action buttons right -->
            <div class="flex items-center justify-between mb-2 shrink-0">
              <div class="flex gap-1">
                <button
                  @click="activeTab = 'changes'"
                  :class="activeTab === 'changes' ? 'tab-active' : 'border-transparent text-sub hover:text-main'"
                  class="text-sm font-medium px-2 py-1 border-b-2"
                >
                  Changes ({{ changedFiles.length }})
                </button>
                <button
                  @click="activeTab = 'commits'"
                  :class="activeTab === 'commits' ? 'tab-active' : 'border-transparent text-sub hover:text-main'"
                  class="text-sm font-medium px-2 py-1 border-b-2"
                >
                  Commits
                </button>
              </div>
              <!-- Accept button: visible in changes tab -->
              <button
                v-if="activeTab === 'changes'"
                @click="openCommitMessageModal"
                :disabled="accepting"
                :class="['p-1.5 rounded-lg hover:bg-sub', { 'pointer-events-none opacity-60 cursor-not-allowed': accepting }]"
                title="Accept"
              >
                <span v-if="accepting" class="spinner w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full"></span>
                <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
              </button>
              <!-- Merge button: visible in commits tab, not direct_on_branch -->
              <button
                v-if="activeTab === 'commits' && !task?.direct_on_branch"
                @click="mergeTask"
                :disabled="syncing"
                :class="['p-1.5 rounded-lg hover:bg-sub', { 'pointer-events-none opacity-60 cursor-not-allowed': syncing }]"
                title="Merge"
              >
                <span v-if="syncing" class="spinner w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full"></span>
                <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </button>
            </div>

            <!-- Tab content -->
            <div class="flex-1 overflow-y-auto min-h-0">
              <!-- Changes tab -->
              <div v-if="activeTab === 'changes'" class="changed-files-list p-4 min-h-full">
                <div v-if="initialLoading" class="flex items-center justify-center py-4">
                  <div class="spinner"></div>
                </div>
                <div v-else-if="changedFiles.length === 0" class="text-xs text-sub py-2">
                  No changes detected
                </div>
                <div v-else class="space-y-1" @click="closeContextMenuOnClick">
                  <div
                    v-for="file in changedFiles"
                    :key="file.path"
                    @click="loadFile(file.path, 'diff')"
                    @contextmenu.prevent.stop="(e) => handleShowContextMenu({ x: e.clientX, y: e.clientY, path: file.path, type: 'file', source: 'changedFiles' })"
                    @touchstart="(e) => handleChangedFilesTouchStart(e, file.path)"
                    @touchend="handleChangedFilesTouchEnd"
                    @touchmove="handleChangedFilesTouchMove"
                    :class="['text-xs px-2 py-1 rounded cursor-pointer hover:bg-sub flex items-center justify-between gap-2', currentFile === file.path && editorMode === 'diff' ? 'item-selected' : '']"
                    :title="file.path"
                  >
                    <span :class="['truncate flex-1', currentFile === file.path && editorMode === 'diff' ? 'text-main font-medium' : 'text-green-600 dark:text-green-400']">{{ file.path }}</span>
                    <span class="px-1.5 py-0.5 rounded text-xs font-mono font-medium min-w-[20px] text-center flex-shrink-0"
                      :class="{
                        'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400': file.status === 'A',
                        'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400': file.status === 'M',
                        'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400': file.status === 'D',
                        'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400': file.status === 'R',
                        'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400': file.status === 'C',
                        'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400': file.status === 'U',
                        'bg-gray-100 text-gray-700 dark:bg-gray-700/30 dark:text-gray-400': file.status === 'T',
                        'bg-gray-50 text-gray-500 dark:bg-gray-800/30 dark:text-gray-500': file.status === '?'
                      }">{{ file.status }}</span>
                  </div>
                </div>
                <Pagination
                  v-if="changedFilesData && changedFilesData.total > 20"
                  :total="changedFilesData.total"
                  :page="changedFilesData.page"
                  :page-size="changedFilesData.page_size"
                  :total-pages="changedFilesData.total_pages"
                  @page-change="handleChangedFilesPageChange"
                />
              </div>

              <!-- Commits tab -->
              <div v-else class="flex-[1] p-4 min-h-full">
                <CommitsList
                  :commits="commits"
                  :loading="loadingCommits"
                  :error="commitsError"
                  :lastMergeCommitHash="task?.last_merge_commit_hash"
                  :newCommitHashes="newCommitHashes"
                  @select="loadCommitDiff"
                  @showContextMenu="handleCommitContextMenu"
                />
                <Pagination
                  v-if="commitsData"
                  :total="commitsData.total"
                  :page="commitsData.page"
                  :page-size="commitsData.page_size"
                  :total-pages="commitsData.total_pages"
                  @page-change="handlePageChange"
                />
              </div>
            </div>
          </pane>

          <!-- Task List pane -->
          <pane :size="layout.tasksPane" :min-size="10" class="flex flex-col min-h-0 bg-main border-r border-main">
            <div class="p-4 flex-1 overflow-y-auto min-h-0">
              <div class="flex items-center justify-between mb-2">
                <h3 class="text-sm font-semibold text-main">Tasks</h3>
                <button @click="showCreateDialog = true" class="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-500">+ New</button>
              </div>

              <div v-if="tasksLoading" class="flex items-center justify-center py-4">
                <div class="spinner"></div>
              </div>
              <div v-else-if="tasks.length === 0" class="text-xs text-sub py-2 text-center">
                No tasks
              </div>
              <div v-else class="space-y-1">
                <div
                  v-for="task in tasks"
                  :key="task.id"
                  @click="switchTask(task.id)"
                  :class="[
                    'px-2 py-1.5 rounded cursor-pointer text-sm flex items-center gap-2',
                    task.id === taskId ? 'task-item-selected' : 'hover:bg-sub text-sub'
                  ]"
                >
                  <span class="truncate flex-1">{{ task.name }}<span v-if="task.code_status === 'pending_review'" class="text-yellow-500 text-xs ml-1">(review)</span><span v-else-if="task.code_status === 'ready_to_merge'" class="text-green-500 text-xs ml-1">(merge)</span></span>
                  <span v-if="task.direct_on_branch" class="badge-direct px-1 py-0.5 text-xs rounded shrink-0">Direct</span>
                  <button
                    v-if="!task.direct_on_branch"
                    @click="deleteTask(task.id, $event)"
                    class="task-delete-btn"
                    title="Delete task"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                  <span :class="task.task_status === 'running' ? 'text-green-600 dark:text-green-400' : 'text-gray-400'">
                    {{ task.task_status === 'running' ? '🟢' : '⚪' }}
                  </span>
                </div>
              </div>
            </div>
          </pane>
        </splitpanes>
      </pane>

      <!-- Editor pane -->
      <pane v-if="!isMobile || !showFileList"
            :size="(isMobile && showFileList) ? 0 : (isMobile ? 100 : (100 - layout.sidebar))"
            :min-size="(isMobile && showFileList) ? 0 : 20">
        <splitpanes ref="editorSplitpanesRef" vertical class="default-theme h-full min-h-0" @resize="handleEditorResize">
          <pane :size="mainEditorPercent" :min-size="10" class="flex flex-col min-h-0">
            <!-- Editor area -->
            <main class="flex-1 flex flex-col overflow-hidden bg-main">
              <!-- Editor header -->
              <div v-if="currentFile || selectedCommitHash || imagePreviewFile" class="bg-sub border-b border-main px-4 py-1 flex items-center gap-2 min-h-[32px]">
                <div class="text-sm text-sub flex items-center gap-2 min-w-0 flex-1 truncate">
                  <span v-if="imagePreviewFile" class="text-base shrink-0">🖼️</span>
                  <span v-else-if="editorMode === 'commit-diff'" class="text-base shrink-0">📋</span>
                  <span v-else-if="editorMode === 'conflict'" class="text-base shrink-0">⚠️</span>
                  <span v-else-if="editorMode === 'deleted'" class="text-base shrink-0">🗑️</span>
                  <span v-else-if="editorMode === 'diff'" class="text-base shrink-0">🔄</span>
                  <span v-else class="text-base shrink-0">📝</span>
                  <span v-if="imagePreviewFile" class="truncate">
                    {{ imagePreviewFile }}
                  </span>
                  <span v-else-if="editorMode === 'commit-diff' && selectedCommitHash" class="truncate">
                    Commit: {{ selectedCommitHash.slice(0, 8) }} - {{ selectedCommitMessage }}
                  </span>
                  <span v-else class="truncate">
                    {{ currentFile }}{{ isFileDeleted ? ' (deleted)' : '' }}{{ editorMode === 'conflict' ? ' (conflict)' : '' }}
                  </span>
                </div>
                <div class="flex items-center gap-1.5 shrink-0">
                  <span v-if="savingContent" class="spinner-xs"></span>
                  <button
                    v-if="editorMode === 'diff'"
                    @click="goToPrevDiff"
                    :disabled="!diffEditorRef?.hasDiffs"
                    :class="['p-1.5 rounded-lg hover:bg-sub', { 'pointer-events-none opacity-60 cursor-not-allowed': !diffEditorRef?.hasDiffs }]"
                    title="Jump to previous change"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18" />
                    </svg>
                  </button>
                  <button
                    v-if="editorMode === 'diff'"
                    @click="goToNextDiff"
                    :disabled="!diffEditorRef?.hasDiffs"
                    :class="['p-1.5 rounded-lg hover:bg-sub', { 'pointer-events-none opacity-60 cursor-not-allowed': !diffEditorRef?.hasDiffs }]"
                    title="Jump to next change"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                    </svg>
                  </button>
                  <button
                    v-if="editorMode === 'commit-diff'"
                    @click="closeCommitDiff"
                    class="p-1.5 rounded-lg hover:bg-sub"
                    title="Close"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                  <button
                    v-if="editorMode === 'editor' && (fileContent !== originalContent || savingContent)"
                    @click="saveFile"
                    :disabled="savingContent"
                    :class="['p-1.5 rounded-lg hover:bg-sub', { 'pointer-events-none opacity-60 cursor-not-allowed': savingContent }]"
                    title="Save"
                  >
                    <span v-if="savingContent" class="spinner w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full"></span>
                    <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                    </svg>
                  </button>
                  <button
                    v-if="editorMode === 'conflict'"
                    @click="saveConflictFile"
                    :disabled="savingContent"
                    :class="['p-1.5 rounded-lg hover:bg-sub', { 'pointer-events-none opacity-60 cursor-not-allowed': savingContent }]"
                    title="Save"
                  >
                    <span v-if="savingContent" class="spinner w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full"></span>
                    <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                    </svg>
                  </button>
                  <button
                    v-if="isMarkdownFile && editorMode === 'editor'"
                    @click="openMarkdownPreview"
                    class="p-1.5 rounded-lg hover:bg-sub"
                    title="Preview Markdown"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-sub" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  </button>
                </div>
              </div>

              <!-- Editor Content -->
              <div class="flex flex-col flex-1 overflow-hidden relative">
                <!-- Loading state -->
                <div v-if="loadingContent || loadingCommitDiff" class="flex items-center justify-center h-full">
                  <div class="spinner"></div>
                </div>

                <!-- Empty state -->
                <div v-else-if="!currentFile && !selectedCommitHash && !pdfPromptFile && !imagePreviewFile" class="flex items-center justify-center h-full text-sub">
                  Select a file to edit
                </div>

                <!-- PDF File Prompt -->
                <div v-else-if="pdfPromptFile" class="flex flex-col items-center justify-center h-full text-gray-400 dark:text-gray-500">
                  <div class="text-6xl mb-4">📄</div>
                  <div class="text-lg mb-2 max-w-md truncate" :title="pdfPromptFile">{{ pdfPromptFile }}</div>
                  <div class="text-sm mb-4 text-center">
                    This is a PDF file.<br/>
                    Open in browser to view.
                  </div>

                  <!-- Progress bar -->
                  <div v-if="openingPdf && pdfDownloadProgress" class="w-64 mb-4">
                    <div class="flex justify-between text-xs mb-1">
                      <span>{{ formatFileSize(pdfDownloadProgress.loaded) }}</span>
                      <span v-if="pdfDownloadProgress.total > 0">
                        {{ Math.round(pdfDownloadProgress.loaded / pdfDownloadProgress.total * 100) }}%
                      </span>
                    </div>
                    <div class="w-full bg-gray-700 dark:bg-gray-600 rounded-full h-2">
                      <div
                        class="bg-blue-500 h-2 rounded-full transition-all duration-200"
                        :style="{ width: pdfDownloadProgress.total > 0 ? `${(pdfDownloadProgress.loaded / pdfDownloadProgress.total * 100)}%` : '0%' }"
                      ></div>
                    </div>
                    <div v-if="pdfDownloadProgress.total > 0" class="text-xs text-center mt-1">
                      {{ formatFileSize(pdfDownloadProgress.loaded) }} / {{ formatFileSize(pdfDownloadProgress.total) }}
                    </div>
                  </div>

                  <div v-if="pdfError" class="text-red-500 text-sm mb-2">{{ pdfError }}</div>
                  <div class="flex gap-2">
                    <button
                      @click="openPdfInBrowser"
                      :disabled="openingPdf"
                      class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 disabled:opacity-50"
                    >
                      {{ openingPdf ? 'Opening...' : 'Open in Browser' }}
                    </button>
                    <button
                      @click="closePdfPrompt"
                      :disabled="openingPdf"
                      class="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 dark:bg-gray-500 dark:hover:bg-gray-600 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>

                <!-- Image Preview -->
                <div v-else-if="imagePreviewFile" class="flex flex-col items-center justify-center h-full bg-main p-4">
                  <div v-if="loadingImage" class="flex flex-col items-center gap-2">
                    <div class="spinner"></div>
                    <span class="text-sm text-sub">Loading image...</span>
                  </div>
                  <template v-else-if="imagePreviewUrl">
                    <img
                      :src="imagePreviewUrl"
                      :alt="imagePreviewFile"
                      class="max-w-full max-h-full object-contain rounded shadow-lg"
                    />
                    <div class="mt-2 text-xs text-sub truncate max-w-md" :title="imagePreviewFile">
                      {{ imagePreviewFile.split('/').pop() }}
                    </div>
                  </template>
                  <div v-else-if="imageError" class="flex flex-col items-center gap-2 text-red-500">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <span>{{ imageError }}</span>
                    <button @click="loadImagePreview(imagePreviewFile)" class="mt-2 px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700">
                      Retry
                    </button>
                  </div>
                </div>

                <!-- Commit Diff View -->
                <CommitDiffView
                  v-else-if="editorMode === 'commit-diff' && selectedCommitHash"
                  :task-id="taskId"
                  :commit-hash="selectedCommitHash"
                />

                <!-- File Diff Editor -->
                <div v-else-if="editorMode === 'diff' && currentFile" class="flex flex-col flex-1 min-h-0">
                  <MonacoDiffEditor
                    ref="diffEditorRef"
                    :original="originalContent"
                    :modified="fileContent"
                    :path="currentFile"
                    :read-only="true"
                    :is-mobile="isMobile"
                    class="min-h-0"
                    @cursor-word="handleCursorWord"
                  />
                  <SymbolOutline
                    ref="outlineRef"
                    v-if="isSupportedFileType"
                    :symbols="symbols"
                    :collapsed="outlineCollapsed"
                    :preview-collapsed="previewCollapsed"
                    :show-previews="showPreviews && !isMobile"
                    :task-id="taskId"
                    :current-file-path="currentFile || ''"
                    class="flex-shrink-0"
                    @select="handleSymbolSelect"
                    @toggle="handleOutlineToggle"
                    @preview-toggle="handlePreviewToggle"
                    @toggle-preview-panes="handleTogglePreviewPanes"
                    @navigate="handleSymbolNavigate"
                  />
                </div>

                <!-- Regular Editor -->
                <div v-else-if="editorMode === 'editor' && currentFile" class="flex flex-col flex-1 min-h-0">
                  <MonacoEditor
                    ref="editorRef"
                    v-model="fileContent"
                    :path="currentFile"
                    :enable-save-shortcut="fileContent !== originalContent && !savingContent"
                    :is-mobile="isMobile"
                    class="min-h-0"
                    @save="saveFile"
                    @preview-markdown="openMarkdownPreview"
                    @content-change="handleContentChange"
                    @cursor-word="handleCursorWord"
                    @find-references="handleFindReferences"
                  />
                  <SymbolOutline
                    ref="outlineRef"
                    v-if="isSupportedFileType"
                    :symbols="symbols"
                    :collapsed="outlineCollapsed"
                    :preview-collapsed="previewCollapsed"
                    :show-previews="showPreviews && !isMobile"
                    :task-id="taskId"
                    :current-file-path="currentFile || ''"
                    class="flex-shrink-0"
                    @select="handleSymbolSelect"
                    @toggle="handleOutlineToggle"
                    @preview-toggle="handlePreviewToggle"
                    @toggle-preview-panes="handleTogglePreviewPanes"
                    @navigate="handleSymbolNavigate"
                  />
                </div>

                <!-- Conflict Editor -->
                <div v-else-if="editorMode === 'conflict' && currentFile" class="flex flex-col flex-1 min-h-0">
                  <ConflictEditor
                    ref="conflictEditorRef"
                    :content="fileContent"
                    :path="currentFile"
                    :is-mobile="isMobile"
                    class="min-h-0"
                    @update:content="handleConflictContentUpdate"
                    @resolved="handleConflictResolved"
                    @save="saveConflictFile"
                  />
                </div>

                <!-- Deleted File Editor (read-only) -->
                <MonacoEditor
                  v-else-if="editorMode === 'deleted' && currentFile"
                  v-model="fileContent"
                  :path="currentFile"
                  :read-only="true"
                  :is-mobile="isMobile"
                />
              </div>

              <!-- Error message -->
              <div v-if="saveError" class="bg-red-50 dark:bg-red-900/20 border-t border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-600 dark:text-red-400">
                {{ saveError }}
              </div>
            </main>
          </pane>

          <!-- Terminal pane - always rendered to keep WebSocket alive, size=0 when hidden -->
          <pane v-if="!showFileList && !showPreviews" :size="showTerminal ? (isMobile ? 100 : terminalPercent) : 0" :min-size="showTerminal ? (isMobile ? 100 : 10) : 0" class="flex flex-col min-h-0">
            <div class="w-full bg-main border-l border-main flex-1 flex flex-col min-h-0">
              <Terminal :key="taskId" :task-id="taskId" />
            </div>
          </pane>

          <!-- Preview area - shows when showPreviews=true, replaces terminal -->
          <pane v-if="!showFileList && showPreviews && !isMobile" :size="previewPercent" :min-size="10" class="flex flex-col min-h-0">
            <splitpanes horizontal class="default-theme h-full min-h-0">
              <!-- Preview2 (top) -->
              <pane :size="preview2Percent" :min-size="10" class="flex flex-col min-h-0 bg-main border-l border-main">
                <div class="flex-1 min-h-0 overflow-hidden">
                  <EditorView
                    ref="preview2Ref"
                    viewType="preview2"
                    :filePath="preview2State.filePath"
                    :content="preview2State.fileContent"
                    :history="preview2State.history"
                  />
                </div>
              </pane>
              <!-- Preview1 (bottom) -->
              <pane :size="preview1Percent" :min-size="10" class="flex flex-col min-h-0 bg-main border-l border-main">
                <div class="flex-1 min-h-0 overflow-hidden">
                  <EditorView
                    ref="preview1Ref"
                    viewType="preview1"
                    :filePath="preview1State.filePath"
                    :content="preview1State.fileContent"
                    :history="preview1State.history"
                  />
                </div>
              </pane>
            </splitpanes>
          </pane>
        </splitpanes>
      </pane>
    </splitpanes>

    <!-- Context Menu -->
    <ContextMenu
      :show="contextMenu.show"
      :x="contextMenu.x"
      :y="contextMenu.y"
      :items="contextMenuItems"
      @close="closeContextMenu"
    />

    <!-- Hidden file input for upload -->
    <input
      ref="fileInputRef"
      type="file"
      multiple
      @change="handleFileSelect"
      class="hidden"
    />

    <!-- Upload progress modal -->
    <div v-if="uploadProgress.show"
         role="dialog"
         class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card max-w-md w-full">
        <h3 class="text-lg font-semibold text-main mb-4">Uploading Files</h3>

        <div class="space-y-4">
          <!-- Progress bar -->
          <div>
            <div class="flex items-center justify-between text-sm mb-2">
              <span class="text-sub">
                {{ uploadProgress.currentFile }}
              </span>
              <span class="text-muted">
                {{ uploadProgress.current }} / {{ uploadProgress.total }}
              </span>
            </div>
            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <div
                class="bg-blue-600 dark:bg-blue-400 h-2 rounded-full transition-all duration-200"
                :style="{ width: `${(uploadProgress.current / uploadProgress.total) * 100}%` }">
              </div>
            </div>
          </div>

          <!-- Cancel button -->
          <div class="flex justify-end">
            <button @click="cancelUpload" class="btn btn-secondary">
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Sync progress modal -->
    <div v-if="syncing"
         role="alertdialog"
         aria-labelledby="sync-modal-title"
         aria-describedby="sync-modal-description"
         class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card max-w-md w-full text-center">
        <div class="spinner mb-4" aria-hidden="true"></div>
        <h3 id="sync-modal-title" class="text-lg font-semibold text-main mb-2">Syncing with Main</h3>
        <p id="sync-modal-description" class="text-sub mb-4">{{ syncStep }}</p>
        <div class="text-sm text-sub space-y-1">
          <div :class="{ 'text-blue-600 dark:text-blue-400 font-semibold': syncStep.includes('Fetching') }">
            Step 1/2: Fetching latest changes...
          </div>
          <div :class="{ 'text-blue-600 dark:text-blue-400 font-semibold': syncStep.includes('Merging') }">
            Step 2/2: Merging main into worktree...
          </div>
        </div>
      </div>
    </div>

    <!-- Conflict resolution modal -->
    <!-- TODO: Add ESC key handler for modal dismissal (requires composable) -->
    <div v-if="hasConflicts && syncNeedsResolution"
         role="alertdialog"
         aria-labelledby="conflict-modal-title"
         aria-describedby="conflict-modal-description"
         class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card max-w-2xl w-full">
        <h3 id="conflict-modal-title" class="text-lg font-semibold text-red-600 dark:text-red-400 mb-2">
          ⚠️ Merge Conflicts Detected
        </h3>
        <p id="conflict-modal-description" class="text-sub mb-4">
          Main branch has changes that conflict with your work. Please resolve these conflicts before merging.
        </p>

        <h4 class="font-semibold text-main mb-2">
          Conflicted Files ({{ conflictedFiles.length }})
        </h4>
        <div class="space-y-1 max-h-64 overflow-y-auto mb-4 border border-main rounded-lg p-2">
          <div
            v-for="file in conflictedFiles"
            :key="file"
            @click="loadConflictedFile(file)"
            class="p-2 bg-sub rounded cursor-pointer hover:bg-tertiary flex items-center gap-2"
          >
            <span class="text-red-600 dark:text-red-400" aria-hidden="true">⚠️</span>
            <span class="text-sm font-mono">{{ file }}</span>
          </div>
        </div>

        <div class="flex justify-center">
          <button
            @click="dismissConflictModal"
            class="btn btn-primary"
          >
            Confirm
          </button>
        </div>
      </div>
    </div>

    <!-- Merge success dialog -->
    <div v-if="mergeSuccess" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card max-w-md w-full text-center">
        <div class="text-4xl mb-4">✅</div>
        <h3 class="text-lg font-semibold text-main mb-2">Merge Successful!</h3>
        <p class="text-sub mb-4">Your changes have been merged to the main branch.</p>
        <button @click="mergeSuccess = false" class="btn btn-primary">
          Confirm
        </button>
      </div>
    </div>

    <!-- Accept success toast -->
    <div v-if="acceptSuccess" class="fixed bottom-4 right-4 bg-green-100 dark:bg-green-900/20 border border-green-200 dark:border-green-800 px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 z-50">
      <span class="text-green-600 dark:text-green-400 text-xl">✓</span>
      <span class="text-green-700 dark:text-green-300 text-sm font-medium">Changes accepted and committed</span>
    </div>

    <!-- Merge error dialog -->
    <div v-if="mergeError && !syncNeedsResolution" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card max-w-2xl w-full max-h-[80vh] overflow-y-auto">
        <h3 class="text-lg font-semibold text-red-600 dark:text-red-400 mb-2">Merge Failed</h3>
        <p class="text-sub mb-4">{{ mergeError }}</p>
        <p class="text-sm text-sub mb-4" v-if="mergeError.includes('Main branch rolled back')">
          The main branch has been automatically rolled back to a clean state. Your worktree changes are safe.
        </p>

        <!-- Command execution log -->
        <div v-if="mergeExecutionLog && mergeExecutionLog.length > 0" class="mb-4">
          <div class="flex items-center justify-between mb-2">
            <h4 class="text-sm font-semibold text-sub">Command Execution Log</h4>
            <button
              @click="copyExecutionLog"
              class="text-xs px-3 py-1 bg-sub hover:bg-tertiary rounded text-sub"
            >
              Copy Log
            </button>
          </div>
          <div class="bg-gray-900 dark:bg-gray-950 rounded-lg p-4 text-xs font-mono overflow-x-auto max-h-64 overflow-y-auto">
            <div v-for="(cmd, index) in mergeExecutionLog" :key="index" class="mb-3 last:mb-0">
              <div class="flex items-start gap-2">
                <span class="text-green-500 dark:text-green-400 mt-0.5 flex-shrink-0">$</span>
                <div class="flex-1 min-w-0">
                  <div class="text-gray-300 dark:text-gray-300 break-words whitespace-pre-wrap">{{ cmd.command }}</div>
                  <div v-if="cmd.exit_code !== 0" class="text-red-400 dark:text-red-400 mt-1">
                    ✗ Exit code: {{ cmd.exit_code }}
                  </div>
                  <div v-if="cmd.stdout" class="text-gray-400 dark:text-gray-400 mt-1 whitespace-pre-wrap">{{ cmd.stdout }}</div>
                  <div v-if="cmd.stderr" class="text-red-400 dark:text-red-400 mt-1 whitespace-pre-wrap">{{ cmd.stderr }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="flex gap-3">
          <button @click="mergeError = ''; mergeExecutionLog = null; showTerminal = true" class="btn btn-secondary flex-1">
            Open Terminal
          </button>
          <button @click="mergeError = ''; mergeExecutionLog = null" class="btn btn-primary flex-1">
            Close
          </button>
        </div>
      </div>
    </div>

    <!-- Accept error dialog -->
    <div v-if="acceptError" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card max-w-lg w-full">
        <h3 class="text-lg font-semibold text-red-600 dark:text-red-400 mb-2">Accept Failed</h3>
        <p class="text-sub mb-4">{{ acceptError }}</p>
        <div class="flex gap-3">
          <button @click="acceptError = ''; showTerminal = true" class="btn btn-secondary flex-1">
            Open Terminal
          </button>
          <button @click="acceptError = ''" class="btn btn-primary flex-1">
            Close
          </button>
        </div>
      </div>
    </div>

    <!-- Merge commit message dialog -->
    <div v-if="showMergeDialog"
         role="dialog"
         aria-labelledby="merge-dialog-title"
         class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card max-w-md w-full">
        <h3 id="merge-dialog-title" class="text-lg font-semibold text-main mb-2">
          Merge Task
        </h3>

        <label for="merge-message" class="block text-sm font-medium text-sub mb-2">
          Commit Message
        </label>
        <input
          id="merge-message"
          v-model="mergeMessage"
          type="text"
          class="input w-full mb-4"
          placeholder="Describe changes for this merge"
          @keyup.enter="confirmMerge"
          ref="mergeInputRef"
        />

        <div class="flex gap-3 justify-end">
          <button
            @click="showMergeDialog = false"
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            @click="confirmMerge"
            class="btn btn-primary"
          >
            Merge
          </button>
        </div>
      </div>
    </div>

    <!-- Markdown Preview Modal -->
    <MarkdownPreviewModal
      :task-id="taskId"
      :file-path="markdownPreviewPath"
      :content="markdownPreviewContent"
      :show="showMarkdownPreview"
      @close="showMarkdownPreview = false"
    />

    <!-- File Quick Jump Modal -->
    <FileQuickJumpModal
      :task-id="taskId"
      :show="showFileQuickJump"
      @close="showFileQuickJump = false"
      @select-file="handleQuickJumpFileSelect"
    />

    <!-- Settings Modal -->
    <TaskSettingsModal
      v-if="showSettingsModal"
      :task-id="taskId"
      @close="showSettingsModal = false"
    />

    <!-- Commit Message Modal -->
    <div v-if="showCommitMessageModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card max-w-md w-full">
        <h3 class="text-lg font-semibold text-main mb-4">Accept Changes</h3>
        <p class="text-sm text-sub mb-3">Enter a commit message:</p>
        <textarea
          v-model="commitMessage"
          class="w-full h-24 p-3 border border-main rounded-lg bg-main text-main text-sm resize-none focus:outline-none focus:ring-2 focus:ring-accent"
          placeholder="Enter commit message..."
        ></textarea>
        <div class="flex justify-end gap-2 mt-4">
          <button
            @click="showCommitMessageModal = false"
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            @click="acceptChanges"
            :disabled="!commitMessage.trim()"
            :class="['btn btn-primary', { 'opacity-50 cursor-not-allowed': !commitMessage.trim() }]"
          >
            Accept
          </button>
        </div>
      </div>
    </div>

    <!-- Create task dialog -->
    <div v-if="showCreateDialog" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card max-w-md w-full">
        <h3 class="text-lg font-semibold text-main mb-4">Create New Task</h3>
        <form @submit.prevent="createTask" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-sub mb-2">Task Name *</label>
            <input v-model="newTaskName" type="text" class="input w-full" placeholder="Implement feature X" />
          </div>
          <div class="flex items-start gap-2">
            <input type="checkbox" id="newTaskDirect" v-model="newTaskDirectOnBranch" class="mt-1" />
            <label for="newTaskDirect" class="text-sm text-sub">
              <span class="font-medium text-main">Directly on the branch</span>
              <br />
              <span class="text-xs">Work directly on main branch, no worktree created.</span>
            </label>
          </div>
          <div v-if="createError" class="text-red-600 dark:text-red-400 text-sm">{{ createError }}</div>
          <div class="flex gap-3 justify-end">
            <button type="button" @click="showCreateDialog = false; newTaskDirectOnBranch = false" class="btn btn-secondary">Cancel</button>
            <button type="submit" :disabled="creatingTask" class="btn btn-primary">
              <span v-if="creatingTask" class="spinner mr-2"></span>Create
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Delete task confirmation dialog -->
    <div v-if="showDeleteConfirm" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" @click.self="cancelDeleteTask">
      <div class="card max-w-sm w-full">
        <h3 class="text-lg font-semibold text-red-600 dark:text-red-400 mb-2">Delete Task</h3>
        <p class="text-sub mb-6">
          Delete task "<span class="font-medium text-main">{{ deleteTargetTask?.name }}</span>"? This action cannot be undone.
        </p>
        <div class="flex gap-3">
          <button @click="cancelDeleteTask" class="btn btn-secondary flex-1">Cancel</button>
          <button @click="confirmDeleteTask" class="btn btn-danger flex-1">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// Type declaration for window property used by ResizeObserver
declare global {
  interface Window {
    __editorResizeObserver?: ResizeObserver
  }
}
export {}
</script>

<style>
/* Splitpanes pane background colors - use CSS variables for theme support */
.splitpanes.default-theme .splitpanes__pane {
  background-color: var(--bg-primary) !important;
}

/* Splitpanes separator customization - working with default-theme */
.splitpanes.default-theme .splitpanes__splitter {
  background-color: var(--border-color);
  border-color: var(--border-secondary);
  transition: none !important;
}

/* Make separators very subtle */
.splitpanes--vertical.default-theme > .splitpanes__splitter {
  width: 2px;
  border-left: 1px solid var(--border-secondary);
}

.splitpanes--horizontal.default-theme > .splitpanes__splitter {
  height: 2px;
  border-top: 1px solid var(--border-secondary);
}

/* Strong hover effect */
@media (hover: hover) {
  .splitpanes.default-theme .splitpanes__splitter:hover {
    background-color: var(--splitter-hover);
    border-color: var(--splitter-active);
  }
}

@media (hover: hover) {
  .splitpanes.default-theme .splitpanes__splitter:hover:before,
  .splitpanes.default-theme .splitpanes__splitter:hover:after {
    background-color: var(--splitter-handle);
  }
}

/* Active dragging state */
.splitpanes.default-theme.splitpanes--dragging .splitpanes__splitter {
  background-color: var(--splitter-active);
}

/* Disable all transitions and animations for panes */
.splitpanes.default-theme .splitpanes__pane {
  transition: none !important;
  animation: none !important;
}

/* Status badge styles - theme-aware using CSS variables */
.status-badge {
  @apply px-1.5 py-0.5 rounded text-xs font-mono font-medium min-w-[20px] text-center;
  flex-shrink: 0;
}

.status-a {
  background-color: var(--badge-added-bg);
  color: var(--badge-added-text);
}

.status-m {
  background-color: var(--badge-modified-bg);
  color: var(--badge-modified-text);
}

.status-d {
  background-color: var(--badge-deleted-bg);
  color: var(--badge-deleted-text);
}

.status-r {
  background-color: var(--badge-renamed-bg);
  color: var(--badge-renamed-text);
}

.status-c {
  background-color: var(--badge-copied-bg);
  color: var(--badge-copied-text);
}

.status-u {
  background-color: var(--badge-untracked-bg);
  color: var(--badge-untracked-text);
}

.status-t {
  background-color: var(--badge-typed-bg);
  color: var(--badge-typed-text);
}

.status-\? {
  background-color: var(--badge-typed-bg);
  color: var(--badge-typed-text);
}

/* Task delete button */
.task-delete-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  border: none;
  cursor: pointer;
  flex-shrink: 0;
  padding: 0;
  transition: all 0.15s;
}
@media (hover: hover) {
  .task-delete-btn:hover {
    background: rgba(239, 68, 68, 0.15);
    color: #dc2626;
  }
}
</style>

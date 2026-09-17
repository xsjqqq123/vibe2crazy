import { ref, computed, nextTick } from 'vue'
import { defineStore } from 'pinia'
import notebooksApi, {
  type Notebook,
  type NotebookDetail,
  type NotebookSearchResult,
  type NotebookTreeGroup,
  type MoveDirection
} from '@/api/notebooks'

export type EditorMode = 'edit' | 'split' | 'preview'

export const DEFAULT_GROUP_NAME = 'Unsorted'

const STALE_MESSAGE = 'This note was changed on disk by something else. Overwrite it with your version?'

const STORAGE_KEY = 'notebook_ui'
const AUTOSAVE_DELAY_MS = 1500
const SEARCH_DEBOUNCE_MS = 300

interface PersistedState {
  mode: EditorMode
  collapsedGroups: string[]
  lastNoteId: string | null
  sidebarVisible: boolean
}

interface SaveOptions {
  /** Asked when the file changed on disk underneath us. Resolve true to overwrite. */
  onConflict?: (message: string) => Promise<boolean>
}

export const useNotebookStore = defineStore('notebook', () => {
  // -- data --
  const groups = ref<NotebookTreeGroup[]>([])
  const currentNote = ref<NotebookDetail | null>(null)
  const editorContent = ref('')
  const mode = ref<EditorMode>('split')
  const isDirty = ref(false)
  const loading = ref(false)
  const saving = ref(false)
  const error = ref('')
  const root = ref('')

  // -- search --
  const searchQuery = ref('')
  const searchResults = ref<NotebookSearchResult[]>([])
  const searchTotal = ref(0)
  const searchTruncated = ref(false)
  const searching = ref(false)

  // -- ui state (persisted) --
  const collapsedGroups = ref<string[]>([])
  const lastNoteId = ref<string | null>(null)
  const sidebarVisible = ref(true)

  /** Set when an autosave lost the race with an external edit. */
  const conflictPending = ref(false)

  // -- internal --
  const positionCache: Record<string, { lineNumber: number; column: number }> = {}
  let saveTimer: ReturnType<typeof setTimeout> | null = null
  let searchTimer: ReturnType<typeof setTimeout> | null = null
  let searchSeq = 0

  // -- getters --
  const allNotes = computed<Notebook[]>(() => groups.value.flatMap((g) => g.notes))

  const currentGroupName = computed(() => currentNote.value?.group_name ?? '')

  const currentNoteId = computed(() => currentNote.value?.id ?? null)

  /** Groups in display order. Notes within each group are already ordered by the server. */
  const sortedGroups = computed(() =>
    [...groups.value].sort((a, b) => a.position - b.position)
  )

  function samePinnedBucket(note: Notebook) {
    return allNotes.value.filter((n) => n.group_id === note.group_id && n.pinned === note.pinned)
  }

  const canMoveUp = (note: Notebook) => samePinnedBucket(note)[0]?.id !== note.id

  const canMoveDown = (note: Notebook) => {
    const siblings = samePinnedBucket(note)
    return siblings[siblings.length - 1]?.id !== note.id
  }

  const movableGroups = computed(() => sortedGroups.value.filter((g) => !g.is_default))

  const canMoveGroupUp = (group: NotebookTreeGroup) =>
    !group.is_default && movableGroups.value[0]?.id !== group.id

  const canMoveGroupDown = (group: NotebookTreeGroup) =>
    !group.is_default && movableGroups.value[movableGroups.value.length - 1]?.id !== group.id

  // -- persistence --
  function load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const saved = JSON.parse(raw) as Partial<PersistedState>
      if (saved.mode) mode.value = saved.mode
      if (Array.isArray(saved.collapsedGroups)) collapsedGroups.value = saved.collapsedGroups
      if (saved.lastNoteId !== undefined) lastNoteId.value = saved.lastNoteId
      if (typeof saved.sidebarVisible === 'boolean') sidebarVisible.value = saved.sidebarVisible
    } catch (e) {
      console.warn('[Notebook] Failed to load UI state:', e)
    }
  }

  function save() {
    const state: PersistedState = {
      mode: mode.value,
      collapsedGroups: collapsedGroups.value,
      lastNoteId: lastNoteId.value,
      sidebarVisible: sidebarVisible.value
    }
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    } catch (e) {
      console.warn('[Notebook] Failed to save UI state:', e)
    }
  }

  function toggleCollapse(groupId: string) {
    const index = collapsedGroups.value.indexOf(groupId)
    if (index >= 0) collapsedGroups.value.splice(index, 1)
    else collapsedGroups.value.push(groupId)
    save()
  }

  function isCollapsed(groupId: string) {
    return collapsedGroups.value.includes(groupId)
  }

  function setMode(next: EditorMode) {
    mode.value = next
    save()
  }

  function toggleSidebar() {
    sidebarVisible.value = !sidebarVisible.value
    save()
  }

  // -- saving -----------------------------------------------------------
  // The dirty flag is only cleared once content is actually on disk, so a
  // failed write is retried rather than silently dropped.

  function cancelPendingSave() {
    if (saveTimer) {
      clearTimeout(saveTimer)
      saveTimer = null
    }
  }

  function scheduleSave() {
    isDirty.value = true
    cancelPendingSave()
    saveTimer = setTimeout(() => {
      saveTimer = null
      void flushSave()
    }, AUTOSAVE_DELAY_MS)
  }

  function applySaveResult(
    noteId: string,
    result: { mtime: number; size: number; hash: string }
  ) {
    if (currentNote.value?.id === noteId) {
      currentNote.value.mtime = result.mtime
      currentNote.value.size = result.size
      // Only a successful write may advance the token.
      currentNote.value.hash = result.hash
    }
  }

  /** Write pending edits. Returns false if anything is still unsaved. */
  async function flushSave(options: SaveOptions = {}): Promise<boolean> {
    cancelPendingSave()
    const note = currentNote.value
    if (!isDirty.value || !note) return true

    const content = editorContent.value
    saving.value = true
    try {
      const result = await notebooksApi.saveContent(note.id, content, note.hash)
      applySaveResult(note.id, result)
      isDirty.value = false
      error.value = ''
      return true
    } catch (e: any) {
      if (isStale(e)) {
        if (options.onConflict) {
          if (await options.onConflict(STALE_MESSAGE)) {
            return await forceSaveContent(note.id, content)
          }
          // The user chose the on-disk version; drop ours.
          isDirty.value = false
          error.value = ''
          return true
        }
        // Nobody to ask yet - surface it so NotebookView can prompt.
        conflictPending.value = true
        error.value = STALE_MESSAGE
        return false
      }
      // Keep the dirty flag so the next edit (or an explicit save) retries.
      error.value = e?.message || 'Could not save'
      return false
    } finally {
      saving.value = false
    }
  }

  function isStale(e: any): boolean {
    return String(e?.message ?? '').startsWith('stale_content:')
  }

  /** Overwrite the on-disk version unconditionally. */
  async function forceSaveContent(noteId: string, content: string): Promise<boolean> {
    try {
      applySaveResult(noteId, await notebooksApi.saveContent(noteId, content, null))
      isDirty.value = false
      error.value = ''
      return true
    } catch (e: any) {
      error.value = e?.message || 'Could not save'
      return false
    }
  }

  /** Answer the prompt raised by an autosave that hit an external edit. */
  async function resolveConflict(overwrite: boolean): Promise<boolean> {
    conflictPending.value = false
    if (!overwrite) {
      isDirty.value = false
      error.value = ''
      return true
    }
    const note = currentNote.value
    if (!note) return true
    return forceSaveContent(note.id, editorContent.value)
  }

  // -- loading ----------------------------------------------------------

  async function loadTree() {
    error.value = ''
    try {
      const tree = await notebooksApi.tree()
      groups.value = tree.groups
      root.value = tree.root
    } catch (e: any) {
      error.value = e?.message || 'Could not load the notebook'
    }
  }

  function findNote(id: string): Notebook | undefined {
    return allNotes.value.find((n) => n.id === id)
  }

  /** Neighbour to select after a delete: the next note, else the previous one. */
  function neighbourNoteId(removedId: string): string | null {
    const notes = allNotes.value
    const index = notes.findIndex((n) => n.id === removedId)
    if (index < 0) return null
    const next = notes[index + 1] ?? notes[index - 1]
    return next ? next.id : null
  }

  /** Remember where the caret was, so it can be restored on the way back. */
  function rememberCaret(noteId: string, position: { lineNumber: number; column: number } | null) {
    if (position) positionCache[noteId] = position
  }

  function recallCaret(noteId: string) {
    return positionCache[noteId] ?? null
  }

  /**
   * Switch notes, writing pending edits first.
   *
   * Returns false without switching when the pending edits could not be saved,
   * so typing is never lost to a failed request.
   */
  async function selectNote(id: string, options: SaveOptions = {}): Promise<boolean> {
    if (id === currentNote.value?.id) return true

    if (!(await flushSave(options))) return false

    loading.value = true
    try {
      const detail = await notebooksApi.get(id)
      currentNote.value = detail
      editorContent.value = detail.content
      isDirty.value = false
      lastNoteId.value = id
      save()
      await nextTick()
      return true
    } catch (e: any) {
      error.value = e?.message || 'Could not open the note'
      await loadTree()
      if (!findNote(id)) {
        currentNote.value = null
        editorContent.value = ''
      }
      return false
    } finally {
      loading.value = false
    }
  }

  function clearSelection() {
    currentNote.value = null
    editorContent.value = ''
    isDirty.value = false
    lastNoteId.value = null
    save()
  }

  // -- group actions ----------------------------------------------------

  async function createGroup(name: string): Promise<boolean> {
    try {
      const group = await notebooksApi.createGroup(name)
      await loadTree()
      return Boolean(group?.id)
    } catch (e: any) {
      error.value = e?.message || 'Could not create the group'
      return false
    }
  }

  async function renameGroup(groupId: string, name: string): Promise<boolean> {
    try {
      await notebooksApi.renameGroup(groupId, name)
      const tree = await notebooksApi.tree()
      groups.value = tree.groups
      // A rename moves the directory, so the open note's path changed too.
      if (currentNote.value) {
        const refreshed = findNote(currentNote.value.id)
        if (refreshed) currentNote.value.group_name = currentGroupNameOf(refreshed.group_id)
      }
      return true
    } catch (e: any) {
      error.value = e?.message || 'Could not rename the group'
      return false
    }
  }

  function currentGroupNameOf(groupId: string): string {
    return groups.value.find((g) => g.id === groupId)?.name ?? ''
  }

  async function deleteGroup(groupId: string, force = false): Promise<boolean> {
    try {
      await notebooksApi.deleteGroup(groupId, force)
      if (currentNote.value?.group_id === groupId) clearSelection()
      await loadTree()
      return true
    } catch (e: any) {
      error.value = e?.message || 'Could not delete the group'
      return false
    }
  }

  async function moveGroup(groupId: string, direction: MoveDirection): Promise<boolean> {
    try {
      await notebooksApi.moveGroup(groupId, direction)
      await loadTree()
      return true
    } catch (e: any) {
      error.value = e?.message || 'Could not move the group'
      return false
    }
  }

  // -- note actions -----------------------------------------------------

  async function createNote(
    groupId: string,
    title: string,
    options: SaveOptions = {}
  ): Promise<boolean> {
    if (!(await flushSave(options))) return false
    try {
      const created = await notebooksApi.create(groupId, title)
      await loadTree()
      await selectNote(created.id, options)
      return true
    } catch (e: any) {
      error.value = e?.message || 'Could not create the note'
      return false
    }
  }

  async function renameNote(noteId: string, title: string): Promise<boolean> {
    try {
      await notebooksApi.update(noteId, { title })
      await loadTree()
      const refreshed = findNote(noteId)
      if (refreshed && currentNote.value?.id === noteId) {
        currentNote.value.title = refreshed.title
        currentNote.value.filename = refreshed.filename
      }
      return true
    } catch (e: any) {
      error.value = e?.message || 'Could not rename'
      return false
    }
  }

  async function moveNoteToGroup(noteId: string, groupId: string): Promise<boolean> {
    try {
      await notebooksApi.update(noteId, { group_id: groupId })
      await loadTree()
      if (currentNote.value?.id === noteId) {
        currentNote.value.group_id = groupId
        currentNote.value.group_name = currentGroupNameOf(groupId)
      }
      return true
    } catch (e: any) {
      error.value = e?.message || 'Could not move the note'
      return false
    }
  }

  async function deleteNote(noteId: string): Promise<boolean> {
    try {
      const wasCurrent = currentNote.value?.id === noteId
      const nextId = wasCurrent ? neighbourNoteId(noteId) : null
      if (wasCurrent) {
        cancelPendingSave()
        isDirty.value = false
      }
      await notebooksApi.remove(noteId)
      await loadTree()
      if (nextId && findNote(nextId)) await selectNote(nextId)
      else if (wasCurrent) clearSelection()
      return true
    } catch (e: any) {
      error.value = e?.message || 'Could not delete the note'
      return false
    }
  }

  async function togglePin(note: Notebook): Promise<boolean> {
    try {
      await notebooksApi.setPinned(note.id, !note.pinned)
      await loadTree()
      return true
    } catch (e: any) {
      error.value = e?.message || 'Could not update the pin'
      return false
    }
  }

  /** Reorder returns the group's full ordered list — trust the server over local guesses. */
  async function moveNote(noteId: string, direction: MoveDirection): Promise<boolean> {
    try {
      const notes = await notebooksApi.move(noteId, direction)
      const first = notes[0]
      if (first) {
        const group = groups.value.find((g) => g.id === first.group_id)
        if (group) group.notes = notes
      }
      return true
    } catch (e: any) {
      error.value = e?.message || 'Could not move'
      return false
    }
  }

  // -- search -----------------------------------------------------------

  function setSearchQuery(query: string) {
    searchQuery.value = query
    if (searchTimer) {
      clearTimeout(searchTimer)
      searchTimer = null
    }
    if (!query.trim()) {
      searchResults.value = []
      searchTotal.value = 0
      searchTruncated.value = false
      searching.value = false
      searchSeq++ // invalidate any in-flight request
      return
    }
    searching.value = true
    searchTimer = setTimeout(() => {
      searchTimer = null
      void runSearch(query)
    }, SEARCH_DEBOUNCE_MS)
  }

  async function runSearch(query: string) {
    const seq = ++searchSeq
    try {
      const result = await notebooksApi.search(query, 50)
      if (seq !== searchSeq) return // a newer query is already in flight
      searchResults.value = result.results
      searchTotal.value = result.total
      searchTruncated.value = result.truncated
      error.value = ''
    } catch (e: any) {
      if (seq !== searchSeq) return
      error.value = e?.message || 'Search failed'
      searchResults.value = []
    } finally {
      if (seq === searchSeq) searching.value = false
    }
  }

  function clearSearch() {
    setSearchQuery('')
  }

  // -- lifecycle --------------------------------------------------------

  async function init() {
    load()
    await loadTree()
    if (lastNoteId.value && findNote(lastNoteId.value)) {
      await selectNote(lastNoteId.value)
    }
  }

  function dispose() {
    cancelPendingSave()
    if (searchTimer) {
      clearTimeout(searchTimer)
      searchTimer = null
    }
  }

  return {
    groups,
    root,
    currentNote,
    editorContent,
    mode,
    isDirty,
    loading,
    saving,
    error,
    conflictPending,
    searchQuery,
    searchResults,
    searchTotal,
    searchTruncated,
    searching,
    allNotes,
    sortedGroups,
    currentGroupName,
    currentNoteId,
    canMoveUp,
    canMoveDown,
    canMoveGroupUp,
    canMoveGroupDown,
    isCollapsed,
    toggleCollapse,
    setMode,
    sidebarVisible,
    toggleSidebar,
    init,
    dispose,
    loadTree,
    rememberCaret,
    recallCaret,
    resolveConflict,
    load,
    save,
    scheduleSave,
    flushSave,
    selectNote,
    clearSelection,
    findNote,
    createGroup,
    renameGroup,
    deleteGroup,
    moveGroup,
    createNote,
    renameNote,
    moveNoteToGroup,
    deleteNote,
    togglePin,
    moveNote,
    setSearchQuery,
    clearSearch
  }
})

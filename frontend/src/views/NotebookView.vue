<script setup lang="ts">
/**
 * Markdown notebook.
 *
 * Owns the dialogs and keeps the store's pending content safe across every
 * navigation-away path (note switch, page leave, tab close).
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { Splitpanes, Pane } from 'splitpanes'
import NotebookSidebar from '@/components/NotebookSidebar.vue'
import NotebookEditor from '@/components/NotebookEditor.vue'
import ContextMenu, { type MenuItem } from '@/components/ContextMenu.vue'
import GlobalTerminalIcon from '@/components/GlobalTerminalIcon.vue'
import { useConfirm } from '@/composables/useConfirm'
import { useTheme } from '@/composables/useTheme'
import { useNotebookStore } from '@/store/notebook'
import type { Notebook, NotebookTreeGroup } from '@/api/notebooks'

const router = useRouter()
const store = useNotebookStore()
const { showConfirm } = useConfirm()
const { theme, cycleTheme } = useTheme()

const editorSection = ref<any>(null)

// Hiding the sidebar widens the editor, which Monaco does not notice on its own.
const toggleSidebar = async () => {
  store.toggleSidebar()
  await nextTick()
  editorSection.value?.relayout?.()
}

// -- context menu -----------------------------------------------------------

const menu = ref({ show: false, x: 0, y: 0 })
const menuItems = ref<MenuItem[]>([])
const menuNote = ref<Notebook | null>(null)
const menuGroup = ref<NotebookTreeGroup | null>(null)

const closeMenu = () => {
  menu.value.show = false
  menuNote.value = null
  menuGroup.value = null
}

const openNoteMenu = ({ note, event }: { note: Notebook; event: MouseEvent }) => {
  menuNote.value = note
  menuGroup.value = null
  menuItems.value = [
    {
      label: note.pinned ? 'Unpin' : 'Pin',
      icon: '📌',
      action: () => void store.togglePin(note)
    },
    {
      label: 'Move up',
      icon: '⬆️',
      disabled: !store.canMoveUp(note),
      action: () => void store.moveNote(note.id, 'up')
    },
    {
      label: 'Move down',
      icon: '⬇️',
      disabled: !store.canMoveDown(note),
      action: () => void store.moveNote(note.id, 'down')
    },
    { label: 'Rename', icon: '✏️', action: () => openRenameNote(note) },
    { label: 'Move to group', icon: '📁', action: () => openMoveNote(note) },
    { label: 'Delete', icon: '🗑️', danger: true, action: () => void confirmDeleteNote(note) }
  ]
  menu.value = { show: true, x: event.clientX, y: event.clientY }
}

const openGroupMenu = ({ group, event }: { group: NotebookTreeGroup; event: MouseEvent }) => {
  menuNote.value = null
  menuGroup.value = group
  menuItems.value = [
    { label: 'New note', icon: '➕', action: () => openCreateNote(group.id) },
    {
      label: 'Rename group',
      icon: '✏️',
      disabled: group.is_default,
      action: () => openRenameGroup(group)
    },
    {
      label: 'Move up',
      icon: '⬆️',
      disabled: !store.canMoveGroupUp(group),
      action: () => void store.moveGroup(group.id, 'up')
    },
    {
      label: 'Move down',
      icon: '⬇️',
      disabled: !store.canMoveGroupDown(group),
      action: () => void store.moveGroup(group.id, 'down')
    },
    {
      label: 'Delete group',
      icon: '🗑️',
      danger: true,
      disabled: group.is_default,
      action: () => void confirmDeleteGroup(group)
    }
  ]
  menu.value = { show: true, x: event.clientX, y: event.clientY }
}

const openBackgroundMenu = (event: MouseEvent) => {
  menuNote.value = null
  menuGroup.value = null
  menuItems.value = [
    { label: 'New note', icon: '➕', action: () => openCreateNote(defaultGroupId.value) },
    { label: 'New group', icon: '📁', action: () => openCreateGroup() }
  ]
  menu.value = { show: true, x: event.clientX, y: event.clientY }
}

// -- dialogs ----------------------------------------------------------------

type DialogKind = 'create-note' | 'create-group' | 'rename-note' | 'rename-group' | 'move-note' | null

const dialog = ref<DialogKind>(null)
const dialogInput = ref('')
const dialogError = ref('')
const dialogBusy = ref(false)
const moveTargetGroupId = ref('')

// Targets captured when a dialog opens, so submit does not have to guess.
const createNoteGroupId = ref('')
const renameNoteId = ref('')
const renameGroupId = ref('')
const moveNoteId = ref('')

const dialogTitle = computed(() => {
  switch (dialog.value) {
    case 'create-note': return 'New note'
    case 'create-group': return 'New group'
    case 'rename-note': return 'Rename note'
    case 'rename-group': return 'Rename group'
    case 'move-note': return 'Move to group'
    default: return ''
  }
})

const defaultGroupId = computed(
  () => store.groups.find((g) => g.is_default)?.id ?? store.groups[0]?.id ?? ''
)

/** Ask about unsaved content before a destructive or switching action. */
const saveOrAsk = () =>
  store.flushSave({
    onConflict: (message) =>
      showConfirm({
        title: 'File changed on disk',
        message,
        confirmText: 'Overwrite',
        cancelText: 'Discard my changes',
        danger: true
      })
  })

const closeDialog = () => {
  dialog.value = null
  dialogInput.value = ''
  dialogError.value = ''
  dialogBusy.value = false
}

const openCreateNote = (groupId?: string) => {
  closeMenu()
  createNoteGroupId.value = groupId || defaultGroupId.value
  dialog.value = 'create-note'
  dialogInput.value = ''
  dialogError.value = ''
}

const openCreateGroup = () => {
  closeMenu()
  dialog.value = 'create-group'
  dialogInput.value = ''
  dialogError.value = ''
}

const openRenameNote = (note: Notebook) => {
  closeMenu()
  renameNoteId.value = note.id
  dialog.value = 'rename-note'
  dialogInput.value = note.title
  dialogError.value = ''
}

const openRenameGroup = (group: NotebookTreeGroup) => {
  closeMenu()
  renameGroupId.value = group.id
  dialog.value = 'rename-group'
  dialogInput.value = group.name
  dialogError.value = ''
}

const openMoveNote = (note: Notebook) => {
  closeMenu()
  moveNoteId.value = note.id
  dialog.value = 'move-note'
  moveTargetGroupId.value = store.groups.find((g) => g.id !== note.group_id)?.id ?? ''
  dialogError.value = ''
}

const submitDialog = async () => {
  const value = dialogInput.value.trim()
  dialogError.value = ''

  if (dialog.value === 'move-note') {
    if (!moveTargetGroupId.value) {
      dialogError.value = 'Select a group'
      return
    }
    dialogBusy.value = true
    const moved = await store.moveNoteToGroup(moveNoteId.value, moveTargetGroupId.value)
    dialogBusy.value = false
    if (moved) closeDialog()
    else dialogError.value = store.error || 'Could not move'
    return
  }

  if (!value) {
    dialogError.value = 'Name cannot be empty'
    return
  }

  const conflictPrompt = (message: string) =>
    showConfirm({
      title: 'File changed on disk',
      message,
      confirmText: 'Overwrite',
      cancelText: 'Discard',
      danger: true
    })

  dialogBusy.value = true
  let ok = false
  switch (dialog.value) {
    case 'create-note':
      ok = await store.createNote(createNoteGroupId.value, value, {
        onConflict: conflictPrompt
      })
      break
    case 'create-group':
      ok = await store.createGroup(value)
      break
    case 'rename-note':
      ok = await store.renameNote(renameNoteId.value, value)
      break
    case 'rename-group':
      ok = await store.renameGroup(renameGroupId.value, value)
      break
  }
  dialogBusy.value = false
  if (ok) closeDialog()
  else dialogError.value = store.error || 'Action failed'
}

// -- delete confirmations ---------------------------------------------------

const confirmDeleteNote = async (note: Notebook) => {
  closeMenu()
  const ok = await showConfirm({
    title: 'Delete note',
    message: `Delete "${note.title}"? The file on disk will be removed too.`,
    confirmText: 'Delete',
    danger: true
  })
  if (ok) await store.deleteNote(note.id)
}

const confirmDeleteGroup = async (group: NotebookTreeGroup) => {
  closeMenu()
  const count = group.notes.length
  const ok = await showConfirm({
    title: 'Delete group',
    message: count
      ? `"${group.name}" still has ${count} note${count === 1 ? '' : 's'}. Deleting the group removes those files too.`
      : `Delete the group "${group.name}"?`,
    confirmText: 'Delete',
    danger: true
  })
  if (ok) await store.deleteGroup(group.id, true)
}

// -- note selection ---------------------------------------------------------

const onSelectNote = async (id: string) => {
  // Remember the caret before the editor is torn down for the switch.
  if (store.currentNoteId) store.rememberCaret(store.currentNoteId, caret())

  if (!(await saveOrAsk())) return
  if (!(await store.selectNote(id))) return

  const caretToRestore = store.recallCaret(id)
  if (caretToRestore) {
    await nextTick()
    editorSection.value?.getEditor?.()?.setPosition?.(caretToRestore)
  }
}

/** The live editor handle, or null when no editor is mounted (preview mode). */
const caret = () => editorSection.value?.getEditor?.()?.getPosition?.() ?? null

const onContentChange = () => store.scheduleSave()

// An autosave that lost the race with an external edit has nobody to ask, so
// it raises a flag and we surface the prompt here.
watch(
  () => store.conflictPending,
  async (pending) => {
    if (!pending) return
    const overwrite = await showConfirm({
      title: 'File changed on disk',
      message: 'This note was changed on disk by something else. Overwrite it with your version?',
      confirmText: 'Overwrite',
      cancelText: 'Discard my changes',
      danger: true
    })
    await store.resolveConflict(overwrite)
  }
)

const onSave = () =>
  store.flushSave({
    onConflict: (message) =>
      showConfirm({
        title: 'File changed on disk',
        message,
        confirmText: 'Overwrite',
        cancelText: 'Cancel',
        danger: true
      })
  })

// -- lifecycle --------------------------------------------------------------

// Leaving the page must not drop an unsaved edit (nor silently discard one
// that lost a conflict). Cancel the navigation instead.
onBeforeRouteLeave(async () => {
  if (!store.isDirty) return true
  const saved = await saveOrAsk()
  if (saved) return true
  const discard = await showConfirm({
    title: 'Unsaved changes',
    message: 'Saving failed. Leaving now will lose those changes. Leave anyway?',
    confirmText: 'Discard and leave',
    cancelText: 'Stay on page',
    danger: true
  })
  return discard
})

const handleBeforeUnload = (e: BeforeUnloadEvent) => {
  if (store.isDirty) {
    e.preventDefault()
    e.returnValue = ''
  }
}

onMounted(async () => {
  window.addEventListener('beforeunload', handleBeforeUnload)
  await store.init()
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  // onBeforeRouteLeave has already flushed for in-app navigation; this covers
  // the component being torn down some other way.
  void store.flushSave()
  store.dispose()
})
</script>

<template>
  <div class="h-screen flex flex-col bg-main overflow-hidden">
    <!-- Header -->
    <header class="bg-main border-b border-main shrink-0">
      <div class="px-3 sm:px-4 lg:px-6 py-2 flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-main">Notebook</h1>
          <p class="text-xs text-sub truncate">
            {{ store.root || 'Markdown notes' }}
          </p>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="p-0 rounded-lg hover:bg-sub"
            title="Refresh (rescan disk)"
            @click="store.loadTree()"
          >
            <svg class="h-5 w-5 text-sub" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          <button class="p-0 rounded-lg hover:bg-sub" title="Cycle theme" @click="cycleTheme">
            <svg v-if="theme === 'light'" class="h-5 w-5 text-sub" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            <svg v-else-if="theme === 'dark'" class="h-5 w-5 text-sub" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
            <svg v-else-if="theme === 'green'" class="h-5 w-5 text-green-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
            </svg>
            <svg v-else class="h-5 w-5 text-amber-700" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </button>
          <GlobalTerminalIcon />
          <button class="btn btn-secondary text-sm" @click="router.push('/projects')">
            Back to projects
          </button>
        </div>
      </div>
    </header>

    <!-- Error banner -->
    <div
      v-if="store.error"
      class="shrink-0 px-4 py-2 text-sm flex items-center gap-3"
      style="background-color: color-mix(in srgb, #dc2626 12%, transparent); color: #dc2626"
    >
      <span class="flex-1 truncate">{{ store.error }}</span>
      <button class="text-xs underline" @click="store.error = ''">Dismiss</button>
    </div>

    <!-- Body -->
    <splitpanes
      class="default-theme notebook-splitpanes flex-1 min-h-0"
      :class="{ 'sidebar-hidden': !store.sidebarVisible }"
    >
      <pane :size="22" :min-size="14" class="flex flex-col min-h-0">
        <NotebookSidebar
          :groups="store.sortedGroups"
          :selected-id="store.currentNoteId"
          :loading="store.loading"
          :query="store.searchQuery"
          :search-results="store.searchResults"
          :search-total="store.searchTotal"
          :search-truncated="store.searchTruncated"
          :searching="store.searching"
          :is-collapsed="store.isCollapsed"
          @select="onSelectNote"
          @create-note="openCreateNote(defaultGroupId)"
          @create-group="openCreateGroup"
          @toggle-collapse="store.toggleCollapse"
          @update-query="store.setSearchQuery"
          @note-context-menu="openNoteMenu"
          @group-context-menu="openGroupMenu"
          @background-context-menu="openBackgroundMenu"
        />
      </pane>
      <pane :size="78" class="flex flex-col min-h-0">
        <NotebookEditor
          ref="editorSection"
          :note="store.currentNote"
          :group-name="store.currentGroupName"
          :model-value="store.editorContent"
          :mode="store.mode"
          :saving="store.saving"
          :is-dirty="store.isDirty"
          :sidebar-visible="store.sidebarVisible"
          @update:model-value="store.editorContent = $event"
          @update:mode="store.setMode"
          @toggle-sidebar="toggleSidebar"
          @content-change="onContentChange"
          @save="onSave"
          @rename="store.currentNote && openRenameNote(store.currentNote)"
          @move-to-group="store.currentNote && openMoveNote(store.currentNote)"
          @remove="store.currentNote && confirmDeleteNote(store.currentNote)"
        />

      </pane>
    </splitpanes>

    <!-- Context menu -->
    <ContextMenu
      :show="menu.show"
      :x="menu.x"
      :y="menu.y"
      :items="menuItems"
      @close="closeMenu"
    />

    <!-- Dialogs -->
    <div
      v-if="dialog"
      role="dialog"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      @click.self="closeDialog"
    >
      <div class="card max-w-md w-full">
        <h3 class="text-lg font-semibold text-main mb-4">{{ dialogTitle }}</h3>

        <div v-if="dialog === 'move-note'" class="max-h-64 overflow-y-auto">
          <p v-if="store.groups.filter(g => g.id !== store.currentNote?.group_id).length === 0"
             class="text-sm text-sub">
            There is no other group to move it to.
          </p>
          <label
            v-for="group in store.groups.filter(g => g.id !== store.currentNote?.group_id)"
            :key="group.id"
            class="flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer hover:bg-sub"
          >
            <input v-model="moveTargetGroupId" type="radio" :value="group.id" />
            <span class="text-sm text-main truncate">{{ group.name }}</span>
          </label>
        </div>

        <input
          v-else
          v-model="dialogInput"
          class="input w-full"
          :placeholder="dialog === 'create-group' || dialog === 'rename-group' ? 'Group name' : 'Note name'"
          autofocus
          @keydown.enter.prevent="submitDialog"
        />

        <p v-if="dialogError" class="mt-2 text-sm" style="color: #dc2626">{{ dialogError }}</p>

        <div class="flex gap-3 justify-end mt-4">
          <button class="btn btn-secondary" @click="closeDialog">Cancel</button>
          <button class="btn btn-primary" :disabled="dialogBusy" @click="submitDialog">
            {{ dialogBusy ? 'Working…' : 'OK' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/*
 * splitpanes ships a "default-theme" that paints the splitter white and gives
 * it `border-left: 1px solid #eee` - which reads as a bright line against the
 * dark themes. The whole appearance is declared here, on the element itself,
 * rather than relying on CodeReviewView's global fix-up rules: those only
 * exist once that lazily-loaded view has been visited, so the divider used to
 * look different depending on which page you came from.
 *
 * The doubled-up `.notebook-splitpanes.splitpanes` selector outranks
 * splitpanes' own `.default-theme.splitpanes--vertical > ...` rules.
 */
.notebook-splitpanes.splitpanes :deep(.splitpanes__splitter) {
  background-color: var(--border-color);
  border: none;
  transition: none;
}

/* `splitpanes--vertical` sits on the root element itself, so it has to be part
   of the same compound selector rather than a descendant. */
.notebook-splitpanes.splitpanes--vertical > :deep(.splitpanes__splitter) {
  width: 4px;
  margin-left: 0;
}

.notebook-splitpanes.splitpanes--horizontal > :deep(.splitpanes__splitter) {
  height: 4px;
  margin-top: 0;
}

/*
 * Hiding the list is done with CSS rather than v-if so the editor (and its
 * Monaco instance, undo stack and scroll position) survives the toggle.
 * splitpanes writes pane widths as inline styles, hence the !important.
 */
.notebook-splitpanes.sidebar-hidden > :deep(.splitpanes__pane:first-child),
.notebook-splitpanes.sidebar-hidden > :deep(.splitpanes__splitter) {
  display: none;
}

.notebook-splitpanes.sidebar-hidden > :deep(.splitpanes__pane:last-child) {
  width: 100% !important;
}

/* Drag handles, so they stay visible on dark themes. */
.notebook-splitpanes.splitpanes :deep(.splitpanes__splitter:before),
.notebook-splitpanes.splitpanes :deep(.splitpanes__splitter:after) {
  background-color: var(--border-secondary);
}

@media (hover: hover) {
  .notebook-splitpanes.splitpanes :deep(.splitpanes__splitter:hover) {
    background-color: var(--accent-color);
  }

  .notebook-splitpanes.splitpanes :deep(.splitpanes__splitter:hover:before),
  .notebook-splitpanes.splitpanes :deep(.splitpanes__splitter:hover:after) {
    background-color: var(--splitter-handle);
  }
}

.notebook-splitpanes.splitpanes.splitpanes--dragging :deep(.splitpanes__splitter) {
  background-color: var(--accent-color);
}
</style>

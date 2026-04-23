# Remove Tasks Page & Embed Task List in CodeReviewView

**Date:** 2026-04-18
**Status:** Draft

## Problem

The current 3-page navigation (Projects → Tasks → CodeReview) adds unnecessary friction. Users must go through a separate task list page before reaching the code editor. For a single-user tool, this intermediate page provides little value.

## Goals

1. Remove the TasksView intermediate page
2. Clicking a project goes directly to CodeReviewView
3. Merge Changes and Commits into a tabbed pane in the sidebar
4. Add a task list at the bottom of the sidebar for task switching
5. Auto-create a "Direct" task when creating a project
6. Task switching uses in-place data swap (no full page reload)

## Design

### 1. Route Changes

**Before:**
```
/projects          → ProjectsView
/projects/:id      → TasksView (task list page)
/tasks/:id         → CodeReviewView
```

**After:**
```
/projects          → ProjectsView
/projects/:id      → CodeReviewView (default: auto-select Direct task)
```

- Remove `/projects/:id` route pointing to TasksView
- Remove `/tasks/:id` route
- `/projects/:id` now loads CodeReviewView directly
- Task selection via URL query param: `/projects/:id?task=<task_id>`
- If no `?task=` param, auto-select the Direct task

**Router changes in `router/index.ts`:**
```typescript
{
  path: '/projects/:id',
  name: 'project',
  component: () => import('@/views/CodeReviewView.vue'),
  meta: { requiresAuth: true }
}
// Remove: /tasks/:id route
// Remove: TasksView import
```

### 2. Auto-Create Direct Task on Project Creation

**Backend change in `POST /projects` endpoint:**
- After creating the project, automatically create a task with:
  - `name = "Direct"`
  - `direct_on_branch = true`
  - `project_id = <new project's id>`

**Why backend:** The task creation logic (worktree setup, tmux session) already lives in the backend task creation endpoint. Reusing it avoids duplicating logic.

The direct task is special:
- Cannot be deleted (protected)
- Created automatically with every project
- Works directly on the main branch (no separate worktree)

### 3. Sidebar Layout Restructure

**Before (3 horizontal panes):**
```
Files (file tree)
Changes (changed files list)
Commits (commit history)
```

**After (3 horizontal panes):**
```
Files (file tree)
Changes / Commits (tabbed — switch between two views)
Task List (task switcher for current project)
```

#### Changes/Commits Tab Pane

- Two tabs: `Changes (N)` and `Commits`
- `Changes` tab: shows changed files list with Accept button (existing behavior)
- `Commits` tab: shows commit history with Merge button (existing behavior)
- Tab state persists in URL or localStorage
- Only one tab visible at a time, saving vertical space

**Template structure:**
```html
<pane class="changes-commits-pane">
  <div class="tab-bar">
    <button :class="{ active: activeTab === 'changes' }">Changes ({{ count }})</button>
    <button :class="{ active: activeTab === 'commits' }">Commits</button>
  </div>
  <div v-if="activeTab === 'changes'"><!-- existing changes content --></div>
  <div v-else><!-- existing commits content --></div>
</pane>
```

#### Task List Pane

- Shows all tasks for the current project
- Each task item shows: name, task status icon, code status label
- Current task is highlighted (selected state)
- Click a task → in-place data swap (see section 4)
- Direct task has a small "Direct" badge and cannot be deleted
- Non-direct tasks have a delete button (with confirmation)
- Bottom: "+ New Task" button opens create dialog

**Task item template:**
```html
<div class="task-item" :class="{ active: task.id === currentTaskId }" @click="switchTask(task.id)">
  <span class="task-name">{{ task.name }}</span>
  <span class="task-badge" v-if="task.direct_on_branch">Direct</span>
  <span class="task-status">{{ statusIcon }}</span>
  <button v-if="!task.direct_on_branch" @click.stop="deleteTask(task)">×</button>
</div>
```

### 4. In-Place Task Switching

When user clicks a different task in the task list:

1. **Update URL** (no page reload): `router.replace({ query: { task: newTaskId } })`
2. **Load new task data**: `tasksApi.get(newTaskId)` → `store.setCurrentTask()`
3. **Reload dependent data** (in parallel):
   - `loadChangedFiles()`
   - `loadCommits()`
   - `loadButtonStates()`
   - `refreshStatus()`
   - `loadFileTree()` (different worktree = different files)
4. **Reset editor state**: clear `currentFile`, `fileContent`, set `editorMode = 'editor'`
5. **Reset pagination**: `currentPage = 1`, `changedFilesPage = 1`
6. **Clear caches**: FileCacheService entries for old task (optional, browser handles this)

**Key implementation detail:** `taskId` computed property changes from `route.params.id` to `route.query.task`. The existing watchers on `taskId` will trigger data reloads.

```typescript
// Before
const taskId = computed(() => route.params.id as string)

// After
const projectId = computed(() => route.params.id as string)
const taskId = computed(() => route.query.task as string)
```

### 5. ProjectsView Changes

- `openProject()` navigates to `/projects/${project.id}` (CodeReviewView)
- No change to project card visual layout (delete button stays)
- Remove any reference to TasksView

### 6. Data Loading on Mount

CodeReviewView `onMounted` flow changes:

```typescript
onMounted(async () => {
  const projectId = route.params.id as string

  // Load project
  const project = await projectsApi.get(projectId)
  store.setCurrentProject(project)

  // Determine task: from URL query or default Direct task
  let targetTaskId = route.query.task as string

  if (!targetTaskId) {
    // Auto-select: load tasks, find Direct task
    const tasks = await tasksApi.list(projectId)
    const directTask = tasks.find(t => t.direct_on_branch) || tasks[0]
    targetTaskId = directTask.id
    router.replace({ query: { task: targetTaskId } })
  }

  // Load task and proceed with existing mount logic
  await loadTask(targetTaskId)
  // ... rest of existing mount logic
})
```

### 7. Auto-Refresh

- Task list data (task statuses) refreshes every 15 seconds on desktop
- Uses existing `isLanMode()` check — non-LAN skips refresh
- Mobile: no auto-refresh for task list
- Changes/Commits data continues to refresh as before

### 8. Task Creation Dialog

- Opens from "+ New Task" button in the Task List pane
- Same form as current TasksView: task name + direct_on_branch checkbox
- On create: adds task to list, optionally switches to it
- Reuses existing `tasksApi.create()` endpoint

### 9. Cleanup

**Files to remove:**
- `frontend/src/views/TasksView.vue`

**Files to modify:**
- `frontend/src/router/index.ts` — remove TasksView route, update project route
- `frontend/src/views/ProjectsView.vue` — update openProject navigation
- `frontend/src/views/CodeReviewView.vue` — major restructure (sidebar, task list, data loading)
- `frontend/src/api/tasks.ts` — no changes needed (existing API sufficient)
- `backend/app/routers/projects.py` — auto-create Direct task on project creation
- `backend/app/routers/tasks.py` — add protection for Direct task deletion

**Files to keep:**
- `frontend/src/components/TaskCard.vue` — may be reused/adapted for sidebar task items

### 10. Edge Cases

- **Project has no tasks** (shouldn't happen with auto-create, but handle gracefully): show "No tasks" in task list pane with create button
- **Direct task already exists** on project creation: don't create duplicate
- **URL with invalid task ID**: fall back to Direct task
- **Multiple browser tabs**: each tab can have different task selected independently via query param
- **Task deleted while viewing**: redirect to project's Direct task

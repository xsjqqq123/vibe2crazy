# Remove Tasks Page & Embed Task List in CodeReviewView

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the TasksView intermediate page. Clicking a project goes directly to CodeReviewView with an embedded task list. Changes and Commits merge into tabs. Task switching uses in-place data swap.

**Architecture:**
- Backend: `POST /projects` auto-creates a "Direct" task. Task delete endpoint protects direct tasks.
- Frontend: Router `GET /projects/:id` renders CodeReviewView. Task selected via `?task=xxx` query param. Sidebar has 3 panes: Files | Changes/Commits tabs | Task List.
- Task switching: `router.replace()` + parallel data reload, no full page navigation.

**Tech Stack:** Vue 3, FastAPI, Vue Router, Pinia store, Splitpanes

---

## File Map

| File | Action |
|------|--------|
| `frontend/src/router/index.ts` | Modify — remove TasksView route, update `/projects/:id` to use CodeReviewView |
| `frontend/src/views/ProjectsView.vue` | Modify — `openProject()` navigates to `/projects/:id` |
| `frontend/src/views/CodeReviewView.vue` | Major modify — sidebar restructure, task list, in-place switch |
| `frontend/src/views/TasksView.vue` | **Delete** |
| `backend/app/routers/projects.py` | Modify — `create_project()` auto-creates Direct task |
| `backend/app/routers/tasks.py` | Modify — `delete_task()` and `delete_task_by_id()` protect direct tasks |

**Unchanged:** API clients, store, schemas, models (existing endpoints sufficient).

---

## Task 1: Backend — Auto-Create Direct Task on Project Creation

**Files:**
- Modify: `backend/app/routers/projects.py:19-114`

- [ ] **Step 1: Read the existing `create_project` function**

Read `backend/app/routers/projects.py` lines 19-114 (the `create_project` function). Note the current imports already include `Task`, `TaskCreate`, `TaskStatus` from `app.models` and `app.schemas`.

- [ ] **Step 2: Add helper function to create Direct task**

Add this at the top of `projects.py`, after the existing helper functions (around line 15):

```python
def _create_direct_task(db: Session, project_id: str, project_name: str, git_path: str) -> "Task":
    """Create the default Direct task for a newly created project."""
    import uuid
    from app.models import Task, TaskStatus
    from app.services.tmux_service import TmuxService
    from app.config import settings

    task_id = str(uuid.uuid4())
    branch_name = f"direct-{project_id[:8]}"
    tmux_session = f"{settings.tmux_session_prefix}{project_name}-{task_id}"

    # Create tmux session pointing to main repo
    tmux_success, tmux_msg = TmuxService.create_session(tmux_session, git_path)
    if not tmux_success:
        logger.warning(f"Failed to create tmux session for Direct task: {tmux_msg}")
        # Non-fatal: continue without tmux

    db_task = Task(
        id=task_id,
        project_id=project_id,
        name="Direct",
        branch_name=branch_name,
        worktree_path=git_path,
        tmux_session=tmux_session,
        status=TaskStatus.active,
        direct_on_branch=True
    )
    db.add(db_task)
    return db_task
```

- [ ] **Step 3: Call helper after project commit**

In the `create_project` function, after the `db.commit()` and `db.refresh(db_project)` calls (around line 111), add:

```python
    db.commit()
    db.refresh(db_project)

    # Auto-create the default Direct task
    _create_direct_task(db, db_project.id, db_project.name, db_project.git_path)
    db.commit()

    return db_project
```

- [ ] **Step 4: Add type hint import**

Add `"from __future__ import annotations"` at the very top of `projects.py` (line 1) so the `"Task"` forward reference in the helper return type works:

```python
from __future__ import annotations
```

- [ ] **Step 5: Run backend tests to verify project creation still works**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/backend && python -c "from app.routers.projects import router; print('OK')"`

If import succeeds, commit.

- [ ] **Step 6: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add backend/app/routers/projects.py
git commit -m "feat: auto-create Direct task when project is created"
```

---

## Task 2: Backend — Protect Direct Task from Deletion

**Files:**
- Modify: `backend/app/routers/tasks.py:204-242` (delete_task function)
- Modify: `backend/app/routers/tasks.py:267-300` (delete_task_by_id function)

- [ ] **Step 1: Add protection to `delete_task` function**

Find the `delete_task` function (line 204). After the `if not task:` check block and before `# Get project for worktree cleanup`, add:

```python
    # Protect direct tasks from deletion
    if task.direct_on_branch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default Direct task"
        )
```

So the order becomes:
```python
    if not task:
        raise HTTPException(...)
        detail="Task not found"

    # NEW: Protect direct tasks
    if task.direct_on_branch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default Direct task"
        )

    # Get project for worktree cleanup  ← existing line
```

- [ ] **Step 2: Add protection to `delete_task_by_id` function**

Find the `delete_task_by_id` function (line 267). Add the same protection block after `if not task:` and before `# Get project for worktree cleanup`:

```python
    # Protect direct tasks from deletion
    if task.direct_on_branch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default Direct task"
        )
```

- [ ] **Step 3: Verify changes**

Run: `cd /home/xusongjie/workspace/vibe2death/vibe2crazy/backend && python -c "from app.routers.tasks import router, task_router; print('OK')"`

- [ ] **Step 4: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add backend/app/routers/tasks.py
git commit -m "feat: protect Direct task from deletion"
```

---

## Task 3: Frontend — Update Router

**Files:**
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: Read current router file**

Read `frontend/src/router/index.ts` completely.

- [ ] **Step 2: Update `/projects/:id` route to use CodeReviewView**

Change the project route from:
```typescript
{
  path: '/projects/:id',
  name: 'project',
  component: () => import('@/views/TasksView.vue'),
  meta: { requiresAuth: true }
},
```

To:
```typescript
{
  path: '/projects/:id',
  name: 'project',
  component: () => import('@/views/CodeReviewView.vue'),
  meta: { requiresAuth: true }
},
```

- [ ] **Step 3: Remove `/tasks/:id` route**

Delete the entire route block:
```typescript
{
  path: '/tasks/:id',
  name: 'task',
  component: () => import('@/views/CodeReviewView.vue'),
  meta: { requiresAuth: true }
},
```

- [ ] **Step 4: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add frontend/src/router/index.ts
git commit -m "refactor: point /projects/:id to CodeReviewView, remove /tasks/:id route"
```

---

## Task 4: Frontend — Update ProjectsView Navigation

**Files:**
- Modify: `frontend/src/views/ProjectsView.vue:57-59`

- [ ] **Step 1: Update `openProject` function**

Read `frontend/src/views/ProjectsView.vue` lines 1-60.

Change the `openProject` function from:
```typescript
const openProject = (project: Project) => {
  router.push(`/projects/${project.id}`)
}
```

To:
```typescript
const openProject = (project: Project) => {
  router.push(`/projects/${project.id}`)
}
```

**Note:** The navigation target is already `/projects/${project.id}`. Since the route now loads CodeReviewView instead of TasksView, this change is already correct — no actual code change needed. Verify that the function body is `router.push(\`/projects/${project.id}\`)` and that's it.

- [ ] **Step 2: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add frontend/src/views/ProjectsView.vue
git commit -m "refactor: ProjectsView now navigates to CodeReviewView"
```

---

## Task 5: Frontend — CodeReviewView Core Refactor (Data Loading + In-Place Switch)

**Files:**
- Modify: `frontend/src/views/CodeReviewView.vue` (script setup section, ~first 200 lines)

- [ ] **Step 1: Add new state variables**

In the `<script setup>` section, add after the existing `ref` declarations:

```typescript
// Task list state (new)
const tasks = ref<Task[]>([])
const tasksLoading = ref(false)
const activeTab = ref<'changes' | 'commits'>('changes')

// New computed for projectId from route params
const projectId = computed(() => route.params.id as string)

// Existing taskId changes from params to query
const taskId = computed(() => route.query.task as string)
```

- [ ] **Step 2: Add `switchTask` function**

Add this function after `refreshStatus` (around line 1120):

```typescript
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
    loadButtonStates(),
    refreshStatus(),
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
}
```

- [ ] **Step 3: Update `loadTask` to load tasks list too**

Modify `loadTask` to also load the task list for the sidebar. Change it from:

```typescript
const loadTask = async () => {
  try {
    const taskData = await tasksApi.get(taskId.value)
    store.setCurrentTask(taskData)
    store.setCurrentProject({ id: taskData.project_id })
  } catch (err: any) {
    console.error('Failed to load task:', err)
    router.push('/projects')
  }
}
```

To:

```typescript
const loadTask = async () => {
  try {
    const taskData = await tasksApi.get(taskId.value)
    store.setCurrentTask(taskData)
    store.setCurrentProject({ id: taskData.project_id })
    // Also load all tasks for the sidebar list
    tasksLoading.value = true
    tasks.value = await tasksApi.list(projectId.value)
  } catch (err: any) {
    console.error('Failed to load task:', err)
    router.push('/projects')
  } finally {
    tasksLoading.value = false
  }
}
```

- [ ] **Step 4: Update `onMounted` for initial task selection**

Read the current `onMounted` block (around line 1650). Replace it entirely with:

```typescript
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
    loadLayout()
    await loadTask()
    loadFileTree()
    loadChangedFiles().then(() => { initialLoading.value = false })
    loadCommits()
    loadButtonStates()
    refreshStatus()
    startRefresh()
  }

  console.log('[Layout Debug] onMounted completed')
})
```

- [ ] **Step 5: Update the `watch` on `taskId` to trigger task reload on switch**

Find the existing `watch(taskId, ...)` block (around line 508). Replace it with:

```typescript
watch(taskId, async () => {
  currentPage.value = 1
  changedFilesPage.value = 1
  // Reload task and all data when task changes (in-place switch)
  await loadTask()
  await Promise.all([
    loadChangedFiles(),
    loadCommits(),
    loadButtonStates(),
    refreshStatus(),
    loadFileTree()
  ])
})
```

**Important:** This watcher fires when `route.query.task` changes (via `switchTask`). Make sure the watcher is registered at the top level of `<script setup>` (not inside another function).

- [ ] **Step 6: Import Task type**

Find the `import tasksApi, { type Task, isTaskCompleted } from '@/api/tasks'` line and ensure `type Task` is imported (it should already be there from the existing code).

- [ ] **Step 7: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add frontend/src/views/CodeReviewView.vue
git commit -m "feat: add task list state, switchTask, and auto-select Direct task on mount"
```

---

## Task 6: Frontend — CodeReviewView Sidebar: Changes/Commits Tabs + Task List

**Files:**
- Modify: `frontend/src/views/CodeReviewView.vue` (template section)

This task modifies the sidebar template. The sidebar currently has 3 `<pane>` elements in the `sidebarSplitpanesRef`. We need to merge the middle two panes (Changes and Commits) into one pane with tab switching, and add a third pane for the Task List.

- [ ] **Step 1: Find the sidebar panes in the template**

Find this section (around lines 1780-1916):

```html
<splitpanes ref="sidebarSplitpanesRef" horizontal class="default-theme h-full" @resize="handleSidebarResize">
  <!-- File tree pane (keep as-is) -->
  <pane :size="layout.changedFiles" ...>...</pane>

  <!-- Changed files pane (becomes tabbed with Commits) -->
  <pane :size="layout.files" ...>...</pane>

  <!-- Commits pane (becomes tabbed with Changes) -->
  <pane :size="layout.commits" ...>...</pane>
</splitpanes>
```

Replace the **Changed files pane** and **Commits pane** with a single tabbed pane:

```html
<!-- Changes / Commits tabbed pane -->
<pane :size="layout.files + layout.commits" :min-size="15" class="flex flex-col min-h-0 bg-main border-r border-main">
  <!-- Tab bar -->
  <div class="flex border-b border-main">
    <button
      @click="activeTab = 'changes'"
      :class="['flex-1 px-3 py-2 text-sm font-medium transition-colors', activeTab === 'changes' ? 'text-main border-b-2 border-accent' : 'text-sub hover:text-main']"
    >
      Changes ({{ changedFiles.length }})
    </button>
    <button
      @click="activeTab = 'commits'"
      :class="['flex-1 px-3 py-2 text-sm font-medium transition-colors', activeTab === 'commits' ? 'text-main border-b-2 border-accent' : 'text-sub hover:text-main']"
    >
      Commits
    </button>
  </div>

  <!-- Tab content -->
  <div class="flex-1 overflow-y-auto min-h-0">
    <!-- Changes tab -->
    <div v-if="activeTab === 'changes'" class="changed-files-list p-4 min-h-full">
      <!-- Existing changed files content (copy from the old Changes pane) -->
      <!-- Copy lines ~1813-1874 from the current file here -->
      <!-- ... -->
    </div>

    <!-- Commits tab -->
    <div v-else class="flex-[1] p-4 min-h-full">
      <!-- Existing commits content (copy from the old Commits pane) -->
      <!-- Copy lines ~1877-1914 from the current file here -->
      <!-- ... -->
    </div>
  </div>
</pane>

<!-- Task List pane (NEW) -->
<pane :size="25" :min-size="10" class="flex flex-col min-h-0 bg-main border-r border-main">
  <div class="p-4 flex-1 overflow-y-auto min-h-0">
    <div class="flex items-center justify-between mb-2">
      <h3 class="text-sm font-semibold text-main">Tasks</h3>
      <button @click="showCreateDialog = true" class="text-xs text-accent hover:text-accent/80">+ New</button>
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
          'task-item px-2 py-1.5 rounded cursor-pointer text-sm flex items-center gap-2',
          task.id === taskId ? 'bg-accent/10 text-accent font-medium' : 'hover:bg-sub text-sub'
        ]"
      >
        <span class="task-name truncate flex-1">{{ task.name }}</span>
        <span v-if="task.direct_on_branch" class="px-1 py-0.5 text-xs rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 shrink-0">Direct</span>
        <span v-else class="text-xs" :class="task.task_status === 'running' ? 'text-green-600 dark:text-green-400' : 'text-gray-500'">
          {{ task.task_status === 'running' ? '🟢' : '⚪' }}
        </span>
      </div>
    </div>
  </div>
</pane>
```

**Note for the agent:** When copying the Changes and Commits content into the tab panes, preserve the original HTML structure and class names. The key is that both pieces of content go inside `<div v-if="activeTab === 'changes'">` and `<div v-else>` respectively.

- [ ] **Step 2: Update `handleSidebarResize` for new layout**

Since the two panes (Changes + Commits) are now merged into one, update `handleSidebarResize` to handle the new pane count. The sidebar now has 2 panes: File tree + (Tabbed content + Task List). Update the handler:

```typescript
const handleSidebarResize = (event: LayoutEvent) => {
  const panes = (event as any).panes
  if (panes && panes.length >= 2) {
    layout.value.files = Math.round(panes[1].size)
    // Task list is pane 3 (index 2), File tree is pane 1 (index 0)
  }
}
```

Since the sidebar now has 2 horizontal panes (File tree pane + combined Tabbed+Task pane), the resize handler should split the second pane's size between files and tasks. Update it to:

```typescript
const handleSidebarResize = (event: LayoutEvent) => {
  const panes = (event as any).panes
  if (panes && panes.length >= 2) {
    layout.value.files = Math.round(panes[1].size)
    // Note: Task list size derived from remaining space
  }
}
```

- [ ] **Step 3: Add task creation dialog to CodeReviewView**

Add the task creation dialog template at the bottom of the template (before `</template>`). Copy the dialog from `TasksView.vue` lines 275-323 and place it inside CodeReviewView's template.

The dialog shows when `showCreateDialog = true`. Add these to the script setup:

```typescript
const showCreateDialog = ref(false)
const newTaskName = ref('')
const newTaskDirectOnBranch = ref(false)
const createError = ref('')

const createTask = async () => {
  if (!newTaskName.value.trim()) {
    createError.value = 'Please enter a task name'
    return
  }
  loading.value = true
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
    // Optionally switch to the new task
    await switchTask(created.id)
  } catch (err: any) {
    createError.value = err.message || 'Failed to create task'
  }
  loading.value = false
}
```

Add the dialog HTML to the template:

```html
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
        </label>
      </div>
      <div v-if="createError" class="text-red-600 dark:text-red-400 text-sm">{{ createError }}</div>
      <div class="flex gap-3 justify-end">
        <button type="button" @click="showCreateDialog = false; newTaskDirectOnBranch = false" class="btn btn-secondary">Cancel</button>
        <button type="submit" :disabled="loading" class="btn btn-primary">
          <span v-if="loading" class="spinner mr-2"></span>Create
        </button>
      </div>
    </form>
  </div>
</div>
```

- [ ] **Step 4: Add CSS for task items**

Add to the `<style>` section (at the bottom of the file):

```css
.task-item {
  transition: background-color 0.15s;
}
```

- [ ] **Step 5: Update `goBackToTasks` function**

Change `goBackToTasks` to navigate to projects instead:

```typescript
const goBackToTasks = () => {
  router.push('/projects')
}
```

- [ ] **Step 6: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add frontend/src/views/CodeReviewView.vue
git commit -m "feat: merge Changes/Commits into tabs, add embedded task list to sidebar"
```

---

## Task 7: Frontend — Delete TasksView

**Files:**
- Delete: `frontend/src/views/TasksView.vue`

- [ ] **Step 1: Delete the file**

Run: `rm /home/xusongjie/workspace/vibe2death/vibe2crazy/frontend/src/views/TasksView.vue`

- [ ] **Step 2: Commit**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add -A
git commit -m "refactor: remove TasksView, navigation now goes directly to CodeReviewView"
```

---

## Task 8: Integration Test

**Files:**
- All modified files

- [ ] **Step 1: Start backend and frontend, test the full flow**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
./deploy.sh start
```

1. **Create project**: Click "+ New Project", fill in name + path → Verify a "Direct" task is auto-created
2. **Navigate**: Click project card → Verify navigates to CodeReviewView
3. **Auto-select**: Verify Direct task is auto-selected and highlighted in task list
4. **Tabs**: Click "Commits" tab → Verify commits content shows; click "Changes" → Verify changes show
5. **Create task**: Click "+ New Task" in task list → Fill in name → Create → Verify new task appears in list
6. **Switch task**: Click a different task → Verify URL updates, data reloads, task highlights
7. **Delete protection**: Try to delete Direct task → Verify error message
8. **Back navigation**: Click back arrow → Verify navigates to ProjectsView

- [ ] **Step 2: Commit if all tests pass**

```bash
cd /home/xusongjie/workspace/vibe2death/vibe2crazy
git add -A
git commit -m "test: integration verification for remove-tasks-page feature"
```

---

## Self-Review Checklist

- [ ] Spec Section 1 (Routes): Task 3 covers router change. `/projects/:id` → CodeReviewView. `/tasks/:id` removed.
- [ ] Spec Section 2 (Auto-create Direct task): Task 1 covers backend auto-creation in `create_project`.
- [ ] Spec Section 3 (Sidebar restructure): Task 6 covers tabbed Changes/Commits + Task List pane.
- [ ] Spec Section 4 (In-place switch): Task 5 covers `switchTask` function and taskId computed change.
- [ ] Spec Section 5 (ProjectsView): Task 4 verifies navigation is already correct.
- [ ] Spec Section 6 (Mount flow): Task 5 Step 4 covers auto-select Direct task on mount.
- [ ] Spec Section 7 (Auto-refresh): Existing `startRefresh()` continues to work. No new code needed.
- [ ] Spec Section 8 (Create dialog): Task 6 Step 3 covers task creation dialog in CodeReviewView.
- [ ] Spec Section 9 (Cleanup): Task 7 deletes TasksView.vue.
- [ ] Spec Section 10 (Edge cases): Direct task protected by Task 2. Invalid task ID falls back to first task in Step 4 of Task 5.
- [ ] No placeholder code in plan. All code snippets are complete and runnable.
- [ ] Type consistency: `taskId` computed uses `route.query.task`. `projectId` computed uses `route.params.id`. `tasks.value` is `Task[]`. All consistent.

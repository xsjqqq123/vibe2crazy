# Directly on the Branch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Directly on the Branch" option when creating tasks, allowing tasks to work directly on the project's main branch without creating a Git worktree.

**Architecture:** Add a `direct_on_branch` boolean field to the Task model. When true, skip worktree/branch creation and use the project's git_path directly. Modify create/delete endpoints and UI accordingly.

**Tech Stack:** Python/FastAPI (backend), Vue 3/TypeScript (frontend), SQLAlchemy/Alembic (database)

---

## Task 1: Database Model Update

**Files:**
- Modify: `backend/app/models.py:46-69`

- [ ] **Step 1: Add `direct_on_branch` field to Task model**

```python
# In backend/app/models.py, add after line 65 (after extra_index_paths):
    direct_on_branch = Column(Boolean, default=False)
```

- [ ] **Step 2: Commit model change**

```bash
git add backend/app/models.py
git commit -m "feat(models): add direct_on_branch field to Task model

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Alembic Migration

**Files:**
- Create: `backend/alembic/versions/<hash>_add_direct_on_branch.py`

- [ ] **Step 1: Create migration file**

Run from `backend/` directory:
```bash
cd backend && alembic revision -m "add_direct_on_branch_to_tasks"
```

- [ ] **Step 2: Write migration upgrade/downgrade**

Replace the generated file content with:

```python
"""add direct_on_branch to tasks

Revision ID: <generated>
Revises: 6b947996d2bb
Create Date: 2026-03-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '<generated>'
down_revision: Union[str, Sequence[str], None] = '6b947996d2bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('direct_on_branch', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('tasks', 'direct_on_branch')
```

- [ ] **Step 3: Run migration**

```bash
cd backend && alembic upgrade head
```

- [ ] **Step 4: Commit migration**

```bash
git add backend/alembic/versions/*_add_direct_on_branch_to_tasks.py
git commit -m "feat(db): add migration for direct_on_branch field

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: API Schema Updates

**Files:**
- Modify: `backend/app/schemas.py:44-69`

- [ ] **Step 1: Update TaskCreate schema**

```python
# In backend/app/schemas.py, change TaskCreate class (line 48-49):
class TaskCreate(TaskBase):
    direct_on_branch: bool = False
```

- [ ] **Step 2: Update TaskResponse schema**

```python
# In backend/app/schemas.py, add to TaskResponse class (after line 64, before created_at):
    direct_on_branch: bool
```

- [ ] **Step 3: Commit schema changes**

```bash
git add backend/app/schemas.py
git commit -m "feat(schemas): add direct_on_branch to TaskCreate and TaskResponse

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Backend Task Creation Logic

**Files:**
- Modify: `backend/app/routers/tasks.py:28-108`

- [ ] **Step 1: Modify create_task endpoint to handle direct_on_branch**

Replace the `create_task` function (lines 28-108) with:

```python
@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: str,
    task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: Project = Depends(require_auth)
):
    """Create a new task with git worktree and tmux session"""
    logger.info(f"Creating task '{task.name}' for project {project_id}")

    # Get project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"Task creation failed: Project {project_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Generate unique identifiers
    task_id = str(uuid.uuid4())
    tmux_session = f"{settings.tmux_session_prefix}{project.name}-{task_id}"

    logger.info(f"Task ID: {task_id}")
    logger.info(f"Tmux session: {tmux_session}")

    if task.direct_on_branch:
        # Direct on branch mode: work on main branch directly
        branch_name = f"direct-{project.main_branch}-{task_id[:8]}"
        worktree_path = project.git_path

        logger.info(f"Direct on branch mode")
        logger.info(f"Branch name: {branch_name}")
        logger.info(f"Worktree path: {worktree_path}")

        # Create tmux session only (no worktree/branch creation)
        logger.info(f"Creating tmux session: {tmux_session}")
        tmux_success, tmux_msg = TmuxService.create_session(tmux_session, worktree_path)
        if not tmux_success:
            logger.error(f"Failed to create tmux session: {tmux_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create tmux session: {tmux_msg}"
            )
        logger.info(f"Tmux session created successfully")
    else:
        # Normal mode: create new branch and worktree
        branch_name = generate_branch_name(task.name)

        # Create worktrees directory alongside the original repository
        repo_path = Path(project.git_path).resolve()
        worktrees_base = repo_path.parent / f"{repo_path.name}-worktrees"
        worktree_path = str((worktrees_base / branch_name).resolve())

        logger.info(f"Normal mode")
        logger.info(f"Branch name: {branch_name}")
        logger.info(f"Worktree path: {worktree_path}")

        # Create git worktree
        logger.info(f"Creating git worktree at {worktree_path}")
        worktree_success, worktree_msg = GitService.create_worktree(
            repo_path=project.git_path,
            branch_name=branch_name,
            worktree_path=worktree_path
        )

        if not worktree_success:
            logger.error(f"Failed to create worktree: {worktree_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create worktree: {worktree_msg}"
            )
        logger.info(f"Worktree created successfully")

        # Create tmux session
        logger.info(f"Creating tmux session: {tmux_session}")
        tmux_success, tmux_msg = TmuxService.create_session(tmux_session, worktree_path)
        if not tmux_success:
            logger.error(f"Failed to create tmux session: {tmux_msg}")
            # Rollback worktree creation
            GitService.delete_worktree(worktree_path, project.git_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create tmux session: {tmux_msg}"
            )
        logger.info(f"Tmux session created successfully")

    # Create task in database
    db_task = Task(
        id=task_id,
        project_id=project_id,
        name=task.name,
        branch_name=branch_name,
        worktree_path=worktree_path,
        tmux_session=tmux_session,
        status=TaskStatus.active,
        direct_on_branch=task.direct_on_branch
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    logger.info(f"Task '{task.name}' created successfully (ID: {task_id})")
    return db_task
```

- [ ] **Step 2: Commit creation logic change**

```bash
git add backend/app/routers/tasks.py
git commit -m "feat(tasks): support direct_on_branch in task creation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Backend Delete Logic

**Files:**
- Modify: `backend/app/routers/tasks.py:184-221` (delete_task)
- Modify: `backend/app/routers/tasks.py:246-279` (delete_task_by_id)

- [ ] **Step 1: Modify delete_task endpoint**

Replace lines 207-214 with:

```python
    # Kill tmux session
    logger.info(f"Killing tmux session: {task.tmux_session}")
    TmuxService.kill_session(task.tmux_session)

    # Only delete worktree for non-direct tasks
    if not task.direct_on_branch and project:
        logger.info(f"Deleting worktree: {task.worktree_path}")
        GitService.delete_worktree(task.worktree_path, project.git_path)

    # Delete from database
    db.delete(task)
    db.commit()
```

- [ ] **Step 2: Modify delete_task_by_id endpoint**

Replace lines 265-272 with:

```python
    # Kill tmux session
    logger.info(f"Killing tmux session: {task.tmux_session}")
    TmuxService.kill_session(task.tmux_session)

    # Only delete worktree for non-direct tasks
    if not task.direct_on_branch and project:
        logger.info(f"Deleting worktree: {task.worktree_path}")
        GitService.delete_worktree(task.worktree_path, project.git_path)

    # Delete from database
    db.delete(task)
    db.commit()
```

- [ ] **Step 3: Commit delete logic change**

```bash
git add backend/app/routers/tasks.py
git commit -m "feat(tasks): skip worktree deletion for direct_on_branch tasks

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Backend Button States Logic

**Files:**
- Modify: `backend/app/routers/tasks.py:305-374`

- [ ] **Step 1: Add early return for direct_on_branch in get_button_states**

Add after line 329 (after project check, before try block):

```python
    # Direct on branch tasks cannot merge
    if task.direct_on_branch:
        try:
            changed_files = GitService.get_changed_files(task.worktree_path, project.main_branch)
            has_uncommitted = len(changed_files) > 0
            return ButtonStatesResponse(
                can_accept=has_uncommitted,
                can_merge=False,
                reason="Direct on branch tasks do not support merge"
            )
        except Exception as e:
            logger.error(f"Error getting button states for task {task_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
```

- [ ] **Step 2: Commit button states change**

```bash
git add backend/app/routers/tasks.py
git commit -m "feat(tasks): disable merge button for direct_on_branch tasks

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Backend Code Status Monitoring

**Files:**
- Modify: `backend/app/services/task_monitor_service.py:160-191`

- [ ] **Step 1: Modify update_code_status to handle direct_on_branch**

Replace the `update_code_status` method (lines 160-191) with:

```python
    def update_code_status(self, task: Task, db: Session):
        """Update code status by checking git state"""
        project = db.query(Project).filter(Project.id == task.project_id).first()
        if not project:
            logger.warning(f"Task {task.id}: project not found")
            return

        try:
            # Check for uncommitted changes
            changed_files = GitService.get_changed_files(task.worktree_path, project.main_branch)
            has_uncommitted = len(changed_files) > 0

            # For direct_on_branch tasks, skip ready_to_merge status
            if task.direct_on_branch:
                if has_uncommitted:
                    task.code_status = CodeStatusType.pending_review
                    logger.debug(f"Task {task.id}: pending_review ({len(changed_files)} uncommitted files)")
                else:
                    task.code_status = CodeStatusType.no_changes
                    logger.debug(f"Task {task.id}: no_changes (direct on branch)")

                task.last_code_status_check = datetime.now(timezone.utc)
                return

            # Normal mode: check for commits ahead of main
            branch_status = GitService.get_branch_status(task.worktree_path)
            has_unmerged = branch_status["commits_ahead"] > 0

            # Determine code status (pending_review takes priority)
            if has_uncommitted:
                task.code_status = CodeStatusType.pending_review
                logger.debug(f"Task {task.id}: pending_review ({len(changed_files)} uncommitted files)")
            elif has_unmerged:
                task.code_status = CodeStatusType.ready_to_merge
                logger.debug(f"Task {task.id}: ready_to_merge ({branch_status['commits_ahead']} commits ahead)")
            else:
                task.code_status = CodeStatusType.no_changes
                logger.debug(f"Task {task.id}: no_changes")

            task.last_code_status_check = datetime.now(timezone.utc)

        except Exception as e:
            logger.error(f"Task {task.id}: error updating code status: {e}")
            # Don't crash the monitoring loop
```

- [ ] **Step 2: Commit monitor service change**

```bash
git add backend/app/services/task_monitor_service.py
git commit -m "feat(monitor): skip ready_to_merge for direct_on_branch tasks

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Frontend API Types

**Files:**
- Modify: `frontend/src/api/tasks.ts:37-57`

- [ ] **Step 1: Add direct_on_branch to Task interface**

```typescript
// In frontend/src/api/tasks.ts, add to Task interface (after line 50):
  direct_on_branch: boolean
```

- [ ] **Step 2: Add direct_on_branch to TaskCreate interface**

```typescript
// In frontend/src/api/tasks.ts, change TaskCreate interface:
export interface TaskCreate {
  name: string
  direct_on_branch?: boolean
}
```

- [ ] **Step 3: Commit frontend API types**

```bash
git add frontend/src/api/tasks.ts
git commit -m "feat(api): add direct_on_branch to Task and TaskCreate types

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: Frontend Create Task Dialog

**Files:**
- Modify: `frontend/src/views/TasksView.vue:22-25` (script)
- Modify: `frontend/src/views/TasksView.vue:114-133` (createTask function)
- Modify: `frontend/src/views/TasksView.vue:265-297` (template dialog)

- [ ] **Step 1: Add newTaskDirectOnBranch ref**

Add after line 24:
```typescript
const newTaskDirectOnBranch = ref(false)
```

- [ ] **Step 2: Modify createTask function**

Replace the createTask function (lines 114-133):

```typescript
const createTask = async () => {
  if (!newTaskName.value.trim()) {
    createError.value = 'Please enter a task name'
    return
  }

  loading.value = true
  createError.value = ''

  try {
    await tasksApi.create(projectId.value, {
      name: newTaskName.value,
      direct_on_branch: newTaskDirectOnBranch.value
    })
    showCreateDialog.value = false
    newTaskName.value = ''
    newTaskDirectOnBranch.value = false
    await loadTasks()
  } catch (err: any) {
    createError.value = err.message || 'Failed to create task'
  }

  loading.value = false
}
```

- [ ] **Step 3: Update create task dialog template**

Replace the dialog section (lines 265-297):

```vue
    <!-- Create task dialog -->
    <div v-if="showCreateDialog" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card max-w-md w-full">
        <h3 class="text-lg font-semibold text-main mb-4">Create New Task</h3>

        <form @submit.prevent="createTask" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-sub mb-2">
              Task Name *
            </label>
            <input v-model="newTaskName" type="text" class="input w-full" placeholder="Implement feature X" />
          </div>

          <div class="flex items-start gap-2">
            <input
              type="checkbox"
              id="directOnBranch"
              v-model="newTaskDirectOnBranch"
              class="mt-1"
            />
            <label for="directOnBranch" class="text-sm text-sub">
              <span class="font-medium text-main">Directly on the branch</span>
              <br />
              <span class="text-xs">Work directly on main branch, no worktree created, merge not supported.</span>
            </label>
          </div>

          <div v-if="createError" class="text-red-600 dark:text-red-400 text-sm">
            {{ createError }}
          </div>

          <div class="flex gap-3 justify-end">
            <button type="button" @click="showCreateDialog = false; newTaskDirectOnBranch = false" class="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" :disabled="loading" class="btn btn-primary">
              <span v-if="loading" class="spinner mr-2"></span>
              Create
            </button>
          </div>
        </form>

        <p v-if="!newTaskDirectOnBranch" class="text-xs text-sub mt-4">
          A new Git worktree and tmux session will be created for this task.
        </p>
        <p v-else class="text-xs text-amber-600 dark:text-amber-400 mt-4">
          Warning: Multiple direct-on-branch tasks share the same working directory.
        </p>
      </div>
    </div>
```

- [ ] **Step 4: Commit frontend create dialog**

```bash
git add frontend/src/views/TasksView.vue
git commit -m "feat(ui): add direct_on_branch checkbox to task creation dialog

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Frontend TaskCard Badge

**Files:**
- Modify: `frontend/src/components/TaskCard.vue:41-42`

- [ ] **Step 1: Add "Direct" badge to TaskCard**

Replace lines 41-42 with:

```vue
      <div class="flex items-center gap-2">
        <h3 class="text-lg font-semibold text-main">{{ task.name }}</h3>
        <span v-if="task.direct_on_branch" class="px-1.5 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 rounded">
          Direct
        </span>
      </div>
      <p class="text-sm text-sub">{{ task.branch_name }}</p>
```

- [ ] **Step 2: Commit TaskCard change**

```bash
git add frontend/src/components/TaskCard.vue
git commit -m "feat(ui): show Direct badge for direct_on_branch tasks

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 11: Frontend CodeReviewView Notice Banner

**Files:**
- Modify: `frontend/src/views/CodeReviewView.vue:1598-1654` (header section)

- [ ] **Step 1: Add notice banner for direct_on_branch tasks**

Add after the header div (around line 1655, before the main splitpanes):

```vue
    <!-- Direct on branch notice -->
    <div v-if="task?.direct_on_branch" class="bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-800 px-4 py-2">
      <div class="max-w-full mx-auto flex items-center gap-2 text-sm text-amber-700 dark:text-amber-300">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <span>This task works directly on main branch. Changes are committed immediately. Merge is not supported.</span>
      </div>
    </div>
```

- [ ] **Step 2: Commit notice banner**

```bash
git add frontend/src/views/CodeReviewView.vue
git commit -m "feat(ui): add notice banner for direct_on_branch tasks

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 12: Frontend CodeReviewView Merge Button

**Files:**
- Modify: `frontend/src/views/CodeReviewView.vue:1756-1766`

- [ ] **Step 1: Hide merge button for direct_on_branch tasks**

Replace the merge button (lines 1756-1766) with:

```vue
                  <button
                    v-if="!task?.direct_on_branch"
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
```

- [ ] **Step 2: Commit CodeReviewView change**

```bash
git add frontend/src/views/CodeReviewView.vue
git commit -m "feat(ui): hide merge button for direct_on_branch tasks

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 13: Integration Test

- [ ] **Step 1: Start the development environment**

```bash
./deploy.sh restart
```

- [ ] **Step 2: Test direct_on_branch task creation**
1. Open the application in browser
2. Navigate to a project
3. Click "New Task"
4. Enter task name "test-direct"
5. Check "Directly on the branch" checkbox
6. Verify the warning message appears
7. Click "Create"
8. Verify task is created with "Direct" badge
9. Verify no new worktree was created (check in terminal)

- [ ] **Step 3: Test CodeReviewView for direct_on_branch tasks**
1. Click on the direct_on_branch task to open CodeReviewView
2. Verify the amber notice banner is displayed
3. Verify the merge button is hidden

- [ ] **Step 4: Test normal task still works**
1. Create a task without checking "Directly on the branch"
2. Verify worktree is created
3. Verify merge button is visible in CodeReviewView
4. Verify no notice banner is shown

- [ ] **Step 5: Test delete behavior**
1. Delete the direct_on_branch task
2. Verify tmux session is killed but code changes remain on main branch
3. Delete the normal task
4. Verify worktree is cleaned up

---

## Summary

This plan implements the "Directly on the Branch" feature with the following changes:

**Backend:**
- Database: Add `direct_on_branch` boolean field with migration
- Schemas: Update TaskCreate and TaskResponse
- Routes: Modify create/delete logic, disable merge for direct tasks
- Monitor: Skip `ready_to_merge` status for direct tasks

**Frontend:**
- Types: Add `direct_on_branch` to Task and TaskCreate interfaces
- TasksView: Add checkbox with description and warning
- TaskCard: Show "Direct" badge
- CodeReviewView: Add notice banner, hide merge button for direct tasks

**Out of Scope:**
- Pull functionality: The Pull button/endpoint does not currently exist in the codebase. When pull is implemented in the future, it should be disabled or show a warning for direct_on_branch tasks since pulling affects all such tasks on the same project.
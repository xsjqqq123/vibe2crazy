# Directly on the Branch Feature Design

Date: 2026-03-25
Updated: 2026-03-25 (after spec review)

## Overview

Add a "Directly on the branch" option when creating tasks. When enabled, the task works directly on the project's main branch instead of creating a new Git worktree and branch. Code changes are committed directly to the main branch, and merge operation is not supported.

## Requirements Summary

1. User can select "Directly on the branch" checkbox when creating a task
2. Task works on project's main branch (no worktree, no new branch)
3. Tmux session is created in the project's git directory
4. Code commits go directly to main branch
5. Merge operation is disabled for this task type
6. Multiple "direct on branch" tasks can exist simultaneously
7. Deleting task only removes tmux session and database record (preserves code changes)

## Technical Design

### 1. Database Model

Add new field to `Task` model in `backend/app/models.py`:

```python
class Task(Base):
    __tablename__ = "tasks"
    # ... existing fields ...
    direct_on_branch = Column(Boolean, default=False)
```

For `direct_on_branch=True` tasks:
- `worktree_path` = project's `git_path`
- `branch_name` = `direct-{main_branch}-{task_id[:8]}` (unique identifier for database constraint)
- `tmux_session` = created normally, working directory points to project repo

**Note on `branch_name` unique constraint:** The existing `branch_name` field has a `unique=True` constraint. Since multiple direct_on_branch tasks would all reference the same actual branch (main), we use a unique identifier format `direct-{branch}-{short_uuid}`. This preserves the database constraint while indicating the task works on the main branch.

### 2. API Schema Changes

**TaskCreate** (`backend/app/schemas.py`):
```python
class TaskCreate(TaskBase):
    direct_on_branch: bool = False
```

**TaskResponse** (`backend/app/schemas.py`):
```python
class TaskResponse(TaskBase):
    direct_on_branch: bool
    # ... other existing fields ...
```

### 3. Backend Task Creation Logic

Modify `create_task` endpoint in `backend/app/routers/tasks.py`:

```python
if task.direct_on_branch == False:
    # Existing logic: create new branch and worktree
    branch_name = generate_branch_name(task.name)
    worktree_path = create_worktree(...)
    tmux_session = create_session(tmux_session, worktree_path)

if task.direct_on_branch == True:
    # New logic: work directly on main branch
    branch_name = f"direct-{project.main_branch}-{task_id[:8]}"
    worktree_path = project.git_path
    tmux_session = f"{settings.tmux_session_prefix}{project.name}-{task_id}"
    TmuxService.create_session(tmux_session, worktree_path)
    # Do NOT create worktree or new git branch
```

### 4. Merge Behavior

**Backend - `get_button_states` endpoint modification** (`routers/tasks.py`):

```python
@task_router.get("/{task_id}/button-states", response_model=ButtonStatesResponse)
async def get_button_states(...):
    # ... existing code ...

    # Direct on branch tasks cannot merge
    if task.direct_on_branch:
        return ButtonStatesResponse(
            can_accept=has_uncommitted,
            can_merge=False,
            reason="Direct on branch tasks do not support merge"
        )

    # ... rest of existing logic ...
```

**Frontend:**
- If `task.direct_on_branch == True`, hide Merge button
- Show badge/indicator that this is a "Direct on Branch" task

### 5. Delete Behavior

**Both delete endpoints must be modified** (`routers/tasks.py`):

**`delete_task` (line 184) and `delete_task_by_id` (line 246):**

```python
# Kill tmux session
TmuxService.kill_session(task.tmux_session)

# Only delete worktree for non-direct tasks
if not task.direct_on_branch:
    if project:
        GitService.delete_worktree(task.worktree_path, project.git_path)

# Delete from database
db.delete(task)
db.commit()
```

### 6. Accept (Commit) Operation

The `accept_changes` endpoint in `routers/git.py` uses `GitService.auto_commit_worktree(task.worktree_path, ...)`. For direct_on_branch tasks, `worktree_path = project.git_path`, so this works correctly - commits go directly to the main branch.

### 7. Pull Operation

Pull operation works but with caveats for direct_on_branch tasks:

**Backend - `pull_worktree` endpoint** (may need modification to handle direct_on_branch):
- Pull fetches from `origin/{main_branch}` into the working directory
- For direct_on_branch tasks, this updates the shared main branch
- **Warning:** Pulling affects all other direct_on_branch tasks on the same project

**Frontend consideration:**
- Consider showing a warning when pulling for direct_on_branch tasks
- Or disable pull for direct_on_branch tasks

### 8. Code Status Monitoring

The `TaskMonitorService` checks git status for tasks. For direct_on_branch tasks:

- `task_status`: Same logic (check tmux for running processes)
- `code_status`:
  - `pending_review` = uncommitted changes exist
  - `ready_to_merge` = NOT applicable for direct_on_branch (set to `no_changes` after commit)
  - `no_changes` = clean working directory

**Modification needed** in `task_monitor_service.py`:
```python
if task.direct_on_branch:
    # Skip ready_to_merge status for direct_on_branch tasks
    if has_uncommitted:
        code_status = CodeStatusType.pending_review
    else:
        code_status = CodeStatusType.no_changes
```

### 9. Frontend Changes

**TasksView.vue - Create Task Dialog:**
- Add checkbox "Directly on the branch"
- Show description: "Work directly on main branch, no worktree created, merge not supported"
- Add warning: "Multiple direct-on-branch tasks share the same working directory"

**frontend/src/api/tasks.ts - Update Task interface:**
```typescript
export interface Task {
  id: string
  project_id: string
  name: string
  branch_name: string
  worktree_path: string
  tmux_session: string
  status: TaskStatus
  direct_on_branch: boolean  // Add this field
  // ... other fields ...
}
```

**TaskCard.vue:**
- Show badge "Direct" for direct_on_branch tasks
- Hide Merge button for direct_on_branch tasks

**CodeReviewView.vue:**
- Hide Merge button for direct_on_branch tasks
- Show notice "This task works directly on main branch. Changes are committed immediately."

### 10. File Operations

File operations in `routers/files.py` use `task.worktree_path`. For direct_on_branch tasks:
- `worktree_path = project.git_path`
- All file read/write operations work on the project's main repository
- No changes needed to file service logic

## Files to Modify

### Backend
- `backend/app/models.py` - Add `direct_on_branch` field
- `backend/app/schemas.py` - Update TaskCreate and TaskResponse
- `backend/app/routers/tasks.py` - Modify create_task, delete_task, delete_task_by_id, get_button_states
- `backend/app/services/task_monitor_service.py` - Adjust code_status logic for direct_on_branch

### Frontend
- `frontend/src/api/tasks.ts` - Update Task interface and TaskCreate type
- `frontend/src/views/TasksView.vue` - Add checkbox to create dialog
- `frontend/src/components/TaskCard.vue` - Add "Direct" badge, hide merge button
- `frontend/src/views/CodeReviewView.vue` - Hide merge button, show notice

## Migration

**Alembic migration:**

```python
def upgrade():
    op.add_column('tasks', sa.Column('direct_on_branch', sa.Boolean(), nullable=False, server_default='0'))

def downgrade():
    op.drop_column('tasks', 'direct_on_branch')
```

The migration adds `direct_on_branch` column with:
- `nullable=False`
- `server_default='0'` (False)
- All existing tasks will have `direct_on_branch=False`

## Edge Cases

1. **Multiple direct-on-branch tasks**: Users can create multiple tasks working on the same branch. They share the same working directory state. Changes made in one task are immediately visible to others.

2. **Task status monitoring**: Adjusted to not show `ready_to_merge` for direct_on_branch tasks.

3. **Pull operation**: Works but affects all direct_on_branch tasks on the same project. Consider adding a warning.

4. **Conflict resolution**: Since merge is not supported, conflicts from pull must be resolved in the terminal.

5. **Simultaneous terminal sessions**: Multiple tmux sessions can be attached to the same working directory. Users should be aware of potential conflicts.

6. **Delete while working**: Deleting a direct_on_branch task kills the tmux session but preserves all code changes on the main branch.

## Out of Scope

- Branch selection (always uses main branch)
- Change tracking per task (all changes are on main branch)
- Rollback on delete (preserves all committed changes)
- Preventing multiple direct_on_branch tasks (allowed but user should manage carefully)
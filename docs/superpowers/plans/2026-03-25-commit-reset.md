# Commit Reset Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add right-click context menu to Commits panel allowing users to reset the working directory to a specific commit (git reset --mixed).

**Architecture:** Add context menu to CommitsList component, reuse existing ContextMenu and useConfirm components, add new backend endpoint for git reset operation.

**Tech Stack:** Vue 3 + TypeScript (frontend), FastAPI + Python (backend)

---

## Task 1: Backend Git Service Method

**Files:**
- Modify: `backend/app/services/git_service.py`

- [ ] **Step 1: Add reset_to_commit method**

Add to `GitService` class (after other static methods):

```python
@staticmethod
def reset_to_commit(worktree_path: str, commit_hash: str) -> tuple[bool, str]:
    """Reset working directory to specified commit (git reset --mixed).

    Args:
        worktree_path: Path to the git worktree
        commit_hash: Hash of the commit to reset to

    Returns:
        Tuple of (success, message)
    """
    try:
        cmd = [
            "git", "-C", worktree_path,
            "reset", "--mixed", commit_hash
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True, encoding="utf-8",
            check=False
        )

        if result.returncode == 0:
            return True, f"Reset to commit {commit_hash[:8]}"
        else:
            return False, result.stderr or "Unknown error"
    except Exception as e:
        return False, str(e)
```

- [ ] **Step 2: Commit backend service change**

```bash
git add backend/app/services/git_service.py
git commit -m "feat(git): add reset_to_commit method for git reset --mixed

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Backend API Endpoint

**Files:**
- Modify: `backend/app/routers/git.py`
- Create: `backend/app/schemas.py` (add ResetRequest schema if not exists)

- [ ] **Step 1: Add ResetRequest schema**

Check if `ResetRequest` exists in `schemas.py`. If not, add:

```python
class ResetRequest(BaseModel):
    commit_hash: str
```

- [ ] **Step 2: Add reset endpoint to git.py**

Add after other endpoints:

```python
class ResetRequest(BaseModel):
    commit_hash: str

class ResetResponse(BaseModel):
    success: bool
    message: str

@router.post("/{task_id}/reset", response_model=ResetResponse)
async def reset_to_commit(
    task_id: str,
    reset_request: ResetRequest,
    db: Session = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Reset task worktree to a specific commit (mixed reset)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    success, message = GitService.reset_to_commit(
        worktree_path=task.worktree_path,
        commit_hash=reset_request.commit_hash
    )

    return ResetResponse(success=success, message=message)
```

- [ ] **Step 3: Commit backend API change**

```bash
git add backend/app/routers/git.py
git commit -m "feat(api): add POST /tasks/{task_id}/reset endpoint

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Frontend API Function

**Files:**
- Modify: `frontend/src/api/git.ts`

- [ ] **Step 1: Add resetToCommit function**

Add to `git.ts`:

```typescript
export interface ResetResponse {
  success: boolean
  message: string
}

export async function resetToCommit(
  taskId: string,
  commitHash: string
): Promise<ResetResponse> {
  return request<ResetResponse>(`/tasks/${taskId}/reset`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ commit_hash: commitHash })
  })
}
```

- [ ] **Step 2: Export in gitApi object**

Update the gitApi export:

```typescript
export const gitApi = {
  getWorktreeCommits,
  getCommitDiff,
  resetToCommit
}
```

- [ ] **Step 3: Commit frontend API change**

```bash
git add frontend/src/api/git.ts
git commit -m "feat(api): add resetToCommit function

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: CommitsList Component Context Menu

**Files:**
- Modify: `frontend/src/components/CommitsList.vue`

- [ ] **Step 1: Add context menu event emit**

Update the emit definition to include context menu event:

```typescript
const emit = defineEmits<{
  select: [commitHash: string]
  showContextMenu: [event: { x: number; y: number; commit: CommitInfo }]
}>()
```

- [ ] **Step 2: Add contextmenu handler**

Add handler function:

```typescript
const handleContextMenu = (e: MouseEvent, commit: CommitInfo) => {
  e.preventDefault()
  e.stopPropagation()
  emit('showContextMenu', {
    x: e.clientX,
    y: e.clientY,
    commit
  })
}
```

- [ ] **Step 3: Add @contextmenu to commit item template**

Update the commit item div (around line 107-116) to include contextmenu handler:

```vue
<div
  v-for="commit in commits"
  :key="commit.hash"
  :class="{
    'commit-item': true,
    'p-2 bg-sub rounded cursor-pointer hover:bg-accent/10': true,
    'new-commit': isNewCommit(commit.hash)
  }"
  @click="emit('select', commit.hash)"
  @contextmenu.prevent.stop="handleContextMenu($event, commit)"
>
```

- [ ] **Step 4: Commit CommitsList changes**

```bash
git add frontend/src/components/CommitsList.vue
git commit -m "feat(ui): add context menu support to CommitsList

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: CodeReviewView Context Menu Integration

**Files:**
- Modify: `frontend/src/views/CodeReviewView.vue`

- [ ] **Step 1: Add commit context menu state**

Add to the contextMenu ref (around line 63):

```typescript
const contextMenu = ref({
  show: false,
  x: 0,
  y: 0,
  path: '',
  type: '',
  source: 'files' as 'files' | 'changedFiles' | 'commits',
  commit: null as CommitInfo | null  // For commits context menu
})
```

- [ ] **Step 2: Import gitApi resetToCommit**

Ensure gitApi is imported and add CommitInfo type if needed:

```typescript
import { gitApi, type CommitInfo } from '@/api/git'
```

- [ ] **Step 3: Add handleCommitContextMenu function**

```typescript
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
```

- [ ] **Step 4: Update contextMenuItems computed to include commits menu**

Find `contextMenuItems` computed (around line 1326) and add commits section:

```typescript
const contextMenuItems = computed<MenuItem[]>(() => {
  const items: MenuItem[] = []

  // Files context menu items
  if (contextMenu.value.source === 'files') {
    // ... existing files menu items ...
  }
  // Changed files context menu items
  else if (contextMenu.value.source === 'changedFiles') {
    // ... existing changed files menu items ...
  }
  // Commits context menu items
  else if (contextMenu.value.source === 'commits' && contextMenu.value.commit) {
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
  }

  return items
})
```

- [ ] **Step 5: Update CommitsList component usage**

Update the CommitsList component (around line 1780) to include the context menu handler:

```vue
<CommitsList
  :commits="commits"
  :loading="loadingCommits"
  :error="commitsError"
  :lastMergeCommitHash="task?.last_merge_commit_hash"
  :newCommitHashes="newCommitHashes"
  @select="loadCommitDiff"
  @showContextMenu="handleCommitContextMenu"
/>
```

- [ ] **Step 6: Commit CodeReviewView changes**

```bash
git add frontend/src/views/CodeReviewView.vue
git commit -m "feat(ui): add reset context menu to Commits panel

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Integration Test

- [ ] **Step 1: Restart services**

```bash
./deploy.sh restart
```

- [ ] **Step 2: Test reset functionality**

1. Open the application in browser
2. Navigate to a task with commits
3. Right-click on a commit in the Commits panel
4. Verify context menu shows "Reset to this commit"
5. Click the menu item
6. Verify confirmation dialog appears with correct commit count
7. Click "Reset"
8. Verify commits list refreshes and changes appear in working directory

- [ ] **Step 3: Test cancel functionality**

1. Right-click on a commit
2. Click "Reset to this commit"
3. Click "Cancel" in confirmation dialog
4. Verify no changes are made

---

## Summary

**Backend (3 commits):**
- Task 1: GitService.reset_to_commit method
- Task 2: POST /api/tasks/{task_id}/reset endpoint

**Frontend (3 commits):**
- Task 3: resetToCommit API function
- Task 4: CommitsList context menu emit
- Task 5: CodeReviewView context menu integration

**Total: 5 implementation commits + 1 integration test**
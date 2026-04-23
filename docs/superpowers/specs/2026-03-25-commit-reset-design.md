# Commit Reset Feature Design

## Overview

Add right-click context menu to Commits panel allowing users to reset the working directory to a specific commit. Changes are kept in the working directory (equivalent to `git reset --mixed`).

## User Flow

1. User right-clicks on a commit item in the Commits panel
2. Context menu appears with single option: "Reset to this commit"
3. Confirmation dialog shows the number of commits that will be undone
4. User clicks "Reset" to confirm, or "Cancel" to abort
5. After successful reset, the commits list refreshes automatically

## Technical Design

### Frontend

**File: `frontend/src/components/CommitsList.vue`**

Modifications:
- Import existing `ContextMenu` component
- Import existing `useConfirm` composable
- Add `@contextmenu` event handler on commit items
- Add state for context menu position and visibility
- Add API call to new reset endpoint
- Emit event to parent for refresh after successful reset

**File: `frontend/src/api/git.ts`**

Add new function:
```typescript
export async function resetToCommit(taskId: string, commitHash: string): Promise<{ success: boolean; message: string }>
```

### Backend

**File: `backend/app/routers/git.py`**

New endpoint:
```
POST /api/tasks/{task_id}/reset
Body: { "commit_hash": "abc1234..." }
Response: { "success": true, "message": "Reset to commit abc1234" }
```

**File: `backend/app/services/git_service.py`**

New method:
```python
@staticmethod
def reset_to_commit(worktree_path: str, commit_hash: str) -> tuple[bool, str]:
    """Reset working directory to specified commit (git reset --mixed).

    Returns:
        Tuple of (success, message)
    """
```

Implementation:
```python
cmd = ["git", "-C", worktree_path, "reset", "--mixed", commit_hash]
result = subprocess.run(cmd, capture_output=True, text=True)
return result.returncode == 0, result.stdout or result.stderr
```

## Component Reuse

- **ContextMenu.vue** - Existing component, supports `MenuItem[]` with `label`, `icon`, `action`, `danger` props
- **useConfirm()** - Existing composable, supports `title`, `message`, `confirmText`, `cancelText`, `danger`

## Error Handling

- If reset fails, show error toast with the error message from the API
- If reset succeeds, show success toast and refresh the commits list

## Out of Scope

- Soft reset (keep changes staged)
- Hard reset (discard changes)
- Revert (create inverse commit)
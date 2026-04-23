# Reset Include Commit Feature Design

## Overview

Add a second context menu option "Reset to this commit (include it)" that undoes the selected commit along with all commits after it.

## User Flow

1. User right-clicks on a commit item in the Commits panel
2. Context menu appears with two options:
   - "Reset to this commit" - HEAD becomes selected commit, undoes commits after it
   - "Reset to this commit (include it)" - HEAD becomes parent of selected commit, undoes selected commit + commits after it
3. Confirmation dialog shows the number of commits that will be undone
4. User clicks "Reset" to confirm, or "Cancel" to abort
5. After successful reset, the commits list refreshes automatically

## Technical Design

### Frontend

**File: `frontend/src/views/CodeReviewView.vue`**

Add second context menu item in the `contextMenuItems` computed property:

```typescript
// Existing item
{
  label: 'Reset to this commit',
  icon: '↩️',
  action: async () => { ... }
}

// New item
{
  label: 'Reset to this commit (include it)',
  icon: '↩️',
  action: async () => {
    // Call API with include_commit: true
    // Confirmation shows commitsToUndo + 1
  }
}
```

**File: `frontend/src/api/git.ts`**

Extend `resetToCommit` function:

```typescript
export async function resetToCommit(
  taskId: string,
  commitHash: string,
  includeCommit: boolean = false
): Promise<ResetResponse> {
  return request<ResetResponse>(`/tasks/${taskId}/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ commit_hash: commitHash, include_commit: includeCommit })
  })
}
```

### Backend

**File: `backend/app/routers/git.py`**

Extend `ResetRequest` schema:

```python
class ResetRequest(BaseModel):
    commit_hash: str
    include_commit: bool = False
```

Pass `include_commit` to the service method.

**File: `backend/app/services/git_service.py`**

Update `reset_to_commit` method signature:

```python
@staticmethod
def reset_to_commit(worktree_path: str, commit_hash: str, include_commit: bool = False) -> tuple[bool, str]:
    """Reset working directory to specified commit (git reset --mixed).

    Args:
        worktree_path: Path to the git worktree
        commit_hash: Hash of the commit to reset to
        include_commit: If True, reset to parent of commit_hash (include selected commit in undo)

    Returns:
        Tuple of (success, message)
    """
```

Implementation:
- If `include_commit=False`: `git reset --mixed <commit_hash>`
- If `include_commit=True`: `git reset --mixed <commit_hash>^`

## Git Behavior Comparison

| Option | Git Command | Effect |
|--------|-------------|--------|
| Reset to this commit | `git reset --mixed X` | HEAD = X, undoes commits after X |
| Reset to this commit (include it) | `git reset --mixed X^` | HEAD = X^, undoes X + commits after X |

## Confirmation Dialog

- "Reset to this commit": Shows "This will undo N commit(s)"
- "Reset to this commit (include it)": Shows "This will undo N+1 commit(s)"

## Error Handling

- If selected commit has no parent (root commit), show error: "Cannot include the first commit"
- If reset fails, show error toast with the error message from the API
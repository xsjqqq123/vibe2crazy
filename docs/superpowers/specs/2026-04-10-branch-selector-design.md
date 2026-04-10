# Branch Selector for Project Creation

**Date:** 2026-04-10
**Status:** Draft
**Scope:** vibe2crazy frontend + backend

## Summary

When creating a project, after the user enters a git repository path, the "Main Branch" input field should become an editable dropdown that lists all local branches. The current checked-out branch is automatically detected and set as the default value, while allowing the user to select any other local branch or manually enter a custom branch name.

## Requirements

1. **Auto-detect current branch** - When a valid git path is entered, automatically load and display the current branch as the default value
2. **Dropdown branch list** - Provide a dropdown showing all local branches for selection
3. **Editable input** - User can still manually type any branch name (e.g., remote branches or branches not yet created)
4. **Graceful handling** - If the path is not a valid git repository, the dropdown should be empty/disabled but the input remains editable

## Architecture

### Backend

**New endpoint:** `GET /api/git/branches?path={repo_path}`

Location: `backend/app/routers/git.py` (branch_router)

```python
class BranchListResponse(BaseModel):
    branches: List[str]
    current_branch: str
    success: bool
    message: str | None = None

@branch_router.get("/branches", response_model=BranchListResponse)
async def get_branches(
    path: str = Query(..., description="Path to the git repository"),
    current_user = Depends(require_auth)
):
    """Get all local branches and current branch for a git repository"""
```

**New GitService method:** `get_local_branches(path: str)`

Location: `backend/app/services/git_service.py`

```python
@staticmethod
def get_local_branches(path: str) -> tuple[list[str], str]:
    """
    Get all local branch names and current branch.

    Returns: (branches_list, current_branch)

    Implementation:
    - Use `git branch --no-color` to list all local branches
    - Parse output: current branch has '*' prefix, others are plain names
    - Return sorted list of branch names and the current branch name
    """
```

### Frontend

**New API function:** `frontend/src/api/git.ts`

```typescript
export interface BranchListResponse {
  branches: string[]
  current_branch: string
  success: boolean
  message: string | null
}

export async function getBranches(gitPath: string): Promise<BranchListResponse> {
  return request<BranchListResponse>(`/git/branches?path=${encodeURIComponent(gitPath)}`)
}
```

**New component:** `frontend/src/components/BranchAutocomplete.vue`

A reusable dropdown component for branch selection, following the pattern of `DirectoryAutocomplete.vue`.

**Props:**
- `modelValue: string` - Current branch value
- `gitPath: string` - Path to the git repository (triggers branch loading)
- `disabled: boolean` - Disable the input and dropdown

**Emits:**
- `update:modelValue` - Branch value changed
- `blur` - Input lost focus

**Internal state:**
- `query: string` - Input field value
- `branches: string[]` - Loaded local branch list
- `currentBranch: string` - Detected current branch
- `showDropdown: boolean` - Dropdown visibility
- `highlightedIndex: number` - Keyboard navigation index
- `loading: boolean` - Loading state
- `isValidRepo: boolean` - Whether gitPath is a valid repository

**Behavior:**

1. Watch `gitPath` prop for changes
2. When `gitPath` changes to a non-empty value:
   - Call `getBranches(gitPath)`
   - On success: set `branches`, `currentBranch`, `isValidRepo = true`
   - Auto-fill `query` with `currentBranch` if query is empty
   - On failure: set `isValidRepo = false`, clear `branches`
3. Dropdown interaction:
   - Click dropdown button to show/hide list
   - Click branch name to select and close dropdown
   - Keyboard: ArrowUp/Down navigate, Enter select, Escape close
4. User can type any value in input (dropdown is optional)

**UI structure:**

```
┌─────────────────────────────────────────┐
│ [input field]                    [▼]    │  ← dropdown button
└─────────────────────────────────────────┘
         ↓ (click dropdown button)
┌─────────────────────────────────────────┐
│ main (current)                          │
│ develop                                 │
│ feature-x                               │
│ feature-y                               │
└─────────────────────────────────────────┘
```

**Modifications to ProjectsView.vue:**

- Remove `detectCurrentBranch()` function (logic moved to component)
- Replace the Main Branch `<input>` with `<BranchAutocomplete>`
- Bind `git-path` prop to `newProject.git_path`
- Remove `detectingBranch` state (handled by component)

```vue
<!-- Before -->
<input
  v-model="newProject.main_branch"
  type="text"
  class="input w-full"
  placeholder="main"
  :disabled="detectingBranch"
/>

<!-- After -->
<BranchAutocomplete
  v-model="newProject.main_branch"
  :git-path="newProject.git_path"
  placeholder="main"
/>
```

## Data Flow

```
User enters git_path in DirectoryAutocomplete
                ↓
DirectoryAutocomplete emits blur
                ↓
ProjectsView: newProject.git_path updated
                ↓
BranchAutocomplete watches gitPath prop change
                ↓
BranchAutocomplete calls GET /api/git/branches?path={git_path}
                ↓
Backend GitService.get_local_branches() runs git branch --no-color
                ↓
API returns { branches: [...], current_branch: "main", success: true }
                ↓
BranchAutocomplete:
  - branches = ['main', 'develop', 'feature-x', 'feature-y']
  - currentBranch = 'main'
  - query = 'main' (auto-filled if empty)
                ↓
User can:
  - Click dropdown to select another branch
  - Type custom branch name directly
                ↓
BranchAutocomplete emits update:modelValue
                ↓
ProjectsView: newProject.main_branch updated
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| gitPath is empty | No API call, `isValidRepo = false`, dropdown disabled |
| gitPath is not a git repo | API returns `success: false`, `isValidRepo = false`, branches empty, dropdown disabled, input still editable |
| API call fails | Silently fail, allow manual input |
| Branch list is empty (e.g., fresh init) | Dropdown shows empty message or is disabled |

## Testing Checklist

**Backend tests (`backend/tests/test_git.py`):**
- [ ] Returns all local branches for valid repository
- [ ] Returns correct current branch (marked with *)
- [ ] Returns error for non-git directory
- [ ] Returns empty branches list for fresh git init
- [ ] Handles path with special characters

**Frontend tests (`frontend/src/components/__tests__/BranchAutocomplete.spec.ts`):**
- [ ] Loads branches when gitPath changes
- [ ] Auto-fills current branch on successful load
- [ ] Dropdown opens/closes on button click
- [ ] Selecting branch updates modelValue
- [ ] Keyboard navigation works correctly
- [ ] Dropdown disabled when isValidRepo is false
- [ ] Manual input works regardless of branch list

## Files Changed

| File | Change |
|------|--------|
| `backend/app/services/git_service.py` | Add `get_local_branches()` method |
| `backend/app/routers/git.py` | Add `GET /api/git/branches` endpoint |
| `frontend/src/api/git.ts` | Add `getBranches()` function and `BranchListResponse` type |
| `frontend/src/components/BranchAutocomplete.vue` | New component |
| `frontend/src/views/ProjectsView.vue` | Replace input with BranchAutocomplete, remove detectCurrentBranch |

## Implementation Notes

- Follow the styling and interaction patterns of `DirectoryAutocomplete.vue` for consistency
- Use `@vueuse/core`'s `onClickOutside` for dropdown close behavior (same as DirectoryAutocomplete)
- The component should handle the loading state internally without requiring parent state
- No changes needed to project creation backend logic - it already accepts any branch name
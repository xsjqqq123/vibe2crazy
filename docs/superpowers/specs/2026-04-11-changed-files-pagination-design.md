# Changed Files Pagination Design

**Date**: 2026-04-11
**Project**: vibe2crazy
**Feature**: Add pagination to changed files list with 20 items per page, showing pagination controls only when total files exceed 20.

## Problem Statement

The changed files list currently loads all files at once, which can overwhelm the UI when there are many changed files (e.g., 50+ files). This causes:
- Long scrollable list that's hard to navigate
- Increased network payload
- Potential performance issues in the browser

## Solution

Add lazy pagination to the changed files endpoint and frontend, following the same pattern as the existing commits pagination.

## Technical Design

### Backend Changes

#### Endpoint Modification

**File**: `vibe2crazy/backend/app/routers/files.py`

Modify `GET /api/tasks/{task_id}/changed-files`:

```python
@router.get("/{task_id}/changed-files", response_model=PaginatedChangedFilesResponse)
async def get_changed_files(
    task_id: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Get paginated list of changed files in task with Git status"""
    # ... existing task validation ...

    all_files = GitService.get_changed_files_with_status(task.worktree_path)

    # Calculate pagination
    total = len(all_files)
    offset = (page - 1) * page_size
    paginated_files = all_files[offset:offset + page_size]
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedChangedFilesResponse(
        files=paginated_files,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )
```

#### New Schema

**File**: `vibe2crazy/backend/app/schemas.py`

Add paginated response schema:

```python
class PaginatedChangedFilesResponse(BaseModel):
    """Paginated response for changed files endpoint"""
    files: List[ChangedFileInfo]
    total: int
    page: int
    page_size: int
    total_pages: int
```

### Frontend Changes

#### API Client

**File**: `vibe2crazy/frontend/src/api/files.ts`

Update `getChangedFiles` function:

```typescript
interface PaginatedChangedFilesResponse {
  files: ChangedFileInfo[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

const filesApi = {
  // ... existing methods ...

  getChangedFiles: (taskId: string, page: number = 1, pageSize: number = 20) =>
    request<PaginatedChangedFilesResponse>(
      `/tasks/${taskId}/changed-files?page=${page}&page_size=${pageSize}`
    ),
}
```

#### View Component

**File**: `vibe2crazy/frontend/src/views/CodeReviewView.vue`

Add pagination state and handlers:

```typescript
// Pagination state for changed files
const changedFilesPage = ref(1)
const changedFilesData = ref<PaginatedChangedFilesResponse | null>(null)

// Load changed files with pagination
const loadChangedFiles = async (page: number = 1) => {
  if (!taskId.value) return

  try {
    changedFilesData.value = await filesApi.getChangedFiles(taskId.value, page, 20)
    changedFiles.value = changedFilesData.value.files
    changedFilesPage.value = page
  } catch (err: any) {
    console.error('Failed to load changed files:', err)
  }
}

// Handle page change
const handleChangedFilesPageChange = (page: number) => {
  loadChangedFiles(page)
  // Scroll to top of changed files list
  const changedFilesPane = document.querySelector('.changed-files-list')
  if (changedFilesPane) {
    changedFilesPane.scrollTop = 0
  }
}
```

#### Template Changes

Add pagination component after the changed files list:

```vue
<!-- Changed files pane -->
<pane :size="layout.files" :min-size="10" class="flex flex-col min-h-0 bg-main border-r border-main">
  <div class="flex-[1] p-4 border-b border-main overflow-y-auto min-h-0 changed-files-list">
    <!-- ... existing header and file list ... -->

    <!-- Pagination - only show when total > 20 -->
    <Pagination
      v-if="changedFilesData && changedFilesData.total > 20"
      :total="changedFilesData.total"
      :page="changedFilesData.page"
      :page-size="changedFilesData.page_size"
      :total-pages="changedFilesData.total_pages"
      @page-change="handleChangedFilesPageChange"
    />
  </div>
</pane>
```

### UI Behavior

| Scenario | Behavior |
|----------|----------|
| Total files ≤ 20 | Show all files, no pagination UI |
| Total files > 20 | Show 20 files per page with pagination controls |
| Page change | Scroll to top of changed files list |
| Auto-refresh (15s interval) | Fetch current page only |
| Initial load | Always fetch page 1 |
| Task switch | Reset to page 1 |

### Error Handling

- Backend returns empty list if no changes (total=0, files=[])
- Frontend handles API errors gracefully, showing error message
- Invalid page numbers handled by backend validation (ge=1)

### Testing

Backend tests in `vibe2crazy/backend/tests/test_files.py`:

1. Test pagination with no files (total=0)
2. Test pagination with fewer than 20 files (no pagination needed)
3. Test pagination with exactly 20 files
4. Test pagination with 50 files (3 pages)
5. Test invalid page number (negative, zero)
6. Test page_size limits (max 100)

## Implementation Scope

This is a focused change affecting:
- 1 backend file: `routers/files.py`
- 1 schema file: `schemas.py`
- 1 frontend API file: `api/files.ts`
- 1 frontend view: `views/CodeReviewView.vue`

No new dependencies or major refactoring required. Uses existing `Pagination.vue` component.

## Future Considerations

Not part of this implementation:
- User-configurable page size
- Search/filter within changed files
- Sorting options (by path, status, etc.)

These can be added later if needed without changing the pagination foundation.
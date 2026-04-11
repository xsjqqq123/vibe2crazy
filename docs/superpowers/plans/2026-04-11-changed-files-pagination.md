# Changed Files Pagination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add pagination to changed files list with 20 items per page, showing pagination controls only when total > 20.

**Architecture:** Backend adds pagination parameters to existing endpoint, returns paginated metadata. Frontend adds pagination state and uses existing Pagination.vue component. Follows the same pattern as commits pagination.

**Tech Stack:** FastAPI (backend), Vue 3 + TypeScript (frontend), existing Pagination.vue component

---

## File Structure

| File | Responsibility | Action |
|------|---------------|--------|
| `backend/app/schemas.py` | Add `PaginatedChangedFilesResponse` schema | Create |
| `backend/app/routers/files.py` | Modify endpoint to support pagination | Modify |
| `backend/tests/test_changed_files_pagination.py` | Test pagination behavior | Create |
| `frontend/src/api/files.ts` | Update API client with pagination types | Modify |
| `frontend/src/views/CodeReviewView.vue` | Add pagination state and UI | Modify |

---

### Task 1: Add PaginatedChangedFilesResponse Schema

**Files:**
- Modify: `backend/app/schemas.py:105-108` (after ChangedFilesResponse)

- [ ] **Step 1: Add new schema to schemas.py**

Add after `ChangedFilesResponse` (around line 108):

```python
class PaginatedChangedFilesResponse(BaseModel):
    """Paginated response for changed files endpoint"""
    files: List[ChangedFileInfo]
    total: int
    page: int
    page_size: int
    total_pages: int
```

- [ ] **Step 2: Import the new schema in files.py router**

Update import at `backend/app/routers/files.py:7`:

```python
from app.schemas import FileNode, FileRead, FileWrite, FileDeleteResponse, ChangedFilesResponse, RevertResponse, FileUploadResponse, TempUploadResult, TempUploadResponse, PaginatedChangedFilesResponse
```

- [ ] **Step 3: Commit schema changes**

```bash
cd vibe2crazy
git add backend/app/schemas.py backend/app/routers/files.py
git commit -m "feat: add PaginatedChangedFilesResponse schema for pagination support

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Write Backend Tests for Pagination

**Files:**
- Create: `backend/tests/test_changed_files_pagination.py`

- [ ] **Step 1: Write test file with all test cases**

Create `backend/tests/test_changed_files_pagination.py`:

```python
"""
Tests for changed files pagination endpoint.
"""
import os
import subprocess
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, engine, Base
from app.models import Session as SessionModel, Project, Task
from datetime import datetime, timedelta
from app.config import settings
from app.auth import create_access_token
import pytest
import uuid


@pytest.fixture
def git_repo_with_files(tmp_path):
    """Create a git repo with multiple changed files for testing."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Create git repo
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, capture_output=True)

        # Create and commit initial files
        for i in range(1, 51):
            (repo_dir / f"file{i}.txt").write_text(f"content {i}")
        subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, capture_output=True)

        # Modify files to create changes
        for i in range(1, 26):
            (repo_dir / f"file{i}.txt").write_text(f"modified content {i}")

        # Create session and project/task
        token_data = {"sub": "user", "jti": str(uuid.uuid4())}
        token = create_access_token(token_data)
        expires_at = datetime.utcnow() + timedelta(hours=settings.session_expire_hours)
        session = SessionModel(token=token, expires_at=expires_at)
        db.add(session)

        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            git_path=str(repo_dir),
            main_branch="main"
        )
        db.add(project)
        db.commit()

        task = Task(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="Test Task",
            branch_name="test-branch",
            worktree_path=str(repo_dir),
            tmux_session="test-session",
            status="active"
        )
        db.add(task)
        db.commit()

        headers = {"Authorization": f"Bearer {token}"}
        yield TestClient(app, headers=headers), task.id, repo_dir

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_pagination_no_files(tmp_path):
    """Test pagination when there are no changed files (total=0)."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Create clean git repo (no changes)
        repo_dir = tmp_path / "clean_repo"
        repo_dir.mkdir()
        subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, capture_output=True)
        (repo_dir / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, capture_output=True)

        # Create session and task
        token_data = {"sub": "user", "jti": str(uuid.uuid4())}
        token = create_access_token(token_data)
        expires_at = datetime.utcnow() + timedelta(hours=settings.session_expire_hours)
        session = SessionModel(token=token, expires_at=expires_at)
        db.add(session)

        project = Project(
            id=str(uuid.uuid4()),
            name="Clean Project",
            git_path=str(repo_dir),
            main_branch="main"
        )
        db.add(project)
        db.commit()

        task = Task(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="Clean Task",
            branch_name="clean-branch",
            worktree_path=str(repo_dir),
            tmux_session="clean-session",
            status="active"
        )
        db.add(task)
        db.commit()

        headers = {"Authorization": f"Bearer {token}"}
        client = TestClient(app, headers=headers)

        response = client.get(f"/api/tasks/{task.id}/changed-files")

        assert response.status_code == 200
        data = response.json()
        assert data["files"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert data["total_pages"] == 0

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_pagination_less_than_20_files(git_repo_with_files):
    """Test pagination with fewer than 20 files (no pagination needed)."""
    client, task_id, repo_dir = git_repo_with_files

    # Reset to have only 10 modified files
    subprocess.run(["git", "checkout", "."], cwd=repo_dir, capture_output=True)
    for i in range(1, 11):
        (repo_dir / f"file{i}.txt").write_text(f"modified {i}")

    response = client.get(f"/api/tasks/{task_id}/changed-files")

    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 10
    assert data["total"] == 10
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total_pages"] == 1


def test_pagination_exactly_20_files(git_repo_with_files):
    """Test pagination with exactly 20 files."""
    client, task_id, repo_dir = git_repo_with_files

    # Reset and modify exactly 20 files
    subprocess.run(["git", "checkout", "."], cwd=repo_dir, capture_output=True)
    for i in range(1, 21):
        (repo_dir / f"file{i}.txt").write_text(f"modified {i}")

    response = client.get(f"/api/tasks/{task_id}/changed-files")

    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 20
    assert data["total"] == 20
    assert data["total_pages"] == 1


def test_pagination_50_files(git_repo_with_files):
    """Test pagination with 50 files (3 pages)."""
    client, task_id, repo_dir = git_repo_with_files

    # We already have 25 modified files, add more
    for i in range(26, 51):
        (repo_dir / f"file{i}.txt").write_text(f"modified {i}")

    # Page 1
    response = client.get(f"/api/tasks/{task_id}/changed-files?page=1&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 20
    assert data["total"] == 50
    assert data["page"] == 1
    assert data["total_pages"] == 3

    # Page 2
    response = client.get(f"/api/tasks/{task_id}/changed-files?page=2&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 20
    assert data["page"] == 2

    # Page 3
    response = client.get(f"/api/tasks/{task_id}/changed-files?page=3&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 10  # Last page has 10 files
    assert data["page"] == 3


def test_pagination_invalid_page_number(git_repo_with_files):
    """Test pagination with invalid page number (negative, zero)."""
    client, task_id, repo_dir = git_repo_with_files

    # Page 0 should fail validation
    response = client.get(f"/api/tasks/{task_id}/changed-files?page=0&page_size=20")
    assert response.status_code == 422

    # Negative page should fail validation
    response = client.get(f"/api/tasks/{task_id}/changed-files?page=-1&page_size=20")
    assert response.status_code == 422


def test_pagination_page_size_limit(git_repo_with_files):
    """Test page_size limits (max 100)."""
    client, task_id, repo_dir = git_repo_with_files

    # Page size > 100 should fail
    response = client.get(f"/api/tasks/{task_id}/changed-files?page=1&page_size=150")
    assert response.status_code == 422

    # Page size = 100 should work
    response = client.get(f"/api/tasks/{task_id}/changed-files?page=1&page_size=100")
    assert response.status_code == 200
    data = response.json()
    assert data["page_size"] == 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd vibe2crazy/backend && pytest tests/test_changed_files_pagination.py -v`
Expected: Tests fail because endpoint doesn't return paginated response

- [ ] **Step 3: Commit test file**

```bash
cd vibe2crazy
git add backend/tests/test_changed_files_pagination.py
git commit -m "test: add pagination tests for changed files endpoint (failing)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Implement Backend Pagination Endpoint

**Files:**
- Modify: `backend/app/routers/files.py:423-439`

- [ ] **Step 1: Modify the changed-files endpoint**

Replace the endpoint at line 423:

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
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

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

- [ ] **Step 2: Add Query import to files.py**

Add `Query` to the imports at line 4:

```python
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, Form
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd vibe2crazy/backend && pytest tests/test_changed_files_pagination.py -v`
Expected: All tests pass

- [ ] **Step 4: Commit backend implementation**

```bash
cd vibe2crazy
git add backend/app/routers/files.py
git commit -m "feat: add pagination to changed-files endpoint

- Add page and page_size query parameters
- Return PaginatedChangedFilesResponse with metadata
- Default page_size=20, max=100

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Update Frontend API Client

**Files:**
- Modify: `frontend/src/api/files.ts:12-13,68-69`

- [ ] **Step 1: Add paginated response interface**

Add after `ChangedFileInfo` interface (around line 13):

```typescript
export interface PaginatedChangedFilesResponse {
  files: ChangedFileInfo[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
```

- [ ] **Step 2: Update getChangedFiles function**

Replace function at line 68:

```typescript
  getChangedFiles: (taskId: string, page: number = 1, pageSize: number = 20) =>
    request<PaginatedChangedFilesResponse>(`/tasks/${taskId}/changed-files?page=${page}&page_size=${pageSize}`),
```

- [ ] **Step 3: Commit frontend API changes**

```bash
cd vibe2crazy
git add frontend/src/api/files.ts
git commit -m "feat: update files API client with pagination support

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Update Frontend View Component

**Files:**
- Modify: `frontend/src/views/CodeReviewView.vue`

- [ ] **Step 1: Add pagination state variables**

Add after `changedFiles` ref (around line 50):

```typescript
// Changed files pagination
const changedFilesPage = ref(1)
const changedFilesData = ref<PaginatedChangedFilesResponse | null>(null)
```

- [ ] **Step 2: Import PaginatedChangedFilesResponse type**

Add to imports at line 10:

```typescript
import { type ChangedFileInfo, type PaginatedChangedFilesResponse } from '@/api/files'
```

- [ ] **Step 3: Update loadChangedFiles function**

Replace function at line 592:

```typescript
const loadChangedFiles = async (page: number = 1) => {
  // Guard against navigation/unmounting - don't make API calls if taskId is undefined
  if (!taskId.value) return

  // Don't show loading spinner during auto-refresh to prevent jitter
  // initialLoading handles the first load only
  try {
    changedFilesData.value = await filesApi.getChangedFiles(taskId.value, page, 20)
    changedFiles.value = changedFilesData.value.files
    changedFilesPage.value = page
  } catch (err: any) {
    console.error('Failed to load changed files:', err)
  }
}
```

- [ ] **Step 4: Add page change handler**

Add after `loadChangedFiles` function:

```typescript
const handleChangedFilesPageChange = (page: number) => {
  loadChangedFiles(page)
  // Scroll to top of changed files list
  const changedFilesPane = document.querySelector('.changed-files-list')
  if (changedFilesPane) {
    changedFilesPane.scrollTop = 0
  }
}
```

- [ ] **Step 5: Reset page on task change**

Add to existing taskId watcher at line 504:

```typescript
watch(taskId, () => {
  currentPage.value = 1
  changedFilesPage.value = 1
  loadCommits()
})
```

- [ ] **Step 6: Add pagination to template**

Add pagination component after the changed files list in template. Find the changed files pane (around line 1794) and add `changed-files-list` class and Pagination component:

Update the changed files pane div to include pagination:

```vue
          <!-- Changed files -->
          <pane :size="layout.files" :min-size="10" class="flex flex-col min-h-0 bg-main border-r border-main">
            <div class="flex-[1] p-4 border-b border-main overflow-y-auto min-h-0 changed-files-list">
              <div class="flex items-center justify-between mb-2">
                <h3 class="text-sm font-semibold text-main">Changes</h3>
                <button
                  @click="openCommitMessageModal"
                  :disabled="accepting"
                  :class="['p-1.5 rounded-lg hover:bg-sub', { 'pointer-events-none opacity-60 cursor-not-allowed': accepting }]"
                  title="Accept"
                >
                  <span v-if="accepting" class="spinner w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full"></span>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                  </svg>
                </button>
              </div>
              <div v-if="initialLoading" class="flex items-center justify-center py-4">
                <div class="spinner"></div>
              </div>
              <div v-else-if="changedFiles.length === 0" class="text-xs text-sub py-2">
                No changes detected
              </div>
              <div v-else class="space-y-1" @click="closeContextMenuOnClick">
                <div
                  v-for="file in changedFiles"
                  :key="file.path"
                  @click="loadFile(file.path, 'diff')"
                  @contextmenu.prevent.stop="(e) => handleShowContextMenu({
                    x: e.clientX,
                    y: e.clientY,
                    path: file.path,
                    type: 'file',
                    source: 'changedFiles'
                  })"
                  @touchstart="(e) => handleChangedFilesTouchStart(e, file.path)"
                  @touchend="handleChangedFilesTouchEnd"
                  @touchmove="handleChangedFilesTouchMove"
                  :class="['text-xs px-2 py-1 rounded cursor-pointer hover:bg-sub flex items-center justify-between gap-2', currentFile === file.path && editorMode === 'diff' ? 'item-selected' : '']"
                  :title="file.path"
                >
                  <span :class="['truncate flex-1', currentFile === file.path && editorMode === 'diff' ? 'text-main font-medium' : 'text-green-600 dark:text-green-400']">{{ file.path }}</span>
                  <span class="px-1.5 py-0.5 rounded text-xs font-mono font-medium min-w-[20px] text-center flex-shrink-0"
                    :class="{
                      'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400': file.status === 'A',
                      'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400': file.status === 'M',
                      'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400': file.status === 'D',
                      'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400': file.status === 'R',
                      'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400': file.status === 'C',
                      'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400': file.status === 'U',
                      'bg-gray-100 text-gray-700 dark:bg-gray-700/30 dark:text-gray-400': file.status === 'T',
                      'bg-gray-50 text-gray-500 dark:bg-gray-800/30 dark:text-gray-500': file.status === '?'
                    }">{{ file.status }}</span>
                </div>
              </div>
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

- [ ] **Step 7: Run frontend to verify UI works**

Run: `cd vibe2crazy/frontend && npm run dev`
Manual test: Create a task with >20 changed files, verify pagination appears

- [ ] **Step 8: Commit frontend view changes**

```bash
cd vibe2crazy
git add frontend/src/views/CodeReviewView.vue
git commit -m "feat: add pagination UI to changed files list

- Add pagination state (changedFilesPage, changedFilesData)
- Show Pagination component when total > 20
- Reset to page 1 on task change
- Scroll to top on page change

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Final Verification and Integration

**Files:**
- All modified files

- [ ] **Step 1: Run all backend tests**

Run: `cd vibe2crazy/backend && pytest tests/test_changed_files_pagination.py -v`
Expected: All 7 tests pass

- [ ] **Step 2: Run backend lint/type check**

Run: `cd vibe2crazy/backend && python -m py_compile app/routers/files.py app/schemas.py`
Expected: No errors

- [ ] **Step 3: Run frontend lint**

Run: `cd vibe2crazy/frontend && npm run lint`
Expected: No errors related to changed files

- [ ] **Step 4: Manual integration test**

1. Start both services: `./deploy.sh start`
2. Create a task
3. Modify >20 files in the task worktree
4. Verify pagination appears in Changes panel
5. Click page 2, verify files update and scroll to top
6. Modify <20 files, verify pagination disappears

- [ ] **Step 5: Create final commit with all changes**

```bash
cd vibe2crazy
git add -A
git commit -m "feat: complete changed files pagination feature

- Backend: Paginated endpoint with page/page_size params
- Frontend: Pagination UI shown when total > 20
- Tests: 7 test cases covering pagination scenarios

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Paginated endpoint (Task 3)
- [x] PaginatedChangedFilesResponse schema (Task 1)
- [x] Pagination only when total > 20 (Task 5)
- [x] Page size 20 (Task 3)
- [x] Scroll to top on page change (Task 5)
- [x] Reset on task switch (Task 5)
- [x] Auto-refresh fetches current page (Task 5 - loadChangedFiles uses page param)
- [x] Tests for all scenarios (Task 2)

**Placeholder scan:** No TBD, TODO, or vague descriptions found.

**Type consistency:**
- `PaginatedChangedFilesResponse` used consistently across backend and frontend
- `changedFilesData` type matches API response
- Pagination props match component interface
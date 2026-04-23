# File Local Cache Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement localStorage-based file caching with hash validation to reduce bandwidth when opening unchanged files.

**Architecture:** Backend provides a lightweight `/hash` endpoint returning SHA-256 hashes. Frontend checks hash before loading files, using cached content when hashes match. Hash is also included in read responses for cache updates.

**Tech Stack:** Python/FastAPI (backend), TypeScript/Vue 3 (frontend), localStorage for caching, SHA-256 for hashing

---

## Chunk 1: Backend Hash Endpoint

### Task 1: Add Hash Method to FileService

**Files:**
- Modify: `backend/app/services/file_service.py`
- Test: `backend/tests/test_file_service.py` (new file)

- [ ] **Step 1: Write failing test for get_file_hash**

Create `backend/tests/test_file_service.py`:

```python
"""Tests for FileService methods."""
import pytest
import tempfile
import os
from pathlib import Path
from app.services.file_service import FileService


class TestGetFileHash:
    """Tests for the get_file_hash method."""

    def test_get_file_hash_returns_correct_sha256(self):
        """Should return correct SHA-256 hash for file content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file with known content
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")

            # SHA-256 of "Hello, World!" (without newline)
            expected_hash = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"

            result = FileService.get_file_hash(tmpdir, "test.txt")

            assert result["success"] is True
            assert result["hash"] == f"sha256:{expected_hash}"

    def test_get_file_hash_file_not_found(self):
        """Should return success=False for non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = FileService.get_file_hash(tmpdir, "nonexistent.txt")

            assert result["success"] is False
            assert "not found" in result["error"].lower()

    def test_get_file_hash_directory_raises_error(self):
        """Should return success=False for directory path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a subdirectory
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()

            result = FileService.get_file_hash(tmpdir, "subdir")

            assert result["success"] is False
            assert "not a file" in result["error"].lower()

    def test_get_file_hash_path_outside_worktree(self):
        """Should return success=False for path outside worktree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with tempfile.TemporaryDirectory() as otherdir:
                # Create file in different directory
                other_file = Path(otherdir) / "other.txt"
                other_file.write_text("other content")

                # Try to access it from tmpdir worktree
                result = FileService.get_file_hash(tmpdir, "../" + os.path.basename(otherdir) + "/other.txt")

                assert result["success"] is False
                assert "outside worktree" in result["error"].lower()

    def test_get_file_hash_binary_file(self):
        """Should correctly hash binary files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create binary file
            binary_content = bytes([0x00, 0x01, 0x02, 0xFF, 0xFE])
            test_file = Path(tmpdir) / "binary.bin"
            test_file.write_bytes(binary_content)

            result = FileService.get_file_hash(tmpdir, "binary.bin")

            assert result["success"] is True
            assert result["hash"].startswith("sha256:")
            # Verify hash length (64 hex chars after prefix)
            assert len(result["hash"]) == 71  # len("sha256:") + 64
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yhlx/workspace/vibe2death/vibe2crazy/backend && python -m pytest tests/test_file_service.py -v`
Expected: FAIL with "AttributeError: type object 'FileService' has no attribute 'get_file_hash'"

- [ ] **Step 3: Implement get_file_hash in FileService**

Add to `backend/app/services/file_service.py`:

```python
import hashlib

# Add this method to the FileService class (after read_file method):

    @staticmethod
    def get_file_hash(worktree_path: str, file_path: str) -> dict:
        """
        Get SHA-256 hash of file content for cache validation.

        Args:
            worktree_path: Path to the task worktree
            file_path: Relative path to file within worktree

        Returns:
            dict with keys:
                - success: bool
                - hash: str (format "sha256:<hex>") or None
                - error: str or None
        """
        try:
            full_path = Path(worktree_path) / file_path

            # Security check: ensure path is within worktree
            full_path = full_path.resolve()
            worktree = Path(worktree_path).resolve()
            if not str(full_path).startswith(str(worktree)):
                return {"success": False, "hash": None, "error": "Path outside worktree"}

            if not full_path.exists():
                return {"success": False, "hash": None, "error": "File not found"}

            if not full_path.is_file():
                return {"success": False, "hash": None, "error": "Not a file"}

            # Read file in binary mode and compute SHA-256
            sha256_hash = hashlib.sha256()
            with open(full_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256_hash.update(chunk)

            return {"success": True, "hash": f"sha256:{sha256_hash.hexdigest()}", "error": None}
        except Exception as e:
            return {"success": False, "hash": None, "error": str(e)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yhlx/workspace/vibe2death/vibe2crazy/backend && python -m pytest tests/test_file_service.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/file_service.py backend/tests/test_file_service.py
git commit -m "feat(backend): add get_file_hash method to FileService

- Compute SHA-256 hash for cache validation
- Handle file not found, directory, and path traversal errors
- Return hash in 'sha256:<hex>' format

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Add Hash Endpoint to Router

**Files:**
- Modify: `backend/app/routers/files.py`
- Test: `backend/tests/test_files_hash.py` (new file)

- [ ] **Step 1: Write failing test for hash endpoint**

Create `backend/tests/test_files_hash.py`:

```python
"""Tests for file hash endpoint."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.models import Task, Project


client = TestClient(app)


class TestFileHashEndpoint:
    """Tests for GET /api/tasks/{task_id}/files/{file_path}/hash"""

    @pytest.fixture
    def mock_auth(self):
        """Mock authentication dependency."""
        with patch("app.routers.files.require_auth") as mock:
            mock_task = MagicMock(spec=Task)
            mock_task.id = "test-task-id"
            mock_task.worktree_path = "/tmp/test-worktree"
            mock.return_value = mock_task
            yield mock_task

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        with patch("app.routers.files.get_db") as mock:
            db_session = MagicMock()
            mock.return_value = db_session
            yield db_session

    def test_get_file_hash_success(self, mock_auth, mock_db, tmp_path):
        """Should return hash for existing file."""
        import os

        # Create test file
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        test_file = worktree / "test.txt"
        test_file.write_text("Hello, World!")

        # Mock task lookup
        mock_task = MagicMock(spec=Task)
        mock_task.id = "test-task-id"
        mock_task.worktree_path = str(worktree)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        with patch("app.routers.files.require_auth", return_value=mock_task):
            response = client.get(
                "/api/tasks/test-task-id/files/test.txt/hash",
                headers={"Authorization": "Bearer test-token"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "hash" in data
        assert data["hash"].startswith("sha256:")

    def test_get_file_hash_not_found(self, mock_auth, mock_db, tmp_path):
        """Should return 404 for non-existent file."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        mock_task = MagicMock(spec=Task)
        mock_task.id = "test-task-id"
        mock_task.worktree_path = str(worktree)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        with patch("app.routers.files.require_auth", return_value=mock_task):
            response = client.get(
                "/api/tasks/test-task-id/files/nonexistent.txt/hash",
                headers={"Authorization": "Bearer test-token"}
            )

        assert response.status_code == 404

    def test_get_file_hash_directory_returns_400(self, mock_auth, mock_db, tmp_path):
        """Should return 400 for directory path."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        subdir = worktree / "subdir"
        subdir.mkdir()

        mock_task = MagicMock(spec=Task)
        mock_task.id = "test-task-id"
        mock_task.worktree_path = str(worktree)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        with patch("app.routers.files.require_auth", return_value=mock_task):
            response = client.get(
                "/api/tasks/test-task-id/files/subdir/hash",
                headers={"Authorization": "Bearer test-token"}
            )

        assert response.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yhlx/workspace/vibe2death/vibe2crazy/backend && python -m pytest tests/test_files_hash.py -v`
Expected: FAIL with 404 or route not found

- [ ] **Step 3: Add hash endpoint to files router**

Add to `backend/app/routers/files.py` before the `read_file` endpoint (around line 228):

```python
@router.get("/{task_id}/files/{file_path:path}/hash")
async def get_file_hash(
    task_id: str,
    file_path: str,
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """
    Get SHA-256 hash of file content for cache validation.

    Returns a hash that clients can use to check if their cached
    version of a file is still valid.

    Returns:
        {"hash": "sha256:<hex_value>"}
    """
    import os
    from urllib.parse import unquote

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # URL decode the file path
    file_path = unquote(file_path)
    full_path = os.path.join(task.worktree_path, file_path)

    # Security check: ensure path is within worktree
    full_path_resolved = Path(full_path).resolve()
    worktree_resolved = Path(task.worktree_path).resolve()
    if not str(full_path_resolved).startswith(str(worktree_resolved)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path (outside worktree)"
        )

    if not os.path.exists(full_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_path}"
        )

    if not os.path.isfile(full_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not a file"
        )

    result = FileService.get_file_hash(task.worktree_path, file_path)
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )

    return {"hash": result["hash"]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yhlx/workspace/vibe2death/vibe2crazy/backend && python -m pytest tests/test_files_hash.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/files.py backend/tests/test_files_hash.py
git commit -m "feat(api): add GET /files/{path}/hash endpoint

- Return SHA-256 hash for cache validation
- Handle file not found, directory, and path errors

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Add Hash to Read Endpoint Response

**Files:**
- Modify: `backend/app/routers/files.py`
- Test: `backend/tests/test_files_hash.py`

- [ ] **Step 1: Write failing test for hash in read response**

Add to `backend/tests/test_files_hash.py`:

```python
    def test_read_file_includes_hash(self, mock_auth, mock_db, tmp_path):
        """Read endpoint should include hash in response."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        test_file = worktree / "test.txt"
        test_file.write_text("Hello, World!")

        mock_task = MagicMock(spec=Task)
        mock_task.id = "test-task-id"
        mock_task.worktree_path = str(worktree)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        with patch("app.routers.files.require_auth", return_value=mock_task):
            response = client.get(
                "/api/tasks/test-task-id/files/test.txt",
                headers={"Authorization": "Bearer test-token"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert "hash" in data
        assert data["hash"].startswith("sha256:")
        # Verify hash matches content
        import hashlib
        expected = "sha256:" + hashlib.sha256(b"Hello, World!").hexdigest()
        assert data["hash"] == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yhlx/workspace/vibe2death/vibe2crazy/backend && python -m pytest tests/test_files_hash.py::TestFileHashEndpoint::test_read_file_includes_hash -v`
Expected: FAIL with KeyError or assertion error for missing "hash"

- [ ] **Step 3: Modify read_file endpoint to include hash**

In `backend/app/routers/files.py`, modify the read_file endpoint's return statement (around line 288):

Change:
```python
    return {"content": content}
```

To:
```python
    # Get hash for cache validation
    hash_result = FileService.get_file_hash(task.worktree_path, file_path)
    file_hash = hash_result["hash"] if hash_result["success"] else None

    return {"content": content, "hash": file_hash}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yhlx/workspace/vibe2death/vibe2crazy/backend && python -m pytest tests/test_files_hash.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/files.py backend/tests/test_files_hash.py
git commit -m "feat(api): include hash in file read response

- Add hash field to GET /files/{path} response
- Enables clients to update cache after fetching content

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Chunk 2: Frontend FileCacheService

### Task 4: Create FileCacheService

**Files:**
- Create: `frontend/src/services/FileCacheService.ts`
- Create: `frontend/src/services/__tests__/FileCacheService.spec.ts`

- [ ] **Step 1: Write failing tests for FileCacheService**

Create `frontend/src/services/__tests__/FileCacheService.spec.ts`:

```typescript
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import FileCacheService from '../FileCacheService'

describe('FileCacheService', () => {
  const taskId = 'test-task-123'
  const filePath = 'src/main.ts'
  const hash = 'sha256:abc123def456'
  const content = 'console.log("Hello, World!")'

  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()
    // Reset any mocks
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  describe('get', () => {
    it('returns null for missing key', () => {
      const result = FileCacheService.get(taskId, filePath)
      expect(result).toBeNull()
    })

    it('returns cached entry when exists', () => {
      FileCacheService.set(taskId, filePath, hash, content)
      const result = FileCacheService.get(taskId, filePath)
      expect(result).toEqual({ hash, content })
    })

    it('returns null when hash does not match', () => {
      FileCacheService.set(taskId, filePath, hash, content)
      // Get with different task should return null
      const result = FileCacheService.get('different-task', filePath)
      expect(result).toBeNull()
    })
  })

  describe('set', () => {
    it('stores entry in localStorage', () => {
      FileCacheService.set(taskId, filePath, hash, content)

      const key = `filecache:${taskId}:${filePath}`
      const stored = localStorage.getItem(key)
      expect(stored).not.toBeNull()

      const parsed = JSON.parse(stored!)
      expect(parsed).toEqual({ hash, content })
    })

    it('overwrites existing entry', () => {
      FileCacheService.set(taskId, filePath, 'old-hash', 'old content')
      FileCacheService.set(taskId, filePath, hash, content)

      const result = FileCacheService.get(taskId, filePath)
      expect(result).toEqual({ hash, content })
    })
  })

  describe('clear', () => {
    it('clears all entries when no taskId provided', () => {
      FileCacheService.set(taskId, 'file1.ts', hash, content)
      FileCacheService.set('other-task', 'file2.ts', hash, content)

      FileCacheService.clear()

      expect(FileCacheService.get(taskId, 'file1.ts')).toBeNull()
      expect(FileCacheService.get('other-task', 'file2.ts')).toBeNull()
    })

    it('clears only entries for specified taskId', () => {
      FileCacheService.set(taskId, 'file1.ts', hash, content)
      FileCacheService.set('other-task', 'file2.ts', hash, content)

      FileCacheService.clear(taskId)

      expect(FileCacheService.get(taskId, 'file1.ts')).toBeNull()
      expect(FileCacheService.get('other-task', 'file2.ts')).not.toBeNull()
    })
  })

  describe('getStorageSize', () => {
    it('returns 0 when empty', () => {
      expect(FileCacheService.getStorageSize()).toBe(0)
    })

    it('returns total size of cached entries', () => {
      FileCacheService.set(taskId, 'file1.ts', hash, content)
      FileCacheService.set(taskId, 'file2.ts', hash, content + ' more data')

      const size = FileCacheService.getStorageSize()
      expect(size).toBeGreaterThan(0)
    })
  })

  describe('quota handling', () => {
    it('handles quota exceeded error', () => {
      // Mock localStorage to throw QuotaExceededError
      const originalSetItem = localStorage.setItem
      let callCount = 0

      localStorage.setItem = vi.fn((key: string, value: string) => {
        callCount++
        if (callCount === 1) {
          const error = new DOMException('Quota exceeded', 'QuotaExceededError')
          throw error
        }
        // Second call succeeds (after clearing)
        return originalSetItem.call(localStorage, key, value)
      })

      // Pre-populate with some data to be cleared
      FileCacheService.set('old-task', 'old-file.ts', 'old-hash', 'old content')

      // This should trigger quota error, then clear old entries and retry
      FileCacheService.set(taskId, filePath, hash, content)

      // Verify setItem was called twice (initial + retry)
      expect(localStorage.setItem).toHaveBeenCalledTimes(2)

      // Restore
      localStorage.setItem = originalSetItem
    })
  })

  describe('localStorage unavailable', () => {
    it('returns null when localStorage throws', () => {
      // Mock localStorage.getItem to throw
      const originalGetItem = localStorage.getItem
      localStorage.getItem = vi.fn(() => {
        throw new Error('localStorage not available')
      })

      const result = FileCacheService.get(taskId, filePath)
      expect(result).toBeNull()

      // Restore
      localStorage.getItem = originalGetItem
    })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yhlx/workspace/vibe2death/vibe2crazy/frontend && npm test -- src/services/__tests__/FileCacheService.spec.ts`
Expected: FAIL with "Failed to resolve import" or similar

- [ ] **Step 3: Implement FileCacheService**

Create `frontend/src/services/FileCacheService.ts`:

```typescript
/**
 * Service for caching file content in localStorage with hash-based validation.
 *
 * Cache key format: filecache:{taskId}:{filePath}
 * Cache value: { hash: string, content: string }
 */

const PREFIX = 'filecache:'

interface CachedEntry {
  hash: string
  content: string
}

class FileCacheService {
  /**
   * Get cached file entry.
   * Returns null if not found or on error.
   */
  get(taskId: string, filePath: string): CachedEntry | null {
    try {
      const key = this.buildKey(taskId, filePath)
      const stored = localStorage.getItem(key)
      if (!stored) return null

      const entry = JSON.parse(stored) as CachedEntry
      return entry
    } catch {
      // localStorage not available or parse error
      return null
    }
  }

  /**
   * Store file content in cache.
   * Handles quota exceeded by clearing old entries.
   */
  set(taskId: string, filePath: string, hash: string, content: string): void {
    try {
      const key = this.buildKey(taskId, filePath)
      const value = JSON.stringify({ hash, content })

      try {
        localStorage.setItem(key, value)
      } catch (e) {
        if (e instanceof DOMException && e.name === 'QuotaExceededError') {
          // Clear old entries and retry
          this.clearOldEntries()
          localStorage.setItem(key, value)
        } else {
          throw e
        }
      }
    } catch {
      // localStorage not available, skip caching
    }
  }

  /**
   * Clear all cached entries, or just for a specific task.
   */
  clear(taskId?: string): void {
    try {
      const keysToRemove: string[] = []

      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith(PREFIX)) {
          if (taskId) {
            // Only clear entries for this task
            if (key.startsWith(`${PREFIX}${taskId}:`)) {
              keysToRemove.push(key)
            }
          } else {
            keysToRemove.push(key)
          }
        }
      }

      keysToRemove.forEach(key => localStorage.removeItem(key))
    } catch {
      // localStorage not available
    }
  }

  /**
   * Get total size of cached entries in bytes.
   */
  getStorageSize(): number {
    try {
      let totalSize = 0

      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith(PREFIX)) {
          const value = localStorage.getItem(key)
          if (value) {
            // Rough estimate: each char is 2 bytes in UTF-16
            totalSize += (key.length + value.length) * 2
          }
        }
      }

      return totalSize
    } catch {
      return 0
    }
  }

  /**
   * Build cache key from taskId and filePath.
   */
  private buildKey(taskId: string, filePath: string): string {
    return `${PREFIX}${taskId}:${filePath}`
  }

  /**
   * Clear approximately 50% of cached entries (oldest first).
   * Used when quota is exceeded.
   */
  private clearOldEntries(): void {
    try {
      const entries: { key: string; timestamp: number }[] = []

      // Collect all cache entries with their timestamps
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith(PREFIX)) {
          // Use a simple heuristic: entries at lower indices are older
          entries.push({ key, timestamp: i })
        }
      }

      // Sort by timestamp (lower = older) and remove oldest 50%
      entries.sort((a, b) => a.timestamp - b.timestamp)
      const toRemove = entries.slice(0, Math.ceil(entries.length / 2))

      toRemove.forEach(entry => localStorage.removeItem(entry.key))
    } catch {
      // localStorage not available
    }
  }
}

// Export singleton instance
export default new FileCacheService()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yhlx/workspace/vibe2death/vibe2crazy/frontend && npm test -- src/services/__tests__/FileCacheService.spec.ts`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/FileCacheService.ts frontend/src/services/__tests__/FileCacheService.spec.ts
git commit -m "feat(frontend): add FileCacheService for localStorage caching

- get/set methods for cache entries
- Hash-based validation support
- Quota exceeded handling with automatic cleanup
- Clear method for task-specific or full cache

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Chunk 3: Frontend Integration

### Task 5: Update API Client

**Files:**
- Modify: `frontend/src/api/files.ts`

- [ ] **Step 1: Add getHash method and update read return type**

In `frontend/src/api/files.ts`, modify the `filesApi` object:

Add `getHash` method after `read`:
```typescript
  getHash: (taskId: string, filePath: string) => {
    const encodedPath = filePath.split('/').map(encodeURIComponent).join('/')
    return request<{ hash: string }>(`/tasks/${taskId}/files/${encodedPath}/hash`)
  },
```

Update `read` method to include hash in return type:
```typescript
  read: (taskId: string, filePath: string) =>
    request<{ content: string; hash: string }>(`/tasks/${taskId}/files/${filePath}`),
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /home/yhlx/workspace/vibe2death/vibe2crazy/frontend && npm run build`
Expected: Build succeeds without errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/files.ts
git commit -m "feat(api): add getHash method and hash in read response

- Add getHash() for cache validation
- Update read() return type to include hash

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Integrate Caching in CodeReviewView

**Files:**
- Modify: `frontend/src/views/CodeReviewView.vue`

- [ ] **Step 1: Add FileCacheService import**

At the top of `frontend/src/views/CodeReviewView.vue`, add import:

```typescript
import FileCacheService from '@/services/FileCacheService'
```

- [ ] **Step 2: Modify loadFile function to use caching**

Replace the existing `loadFile` function (lines 561-653) with the cached version:

```typescript
const loadFile = async (filePath: string | null, mode: 'editor' | 'diff' = 'editor') => {
  if (!filePath) {
    // Just closing sidebar on mobile
    if (isMobile.value) {
      showFileList.value = false
      showTerminal.value = false
    }
    return
  }

  // CHECK FOR PDF: If file is PDF, show prompt to open in browser
  if (filePath.endsWith('.pdf')) {
    pdfPromptFile.value = filePath
    pdfError.value = null
    closeImagePreview() // Close any image preview

    // Close sidebar on mobile
    if (isMobile.value) {
      showFileList.value = false
      showTerminal.value = false
    }
    return
  }

  // CHECK FOR IMAGE: If file is an image, show preview in editor area
  if (isImageFile(filePath)) {
    closePdfPrompt() // Close any PDF prompt
    loadImagePreview(filePath)

    // Close sidebar on mobile
    if (isMobile.value) {
      showFileList.value = false
      showTerminal.value = false
    }
    return
  }

  // Reset PDF prompt and image preview state when loading other files
  pdfPromptFile.value = null
  closeImagePreview()

  currentFile.value = filePath
  editorMode.value = mode
  loadingContent.value = true
  saveError.value = ''
  isFileDeleted.value = false  // RESET: Clear any previous deleted state

  // Close sidebar and show editor on mobile
  if (isMobile.value) {
    showFileList.value = false
    showTerminal.value = false
  }

  // CHECK IF DELETED: Check if file is deleted
  const fileStatus = changedFiles.value.find(f => f.path === filePath)?.status
  if (fileStatus === 'D') {
    isFileDeleted.value = true
    editorMode.value = 'deleted'

    // Load original content from git (no caching for deleted files)
    try {
      const originalResult = await filesApi.getOriginal(taskId.value, filePath)
      fileContent.value = originalResult.content
      originalContent.value = originalResult.content
    } catch (err: any) {
      saveError.value = 'This file was deleted and has no history to display'
    }
    loadingContent.value = false
    return
  }

  // === CACHE LOGIC START ===
  try {
    // Step 1: Get hash from server
    const hashResult = await filesApi.getHash(taskId.value, filePath)
    const serverHash = hashResult.hash

    // Step 2: Check local cache
    const cached = FileCacheService.get(taskId.value, filePath)

    if (cached && cached.hash === serverHash) {
      // Cache hit - use cached content
      fileContent.value = cached.content

      // If diff mode, still need to load original content from git
      if (mode === 'diff') {
        try {
          const originalResult = await filesApi.getOriginal(taskId.value, filePath)
          originalContent.value = originalResult.content
        } catch (origErr: any) {
          originalContent.value = ''
        }
      } else {
        originalContent.value = cached.content
      }

      loadingContent.value = false
      return
    }

    // Cache miss or stale - fetch from server
    const result = await filesApi.read(taskId.value, filePath)
    fileContent.value = result.content

    // Update cache
    FileCacheService.set(taskId.value, filePath, result.hash, result.content)

    // If diff mode, load original content from git
    if (mode === 'diff') {
      try {
        const originalResult = await filesApi.getOriginal(taskId.value, filePath)
        originalContent.value = originalResult.content
      } catch (origErr: any) {
        // If getting original fails (new file), use empty string
        originalContent.value = ''
      }
    } else {
      originalContent.value = result.content
    }
  } catch (err: any) {
    // Hash endpoint failed or other error - fall back to direct fetch
    console.warn('Cache check failed, fetching directly:', err.message)
    try {
      const result = await filesApi.read(taskId.value, filePath)
      fileContent.value = result.content

      // Cache the result if we have a hash
      if (result.hash) {
        FileCacheService.set(taskId.value, filePath, result.hash, result.content)
      }

      if (mode === 'diff') {
        try {
          const originalResult = await filesApi.getOriginal(taskId.value, filePath)
          originalContent.value = originalResult.content
        } catch (origErr: any) {
          originalContent.value = ''
        }
      } else {
        originalContent.value = result.content
      }
    } catch (readErr: any) {
      saveError.value = readErr.message || 'Failed to load file'
    }
  }
  // === CACHE LOGIC END ===

  loadingContent.value = false
}
```

- [ ] **Step 3: Verify the application builds**

Run: `cd /home/yhlx/workspace/vibe2death/vibe2crazy/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Manual testing**

1. Start the application: `./deploy.sh restart`
2. Open a task in the code review view
3. Click on a file to open it
4. Open the same file again - should use cache (check browser dev tools Network tab for hash request only)
5. Modify the file in the terminal
6. Open the file again - should fetch new content (hash mismatch)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/CodeReviewView.vue
git commit -m "feat(ui): integrate file caching in CodeReviewView

- Check hash before loading files
- Use cached content when hash matches
- Fall back to direct fetch on hash endpoint error
- Update cache with new content after fetch

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Enhanced Manual Testing for Cache Integration

**Note:** CodeReviewView has complex dependencies (router, store, multiple composables, Monaco editor, WebSocket terminal) making unit testing impractical. The caching logic is thoroughly tested in FileCacheService tests. This task provides detailed manual verification steps.

**Files:**
- No new files - manual verification only

- [ ] **Step 1: Start the application**

Run: `./deploy.sh restart`
Expected: Both frontend and backend running

- [ ] **Step 2: Test cache hit scenario**

1. Open browser DevTools → Network tab
2. Navigate to a task's code review view
3. Click on a text file (not PDF or image)
4. Observe Network tab: two requests - `GET .../hash` and `GET .../files/path` (hash + content fetch)
5. Click on the same file again
6. Observe Network tab: only `GET .../hash` request (no content fetch - cache hit)
7. Verify file content displays correctly

- [ ] **Step 3: Test cache miss scenario**

1. Click on a different file that hasn't been opened
2. Observe Network tab: `GET .../hash` followed by `GET .../files/path`
3. Verify file content displays correctly

- [ ] **Step 4: Test cache stale scenario**

1. Open a file and verify it loads
2. Open terminal in the task
3. Edit the file: `echo "new line" >> path/to/file.txt`
4. Return to file tree and click the same file again
5. Observe Network tab: `GET .../hash` followed by `GET .../files/path` (hash mismatch triggers re-fetch)
6. Verify updated content displays

- [ ] **Step 5: Test hash endpoint error fallback**

1. Stop the backend: `./deploy.sh stop`
2. Try to open a file (it should fail gracefully)
3. Restart the backend: `./deploy.sh start`
4. Verify files can be opened again

- [ ] **Step 6: Test localStorage quota handling**

1. Open browser DevTools → Application → Local Storage
2. Find `filecache:` keys
3. Open multiple large files to populate cache
4. Verify cache entries are created
5. Test that old entries are cleared when quota is exceeded (may need to artificially fill localStorage)

- [ ] **Step 7: Verify build and existing tests pass**

Run: `cd /home/yhlx/workspace/vibe2death/vibe2crazy/frontend && npm run build && npm test`
Expected: Build succeeds, all tests pass

---

### Task 8: Final Verification and Cleanup

- [ ] **Step 1: Run all backend tests**

Run: `cd /home/yhlx/workspace/vibe2death/vibe2crazy/backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 2: Run all frontend tests**

Run: `cd /home/yhlx/workspace/vibe2death/vibe2crazy/frontend && npm test`
Expected: All tests PASS

- [ ] **Step 3: Build frontend**

Run: `cd /home/yhlx/workspace/vibe2death/vibe2crazy/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Final commit with summary**

```bash
git add -A
git commit -m "feat: complete file local cache implementation

Backend:
- Add GET /files/{path}/hash endpoint for cache validation
- Include hash in file read response
- SHA-256 hashing with chunked reading for large files

Frontend:
- FileCacheService for localStorage-based caching
- Hash-first validation before loading files
- Quota exceeded handling with automatic cleanup
- Graceful fallback on cache errors

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```
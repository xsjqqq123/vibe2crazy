# File Local Cache Design

**Date:** 2026-03-13
**Status:** Draft

## Problem

Currently, every file open in Vibe2Crazy fetches the full content from the server, wasting bandwidth when the same file is opened multiple times or when files haven't changed.

## Solution

Implement a local file cache using localStorage with hash-based validation. Before loading a file, the frontend checks a hash from the server. If the hash matches the cached version, use the cached content. Otherwise, fetch fresh content and update the cache.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend                                   │
├─────────────────────────────────────────────────────────────────┤
│  loadFile()                                                      │
│      │                                                           │
│      ▼                                                           │
│  ┌─────────────────┐                                            │
│  │ FileCacheService│◄──── localStorage                          │
│  │  - get(hash)    │      { taskId_filePath: { hash, content }} │
│  │  - set(hash,    │                                            │
│  │        content) │                                            │
│  │  - clear()      │                                            │
│  └────────┬────────┘                                            │
│           │                                                       │
└───────────┼───────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────────┐
│                         Backend                                    │
├───────────────────────────────────────────────────────────────────┤
│  GET /api/tasks/{task_id}/files/{file_path}/hash                  │
│      → { "hash": "sha256:abc123..." }                             │
│                                                                   │
│  GET /api/tasks/{task_id}/files/{file_path}  (existing, modified) │
│      → { "content": "...", "hash": "sha256:abc123..." }           │
└───────────────────────────────────────────────────────────────────┘
```

## Cache Key Format

```
filecache:{taskId}:{filePath}
```

Example: `filecache:e37e9f9c-9458-4d10-9d19-0ab7c8972ad3:src/main.ts`

Task IDs are globally unique UUIDs, so no additional project context is needed.

## Components

### Backend: Hash Endpoint

**File:** `backend/app/routers/files.py`

New endpoint:
```python
@router.get("/{task_id}/files/{file_path:path}/hash")
async def get_file_hash(
    task_id: str,
    file_path: str,
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
) -> dict:
    """Return SHA-256 hash of file content for cache validation."""
```

Implementation:
- Read file in binary mode
- Compute SHA-256 hash
- Return `{"hash": "sha256:<hex_value>"}`

### Backend: Modify Read Endpoint

**File:** `backend/app/routers/files.py`

Add `hash` field to existing read endpoint response:
```python
return {"content": content, "hash": f"sha256:{hash_value}"}
```

### Frontend: FileCacheService

**File:** `frontend/src/services/FileCacheService.ts` (new file)

```typescript
class FileCacheService {
  private static PREFIX = 'filecache:'

  // Get cached entry
  get(taskId: string, filePath: string): { hash: string; content: string } | null

  // Store entry in cache
  set(taskId: string, filePath: string, hash: string, content: string): void

  // Clear all cached entries, or just for one task
  clear(taskId?: string): void

  // Get total cache size in bytes (for debugging)
  getStorageSize(): number
}

export default new FileCacheService()
```

### Frontend: API Client

**File:** `frontend/src/api/files.ts`

Add new method and modify existing:
```typescript
// New method
getHash: (taskId: string, filePath: string) =>
  request<{ hash: string }>(`/tasks/${taskId}/files/${filePath}/hash`),

// Modified to include hash
read: (taskId: string, filePath: string) =>
  request<{ content: string; hash: string }>(`/tasks/${taskId}/files/${filePath}`),
```

### Frontend: CodeReviewView Integration

**File:** `frontend/src/views/CodeReviewView.vue`

Modify `loadFile()` function to use cache:
1. Get hash from server via `filesApi.getHash()`
2. Check localStorage via `FileCacheService.get()`
3. If cached hash matches server hash, use cached content
4. Otherwise, fetch full content and update cache

## Data Flow

### Cache Hit
```
User opens file → GET /hash → {"hash": "sha256:abc"}
                 → localStorage lookup → cached hash matches
                 → Return cached content (no content fetch)
```

### Cache Miss
```
User opens file → GET /hash → {"hash": "sha256:xyz"}
                 → localStorage lookup → null
                 → GET /read → {"content": "...", "hash": "sha256:xyz"}
                 → Store in cache → Display content
```

### Cache Stale
```
User opens file → GET /hash → {"hash": "sha256:new"}
                 → localStorage lookup → cached hash "sha256:old"
                 → Hash mismatch → GET /read → Update cache
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Hash endpoint fails | Skip cache, fetch content directly |
| localStorage quota exceeded | Clear 50% oldest entries, retry |
| localStorage unavailable | Disable caching, always fetch |
| File deleted (404) | Clear cached version, show error |
| Binary file (PDF, image) | Skip caching, use existing blob handling |

### Quota Management

```typescript
try {
  localStorage.setItem(key, value)
} catch (e) {
  if (e instanceof DOMException && e.name === 'QuotaExceededError') {
    this.clearOldEntries()  // Remove 50% oldest by access time
    localStorage.setItem(key, value)  // Retry
  }
}
```

## Testing

### Backend Tests (`backend/tests/test_files.py`)

- `test_get_file_hash_success` - Returns correct SHA-256 hash
- `test_get_file_hash_not_found` - Returns 404 for missing file
- `test_get_file_hash_directory` - Returns 400 for directory
- `test_read_includes_hash` - Read endpoint returns hash field

### Frontend Tests

**`frontend/src/services/__tests__/FileCacheService.spec.ts`**

- `get returns null for missing key`
- `set and get roundtrip`
- `clear removes all entries`
- `handles quota exceeded`
- `handles localStorage unavailable`

**`frontend/src/views/__tests__/CodeReviewView.spec.ts`** (update existing)

- `uses cached content on hash match`
- `fetches content on hash mismatch`
- `fetches content on cache miss`
- `falls back on hash endpoint error`

## Files Changed

| File | Change |
|------|--------|
| `backend/app/routers/files.py` | Add `/hash` endpoint, add hash to read response |
| `backend/app/services/file_service.py` | Add `get_file_hash()` method |
| `backend/tests/test_files.py` | Add hash endpoint tests |
| `frontend/src/services/FileCacheService.ts` | New file |
| `frontend/src/api/files.ts` | Add `getHash()`, modify `read()` return type |
| `frontend/src/views/CodeReviewView.vue` | Integrate caching in `loadFile()` |
| `frontend/src/services/__tests__/FileCacheService.spec.ts` | New test file |
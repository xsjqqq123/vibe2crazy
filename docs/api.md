# API Documentation

## Commits API

### Get Paginated Commits

Get a paginated list of commits for a task worktree.

**Endpoint:** `GET /api/tasks/{task_id}/commits`

**Query Parameters:**
- `page` (integer, optional, default: 1, minimum: 1) - Page number (1-indexed)
- `page_size` (integer, optional, default: 30, minimum: 1, maximum: 100) - Number of items per page

**Response Format:**

```json
{
  "items": [
    {
      "hash": "abc123def456...",
      "date": "2026-02-21T10:30:00+00:00",
      "message": "Commit message",
      "files": [
        {
          "path": "src/file.py",
          "status": "M",
          "additions": 10,
          "deletions": 5
        }
      ]
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 30,
  "total_pages": 5
}
```

**Response Fields:**
- `items` - Array of commit objects
- `total` - Total number of commits
- `page` - Current page number
- `page_size` - Number of items per page
- `total_pages` - Total number of pages

**Example:**

```bash
curl "http://localhost:8863/api/tasks/task-123/commits?page=2&page_size=50"
```

**Error Responses:**
- `404` - Task not found
- `422` - Invalid query parameters (e.g., page_size > 100)

## Additional API Endpoints

For complete API documentation, see the inline documentation in the backend code:
- `backend/app/routers/auth.py` - Authentication endpoints
- `backend/app/routers/projects.py` - Project management
- `backend/app/routers/tasks.py` - Task and worktree management
- `backend/app/routers/files.py` - File operations
- `backend/app/routers/git.py` - Git operations

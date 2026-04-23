# File Size Limit Feature Design

## Overview

Server-side file size validation to prevent loading files larger than 500KB in editor, diff comparison, and commit preview.

## Requirement

When a file exceeds 500KB (512000 bytes), return an error instead of the file content. Display: "File too large to display (X MB)".

## Affected Endpoints

1. `GET /{task_id}/files/{file_path}` - File editing
2. `GET /{task_id}/diff/{file_path}` - Diff comparison
3. `GET /{task_id}/original/{file_path}` - Original file for diff
4. `GET /{task_id}/commits/{commit_hash}/diff` - Commit preview (check each file)

## Technical Design

### Backend

**File: `backend/app/services/file_service.py`**

Add helper method to check file size:

```python
MAX_FILE_SIZE = 512000  # 500KB

@staticmethod
def check_file_size(worktree_path: str, file_path: str) -> tuple[bool, int, str]:
    """Check if file size is within limit.

    Returns: (is_within_limit, size_bytes, size_formatted)
    """
```

**File: `backend/app/routers/files.py`**

For each affected endpoint, check file size before reading content:
1. Get file stats
2. If size > MAX_FILE_SIZE, return error response
3. Otherwise, proceed with normal operation

**Error Response Format:**

```json
{
  "detail": "File too large to display (1.2 MB)"
}
```

Use HTTP 413 (Payload Too Large) or HTTP 400 with descriptive message.

### Frontend

Handle error response in the editor/diff component and display the message.

## Implementation Notes

- For commit diff, check each file individually and skip large files with a note
- Binary files are already handled separately (images, PDFs)
- Size formatting: use MB for >= 1MB, KB otherwise
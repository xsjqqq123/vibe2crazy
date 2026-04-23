# Symbol Preview Feature Design

**Date:** 2026-03-15
**Status:** Draft
**Author:** Claude

## Overview

Add a symbol preview feature that allows users to click on a variable or function and view its definition details in a side panel. The feature uses universal-ctags for cross-file symbol resolution within a project.

## Requirements

- **Trigger:** User clicks on a symbol in the SymbolOutline component
- **Display:** Side panel showing:
  - Definition snippet (code)
  - Docstring/JSDoc comments
  - Type signature
  - File path and line number (clickable to navigate)
- **Scope:** Cross-file resolution within the current project
- **Indexing:** Manual trigger by user (async for large projects)
- **Integration:** Extends existing SymbolOutline component

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
├─────────────────────────────────────────────────────────────┤
│  SymbolOutline.vue (extended)                               │
│  ├── Symbol list (existing)                                 │
│  └── Symbol Preview panel (new)                             │
│       ├── Definition snippet                                │
│       ├── Docstring/JSDoc                                   │
│       ├── Type signature                                    │
│       └── File:line (clickable)                             │
├─────────────────────────────────────────────────────────────┤
│  API calls:                                                 │
│  ├── POST /api/symbols/index      → Start indexing job      │
│  ├── GET  /api/symbols/index/status → Poll job status       │
│  └── GET  /api/symbols/definition → Get symbol info         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Backend                               │
├─────────────────────────────────────────────────────────────┤
│  routers/symbols.py (new)                                   │
│  ├── POST /index   → Run ctags async, return job_id         │
│  ├── GET  /index/status → Get job progress/status           │
│  └── GET  /definition → Lookup symbol, extract info         │
├─────────────────────────────────────────────────────────────┤
│  services/ctags_service.py (new)                            │
│  ├── start_index_job()  → Start background indexing         │
│  ├── get_job_status()   → Get job status/progress           │
│  ├── find_symbol()      → Find symbol in tags               │
│  └── extract_snippet()  → Read file, extract code + docs    │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

1. User clicks "Index Project" button
2. Backend starts `ctags -R` on project root in background thread
3. Returns job_id immediately, frontend polls for status
4. Tags saved to `{PROJECTS_DIR}/{project_id}/.tags/`
5. User clicks a symbol in SymbolOutline
6. Frontend sends symbol name + file context to backend
7. Backend looks up symbol in tags, reads definition file
8. Backend extracts snippet, docstring, type signature
9. Backend returns structured SymbolDefinition response
10. Frontend displays in preview panel

## API Specification

### POST /api/symbols/index

Start an asynchronous indexing job for the project.

**Request:**
```json
{
  "task_id": "uuid",
  "force": false
}
```

**Response:**
```json
{
  "job_id": "uuid",
  "status": "pending",
  "message": "Indexing started"
}
```

If already indexed and `force=false`:
```json
{
  "job_id": "uuid",
  "status": "completed",
  "cached": true,
  "indexed_files": 42,
  "indexed_symbols": 350
}
```

### GET /api/symbols/index/status

Poll the status of an indexing job.

**Query Parameters:**
- `job_id`: The job identifier

**Response (in progress):**
```json
{
  "job_id": "uuid",
  "status": "in_progress",
  "progress": {
    "files_scanned": 150,
    "total_files": 500,
    "symbols_found": 1200
  }
}
```

**Response (completed):**
```json
{
  "job_id": "uuid",
  "status": "completed",
  "indexed_files": 500,
  "indexed_symbols": 3500,
  "duration_seconds": 12.5
}
```

**Response (failed):**
```json
{
  "job_id": "uuid",
  "status": "failed",
  "error": "universal-ctags not found",
  "suggestion": "Install with: apt install universal-ctags"
}
```

### GET /api/symbols/definition

Get symbol definition details.

**Query Parameters:**
- `symbol_name`: Name of the symbol to look up
- `file_path`: Current file path (for context)
- `task_id`: Task identifier

**Response (found):**
```json
{
  "found": true,
  "name": "handleSymbolClick",
  "kind": "function",
  "file_path": "/path/to/file.ts",
  "line_number": 26,
  "type_signature": "(symbol: SymbolInfo, index: number) => void",
  "docstring": "Handles click on a symbol in the outline",
  "definition_snippet": [
    "function handleSymbolClick(symbol: SymbolInfo, index: number) {",
    "  currentIndex.value = index",
    "  emit('select', symbol)",
    "}"
  ]
}
```

**Response (not found):**
```json
{
  "found": false,
  "reason": "not_found",
  "similar_symbols": ["handleSymbol", "handleClick"]
}
```

**Response (not indexed):**
```json
{
  "found": false,
  "reason": "not_indexed",
  "message": "Project has not been indexed. Click 'Index Project' to enable symbol preview."
}
```

## Frontend Component Design

### Extended SymbolOutline.vue

```
┌─────────────────────────────────────────────┐
│ [▼] SYMBOLS (42)              [Index] [↓]   │  ← Header (existing + Index button)
├─────────────────────────────────────────────┤
│ [ƒ] handleSymbolClick    26                 │  ← Symbol list (existing)
│ [◼] SymbolInfo           4                  │
│ [v] currentIndex         19                 │
│ ...                                         │
├─────────────────────────────────────────────┤
│ ── Symbol Preview ──                        │  ← Preview panel (new, collapsible)
│ ┌─────────────────────────────────────────┐ │
│ │ function handleSymbolClick(             │ │  ← Definition snippet (monospace)
│ │   symbol: SymbolInfo,                   │ │
│ │   index: number                         │ │
│ │ ) => void                               │ │
│ └─────────────────────────────────────────┘ │
│ ─── Docstring ───                           │
│ Handles click on a symbol in the outline.   │  ← Docstring (if present)
│                                             │
│ 📄 SymbolOutline.vue:26                     │  ← File path + line (clickable)
└─────────────────────────────────────────────┘
```

### New State

```typescript
interface IndexStatus {
  jobId: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  progress?: {
    filesScanned: number
    totalFiles: number
    symbolsFound: number
  }
  indexedFiles?: number
  indexedSymbols?: number
  error?: string
}

interface SymbolDefinition {
  found: boolean
  name?: string
  kind?: 'function' | 'class' | 'variable' | 'constant'
  filePath?: string
  lineNumber?: number
  typeSignature?: string
  docstring?: string
  definitionSnippet?: string[]
  reason?: string
  similarSymbols?: string[]
}

// Component state
const previewSymbol = ref<SymbolInfo | null>(null)
const previewData = ref<SymbolDefinition | null>(null)
const previewLoading = ref(false)
const indexingStatus = ref<IndexStatus | null>(null)
```

### User Interactions

1. Click symbol in list → Load preview for that symbol
2. Click file path in preview → Navigate to that file/line
3. Click "Index" button → Start indexing job, poll for status
4. Collapse/expand preview panel

## Backend Service Design

### services/ctags_service.py

```python
from dataclasses import dataclass
from typing import Optional, Dict, List
from enum import Enum
import asyncio
import json
import subprocess
import os

class JobStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class IndexJob:
    job_id: str
    task_id: str
    status: JobStatus
    progress: Optional[Dict] = None
    indexed_files: int = 0
    indexed_symbols: int = 0
    error: Optional[str] = None

@dataclass
class SymbolDefinition:
    found: bool
    name: Optional[str] = None
    kind: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    type_signature: Optional[str] = None
    docstring: Optional[str] = None
    definition_snippet: Optional[List[str]] = None
    reason: Optional[str] = None
    similar_symbols: Optional[List[str]] = None

class CtagsService:
    def __init__(self, projects_dir: str):
        self.projects_dir = projects_dir
        self.jobs: Dict[str, IndexJob] = {}

    async def start_index_job(self, task_id: str, force: bool = False) -> IndexJob:
        """Start background indexing, return job immediately"""

    def get_job_status(self, job_id: str) -> Optional[IndexJob]:
        """Get current status of an indexing job"""

    def find_symbol(self, task_id: str, symbol_name: str,
                    context_file: str) -> SymbolDefinition:
        """Look up symbol in tags file, extract definition details"""

    def _run_ctags(self, project_path: str, tags_path: str) -> Dict:
        """Execute universal-ctags, return parsed result"""

    def _extract_definition_snippet(self, file_path: str,
                                     line_number: int,
                                     language: str) -> List[str]:
        """Read file, extract code around definition line (max 15 lines)"""

    def _extract_docstring(self, content: str, line_number: int,
                           language: str) -> Optional[str]:
        """Extract JSDoc/docstring above the definition"""

    def _extract_type_signature(self, content: str, line_number: int,
                                 language: str) -> Optional[str]:
        """Extract type signature from definition line"""
```

### ctags Command

```bash
ctags -R \
  --fields=+neKSt \
  --extras=+q \
  --output-format=json \
  --languages=Python,JavaScript,TypeScript,Vue,Go,Rust,C,C++ \
  --exclude=node_modules \
  --exclude=.git \
  --exclude=__pycache__ \
  --exclude=*.min.js \
  --exclude=dist \
  --exclude=build \
  /path/to/project
```

### Tags File Storage

```
{PROJECTS_DIR}/{project_id}/.tags/
├── tags.json      # Parsed tags in JSON format for fast lookup
└── metadata.json  # Index timestamp, file count, symbol count
```

## Error Handling

### Indexing Errors

| Scenario | Handling |
|----------|----------|
| ctags not installed | Return error: "universal-ctags not found. Install with: `apt install universal-ctags`" |
| Empty project | Return success with 0 files/symbols indexed |
| Permission denied | Return error with specific file path that failed |
| Index job already running | Return existing job_id, don't start new one |
| Large project (>10k files) | Warn in UI before indexing |

### Symbol Lookup Errors

| Scenario | Handling |
|----------|----------|
| Project not indexed | Return `{ found: false, reason: "not_indexed" }` |
| Symbol not found | Return `{ found: false, similar_symbols: [...] }` |
| Multiple definitions | Return all matches, let user choose |
| File deleted after indexing | Return `{ found: false, reason: "file_not_found" }` |
| Tags file corrupted | Auto-delete, prompt re-index |

### Definition Extraction Edge Cases

| Scenario | Handling |
|----------|----------|
| Definition spans many lines | Limit snippet to 15 lines max |
| No docstring present | Show "No documentation" placeholder |
| Minified/obfuscated code | Skip during indexing (file size threshold) |
| Binary file | Skip during indexing |

## Frontend UX

- Toast notification when indexing completes
- Disable "Index" button while indexing in progress
- Cache symbol preview result for current session
- Loading spinner while fetching definition
- Progress indicator: "Indexing... 150/500 files"

## Dependencies

### Backend

- `universal-ctags` must be installed on the server
- Python standard library (asyncio, subprocess, json)

### Frontend

- No new dependencies required
- Reuses existing Monaco Editor and SymbolOutline components

## Implementation Order

1. Backend: Create `services/ctags_service.py`
2. Backend: Create `routers/symbols.py`
3. Backend: Register router in `main.py`
4. Frontend: Create `api/symbols.ts`
5. Frontend: Extend `SymbolOutline.vue` with preview panel
6. Frontend: Add Index button and status polling
7. Frontend: Integrate with CodeReviewView for navigation
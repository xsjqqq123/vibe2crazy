# Symbol Preview Feature Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a symbol preview feature that allows users to click on a symbol and view its definition, docstring, type signature, and location in a side panel, using universal-ctags for cross-file symbol resolution.

**Architecture:** Backend runs ctags to generate symbol index asynchronously, stores tags in JSON format. Frontend extends SymbolOutline component with a preview panel. API provides endpoints for starting indexing jobs, polling status, and fetching symbol definitions.

**Tech Stack:** Python/FastAPI (backend), Vue 3/TypeScript (frontend), universal-ctags (symbol indexing)

---

## File Structure

**Backend (new files):**
- `backend/app/services/ctags_service.py` - Core ctags operations, indexing, symbol lookup
- `backend/app/routers/symbols.py` - API endpoints for indexing and definition lookup

**Backend (modified files):**
- `backend/app/main.py` - Register new router
- `backend/app/schemas.py` - Add Pydantic schemas for new endpoints

**Frontend (new files):**
- `frontend/src/api/symbols.ts` - API client for symbol endpoints

**Frontend (modified files):**
- `frontend/src/components/Monaco/SymbolOutline.vue` - Add preview panel and index button
- `frontend/src/views/CodeReviewView.vue` - Pass taskId prop and handle navigation events

---

## Chunk 1: Backend Service - CtagsService

### Task 1: Create CtagsService with data models and job tracking

**Files:**
- Create: `backend/app/services/ctags_service.py`

- [ ] **Step 1: Write the service file with data models and job tracking**

```python
# backend/app/services/ctags_service.py
import subprocess
import json
import os
import uuid
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IndexJob:
    """Represents an indexing job status"""
    job_id: str
    task_id: str
    status: JobStatus
    progress: Optional[Dict] = None
    indexed_files: int = 0
    indexed_symbols: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    suggestion: Optional[str] = None
    cached: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SymbolMatch:
    """A single symbol match from ctags"""
    name: str
    file_path: str
    line_number: int
    kind: str
    signature: Optional[str] = None
    scope: Optional[str] = None


@dataclass
class SymbolDefinition:
    """Full symbol definition with extracted details"""
    found: bool
    name: Optional[str] = None
    kind: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    type_signature: Optional[str] = None
    docstring: Optional[str] = None
    definition_snippet: Optional[List[str]] = None
    reason: Optional[str] = None
    message: Optional[str] = None
    similar_symbols: Optional[List[str]] = None
    matches: Optional[List[Dict]] = None  # For multiple definitions


class CtagsService:
    """Service for managing ctags-based symbol indexing and lookup"""

    # Supported languages for ctags
    SUPPORTED_LANGUAGES = [
        "Python", "JavaScript", "TypeScript", "Vue", "Go", "Rust", "C", "C++"
    ]

    # Directories to exclude from indexing
    EXCLUDE_PATTERNS = [
        "node_modules",
        ".git",
        "__pycache__",
        "*.min.js",
        "dist",
        "build",
        ".venv",
        "venv",
        ".tox",
        "*.egg-info",
    ]

    # Maximum lines for definition snippet
    MAX_SNIPPET_LINES = 15

    # File size threshold to skip (500KB)
    MAX_FILE_SIZE = 500 * 1024

    def __init__(self, projects_dir: str):
        self.projects_dir = Path(projects_dir)
        self.jobs: Dict[str, IndexJob] = {}
        self._lock = threading.Lock()

    def _get_tags_dir(self, project_id: str) -> Path:
        """Get the tags directory for a project"""
        tags_dir = self.projects_dir / project_id / ".tags"
        tags_dir.mkdir(parents=True, exist_ok=True)
        return tags_dir

    def _get_tags_file(self, project_id: str) -> Path:
        """Get the tags JSON file path"""
        return self._get_tags_dir(project_id) / "tags.json"

    def _get_metadata_file(self, project_id: str) -> Path:
        """Get the metadata JSON file path"""
        return self._get_tags_dir(project_id) / "metadata.json"

    def check_ctags_installed(self) -> tuple[bool, str]:
        """Check if universal-ctags is installed and available"""
        try:
            result = subprocess.run(
                ["ctags", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Check it's universal-ctags, not exuberant-ctags
                if "Universal Ctags" in result.stdout:
                    return True, ""
                else:
                    return False, "universal-ctags not found. Found older ctags version."
            return False, "ctags command failed"
        except FileNotFoundError:
            return False, "universal-ctags not found. Install with: apt install universal-ctags"
        except subprocess.TimeoutExpired:
            return False, "ctags command timed out"
        except Exception as e:
            return False, f"Error checking ctags: {str(e)}"

    def start_index_job(self, task_id: str, project_id: str, force: bool = False) -> IndexJob:
        """Start an asynchronous indexing job for a project"""
        job_id = str(uuid.uuid4())

        # Check if ctags is installed
        installed, error_msg = self.check_ctags_installed()
        if not installed:
            return IndexJob(
                job_id=job_id,
                task_id=task_id,
                status=JobStatus.FAILED,
                error=error_msg,
                suggestion="Install with: apt install universal-ctags"
            )

        # Check for existing completed index if not forcing
        if not force:
            metadata_file = self._get_metadata_file(project_id)
            if metadata_file.exists():
                try:
                    with open(metadata_file) as f:
                        metadata = json.load(f)
                    return IndexJob(
                        job_id=job_id,
                        task_id=task_id,
                        status=JobStatus.COMPLETED,
                        indexed_files=metadata.get("file_count", 0),
                        indexed_symbols=metadata.get("symbol_count", 0),
                        duration_seconds=metadata.get("duration_seconds", 0),
                        cached=True
                    )
                except Exception as e:
                    logger.warning(f"Failed to read metadata: {e}")

        # Create pending job
        job = IndexJob(
            job_id=job_id,
            task_id=task_id,
            status=JobStatus.PENDING
        )

        with self._lock:
            self.jobs[job_id] = job

        # Start indexing in background thread
        thread = threading.Thread(
            target=self._run_indexing,
            args=(job_id, project_id)
        )
        thread.daemon = True
        thread.start()

        return job

    def _run_indexing(self, job_id: str, project_id: str):
        """Run the actual indexing (called in background thread)"""
        start_time = time.time()

        with self._lock:
            if job_id not in self.jobs:
                return
            self.jobs[job_id].status = JobStatus.IN_PROGRESS
            self.jobs[job_id].progress = {"files_scanned": 0, "total_files": 0, "symbols_found": 0}

        try:
            project_path = self.projects_dir / project_id
            tags_file = self._get_tags_file(project_id)
            metadata_file = self._get_metadata_file(project_id)

            # Build ctags command
            exclude_args = [f"--exclude={pattern}" for pattern in self.EXCLUDE_PATTERNS]
            language_args = [f"--languages={','.join(self.SUPPORTED_LANGUAGES)}"]

            cmd = [
                "ctags",
                "-R",
                "--fields=+neKSt",
                "--extras=+q",
                "--output-format=json",
            ] + exclude_args + language_args + [str(project_path)]

            logger.info(f"Running ctags: {' '.join(cmd)}")

            # Run ctags
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                raise Exception(f"ctags failed: {result.stderr}")

            # Parse ctags output
            tags = {}
            symbol_count = 0
            file_count = 0
            seen_files = set()

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                try:
                    tag = json.loads(line)
                    name = tag.get("name")
                    if not name:
                        continue

                    file_path = tag.get("path", "")
                    line_number = tag.get("line", 1)
                    kind = tag.get("kind", "unknown")
                    signature = tag.get("signature", "")
                    scope = tag.get("scope", "")

                    # Track files
                    if file_path and file_path not in seen_files:
                        seen_files.add(file_path)
                        file_count += 1

                    # Store tag
                    if name not in tags:
                        tags[name] = []

                    tags[name].append({
                        "file_path": file_path,
                        "line_number": line_number,
                        "kind": kind,
                        "signature": signature,
                        "scope": scope
                    })
                    symbol_count += 1

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse ctags line: {e}")
                    continue

            # Save tags to JSON file
            with open(tags_file, 'w') as f:
                json.dump(tags, f)

            # Save metadata
            duration = time.time() - start_time
            metadata = {
                "file_count": file_count,
                "symbol_count": symbol_count,
                "duration_seconds": duration,
                "indexed_at": time.time()
            }
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f)

            # Update job status
            with self._lock:
                if job_id in self.jobs:
                    self.jobs[job_id].status = JobStatus.COMPLETED
                    self.jobs[job_id].indexed_files = file_count
                    self.jobs[job_id].indexed_symbols = symbol_count
                    self.jobs[job_id].duration_seconds = duration
                    self.jobs[job_id].progress = None

            logger.info(f"Indexing completed: {file_count} files, {symbol_count} symbols in {duration:.2f}s")

        except subprocess.TimeoutExpired:
            with self._lock:
                if job_id in self.jobs:
                    self.jobs[job_id].status = JobStatus.FAILED
                    self.jobs[job_id].error = "Indexing timed out (>5 minutes)"
                    self.jobs[job_id].suggestion = "Try indexing a smaller project or check for large files"
        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            with self._lock:
                if job_id in self.jobs:
                    self.jobs[job_id].status = JobStatus.FAILED
                    self.jobs[job_id].error = str(e)

    def get_job_status(self, job_id: str) -> Optional[IndexJob]:
        """Get the status of an indexing job"""
        with self._lock:
            return self.jobs.get(job_id)

    def find_symbol(self, project_id: str, symbol_name: str, context_file: str = "") -> SymbolDefinition:
        """Look up a symbol in the tags file and extract its definition"""
        tags_file = self._get_tags_file(project_id)

        if not tags_file.exists():
            return SymbolDefinition(
                found=False,
                reason="not_indexed",
                message="Project has not been indexed. Click 'Index Project' to enable symbol preview."
            )

        try:
            with open(tags_file) as f:
                tags = json.load(f)
        except json.JSONDecodeError:
            # Corrupted tags file
            tags_file.unlink()
            return SymbolDefinition(
                found=False,
                reason="corrupted_index",
                message="Tags file corrupted. Please re-index the project."
            )

        # Look for exact match
        if symbol_name not in tags:
            # Try to find similar symbols
            similar = []
            for name in tags.keys():
                if symbol_name.lower() in name.lower() or name.lower() in symbol_name.lower():
                    similar.append(name)
                if len(similar) >= 5:
                    break

            return SymbolDefinition(
                found=False,
                reason="not_found",
                similar_symbols=similar[:5]
            )

        matches = tags[symbol_name]

        # If multiple matches, prefer matches from the same file as context
        if len(matches) > 1 and context_file:
            same_file_matches = [m for m in matches if context_file in m.get("file_path", "")]
            if same_file_matches:
                matches = same_file_matches

        # If still multiple matches, return all for user to choose
        if len(matches) > 1:
            return SymbolDefinition(
                found=True,
                name=symbol_name,
                kind=matches[0].get("kind", "unknown"),
                matches=[{
                    "file_path": m.get("file_path", ""),
                    "line_number": m.get("line_number", 1),
                    "kind": m.get("kind", "unknown"),
                    "signature": m.get("signature", "")
                } for m in matches]
            )

        # Single match - extract full details
        match = matches[0]
        file_path = match.get("file_path", "")
        line_number = match.get("line_number", 1)
        kind = match.get("kind", "unknown")
        signature = match.get("signature", "")

        # Extract definition snippet and docstring
        snippet, docstring, extracted_signature = self._extract_definition_details(
            file_path, line_number, kind
        )

        return SymbolDefinition(
            found=True,
            name=symbol_name,
            kind=kind,
            file_path=file_path,
            line_number=line_number,
            type_signature=extracted_signature or signature,
            docstring=docstring,
            definition_snippet=snippet
        )

    def _extract_definition_details(self, file_path: str, line_number: int, kind: str) -> tuple[List[str], Optional[str], Optional[str]]:
        """Extract definition snippet, docstring, and signature from source file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return [], None, None
        except Exception as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            return [], None, None

        # Get snippet (lines around the definition)
        start = max(0, line_number - 1)
        end = min(len(lines), line_number + self.MAX_SNIPPET_LINES - 1)

        # Try to find the end of the definition (for multi-line definitions)
        if kind in ("function", "method", "f"):
            end = self._find_definition_end(lines, start, end)
        elif kind in ("class", "struct", "interface"):
            end = min(len(lines), start + 5)  # Just get the class header

        snippet = [lines[i].rstrip('\n\r') for i in range(start, end)]

        # Extract docstring (comments above the definition)
        docstring = self._extract_docstring(lines, line_number - 1, file_path)

        # Extract signature from first line of snippet
        signature = None
        if snippet:
            first_line = snippet[0].strip()
            signature = self._extract_signature(first_line, file_path)

        return snippet, docstring, signature

    def _find_definition_end(self, lines: List[str], start: int, default_end: int) -> int:
        """Find the end of a function/method definition"""
        brace_count = 0
        found_opening = False
        in_definition = False

        for i in range(start, min(len(lines), start + 50)):
            line = lines[i]

            # Count braces for C-style languages
            brace_count += line.count('{') - line.count('}')
            if '{' in line:
                found_opening = True
                in_definition = True

            # For Python, look for dedent
            if start > 0 and i > start:
                if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                    if lines[start].startswith(' ') or lines[start].startswith('\t'):
                        return i

            # If braces balanced and we found opening, we're done
            if found_opening and brace_count <= 0 and in_definition:
                return i + 1

        return default_end

    def _extract_docstring(self, lines: List[str], def_line: int, file_path: str) -> Optional[str]:
        """Extract docstring/JSDoc above the definition"""
        if def_line <= 0:
            return None

        # Determine comment style based on file extension
        ext = Path(file_path).suffix.lower()
        is_python = ext == '.py'
        is_c_style = ext in ('.js', '.ts', '.vue', '.go', '.c', '.cpp', '.h', '.hpp', '.rs')

        doc_lines = []
        i = def_line - 1

        if is_python:
            # Look for Python docstrings (""" or ''')
            while i >= 0:
                line = lines[i].strip()
                if line.startswith('#'):
                    doc_lines.insert(0, line[1:].strip())
                    i -= 1
                elif not line:
                    i -= 1
                else:
                    break

            # Also check for triple-quoted docstring right after definition
            if def_line + 1 < len(lines):
                next_line = lines[def_line + 1].strip()
                if next_line.startswith('"""') or next_line.startswith("'''"):
                    quote = '"""' if next_line.startswith('"""') else "'''"
                    doc_start = def_line + 1
                    doc_end = doc_start
                    # Find closing quote
                    for j in range(doc_start + 1, min(len(lines), doc_start + 30)):
                        if quote in lines[j]:
                            doc_end = j + 1
                            break
                    docstring = ''.join(lines[doc_start:doc_end]).replace(quote, '').strip()
                    if doc_lines:
                        return ' '.join(doc_lines) + '\n' + docstring
                    return docstring if docstring else None

        elif is_c_style:
            # Look for JSDoc/C-style comments (/** ... */ or ///)
            in_block_comment = False
            while i >= 0:
                line = lines[i].strip()

                if line.endswith('*/'):
                    in_block_comment = True
                    # Extract content before */
                    content = line[:-2].strip()
                    if content.startswith('*'):
                        content = content[1:].strip()
                    if content.startswith('/**'):
                        content = content[3:].strip()
                    if content.startswith('*'):
                        content = content[1:].strip()
                    if content:
                        doc_lines.insert(0, content)
                    i -= 1
                    continue

                if in_block_comment:
                    if line.startswith('/*'):
                        in_block_comment = False
                        content = line[2:].strip()
                        if content.startswith('*'):
                            content = content[1:].strip()
                        if content.startswith('**'):
                            content = content[2:].strip()
                        if content:
                            doc_lines.insert(0, content)
                    elif line.startswith('*'):
                        content = line[1:].strip()
                        if content:
                            doc_lines.insert(0, content)
                    i -= 1
                    continue

                if line.startswith('///'):
                    doc_lines.insert(0, line[3:].strip())
                    i -= 1
                    continue

                if not line:
                    i -= 1
                    continue

                break

        if doc_lines:
            return '\n'.join(doc_lines)

        return None

    def _extract_signature(self, line: str, file_path: str) -> Optional[str]:
        """Extract type signature from definition line"""
        # This is a simplified extraction - the actual signature comes from ctags
        # Just clean up the line for display
        line = line.strip()
        if len(line) > 100:
            return line[:97] + "..."
        return line


# Global service instance
_ctags_service: Optional[CtagsService] = None


def get_ctags_service() -> CtagsService:
    """Get the global CtagsService instance"""
    global _ctags_service
    if _ctags_service is None:
        from app.config import settings
        _ctags_service = CtagsService(settings.projects_dir)
    return _ctags_service
```

- [ ] **Step 2: Commit the ctags service**

```bash
git add backend/app/services/ctags_service.py
git commit -m "$(cat <<'EOF'
feat(backend): add CtagsService for symbol indexing and lookup

- Add async indexing with job tracking
- Support multiple languages (Python, JS, TS, Vue, Go, Rust, C, C++)
- Extract definition snippets, docstrings, and signatures
- Handle multiple symbol matches with disambiguation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 2: Backend Router and Schemas

### Task 2: Add Pydantic schemas for symbol endpoints

**Files:**
- Modify: `backend/app/schemas.py`

- [ ] **Step 1: Add symbol-related schemas to schemas.py**

Add at the end of `backend/app/schemas.py`:

```python
# Symbol preview schemas
class IndexRequest(BaseModel):
    task_id: str
    force: bool = False


class IndexProgress(BaseModel):
    files_scanned: int
    total_files: int
    symbols_found: int


class IndexResponse(BaseModel):
    job_id: str
    status: str
    message: Optional[str] = None
    cached: bool = False
    indexed_files: Optional[int] = None
    indexed_symbols: Optional[int] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    suggestion: Optional[str] = None
    progress: Optional[IndexProgress] = None


class SymbolMatchItem(BaseModel):
    """A single symbol match for disambiguation"""
    file_path: str
    line_number: int
    kind: str
    signature: Optional[str] = None


class SymbolDefinitionResponse(BaseModel):
    found: bool
    name: Optional[str] = None
    kind: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    type_signature: Optional[str] = None
    docstring: Optional[str] = None
    definition_snippet: Optional[List[str]] = None
    reason: Optional[str] = None
    message: Optional[str] = None
    similar_symbols: Optional[List[str]] = None
    matches: Optional[List[SymbolMatchItem]] = None
```

- [ ] **Step 2: Commit schemas**

```bash
git add backend/app/schemas.py
git commit -m "$(cat <<'EOF'
feat(backend): add Pydantic schemas for symbol preview API

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Task 3: Create symbols router

**Files:**
- Create: `backend/app/routers/symbols.py`

- [ ] **Step 1: Create the symbols router file**

```python
# backend/app/routers/symbols.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Task, Project
from app.schemas import (
    IndexRequest, IndexResponse, IndexProgress,
    SymbolDefinitionResponse, SymbolMatchItem
)
from app.auth import require_auth
from app.services.ctags_service import get_ctags_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


@router.post("/index", response_model=IndexResponse)
async def start_index(
    request: IndexRequest,
    db: Session = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Start an asynchronous indexing job for the project"""
    # Get task to find project
    task = db.query(Task).filter(Task.id == request.task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Get project ID from the worktree path
    # worktree_path is like: {PROJECTS_DIR}/{project_id}/{task_id}
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    ctags_service = get_ctags_service()
    job = ctags_service.start_index_job(
        task_id=request.task_id,
        project_id=project.id,
        force=request.force
    )

    response = IndexResponse(
        job_id=job.job_id,
        status=job.status.value,
        cached=job.cached,
        indexed_files=job.indexed_files,
        indexed_symbols=job.indexed_symbols,
        duration_seconds=job.duration_seconds,
        error=job.error,
        suggestion=job.suggestion
    )

    if job.progress:
        response.progress = IndexProgress(**job.progress)

    if job.status.value == "failed":
        response.message = job.error
    elif job.cached:
        response.message = "Using cached index"
    else:
        response.message = "Indexing started"

    return response


@router.get("/index/status", response_model=IndexResponse)
async def get_index_status(
    job_id: str = Query(..., description="The job identifier"),
    current_user: Task = Depends(require_auth)
):
    """Get the status of an indexing job"""
    ctags_service = get_ctags_service()
    job = ctags_service.get_job_status(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    response = IndexResponse(
        job_id=job.job_id,
        status=job.status.value,
        cached=job.cached,
        indexed_files=job.indexed_files,
        indexed_symbols=job.indexed_symbols,
        duration_seconds=job.duration_seconds,
        error=job.error,
        suggestion=job.suggestion
    )

    if job.progress:
        response.progress = IndexProgress(**job.progress)

    return response


@router.get("/definition", response_model=SymbolDefinitionResponse)
async def get_symbol_definition(
    symbol_name: str = Query(..., description="Name of the symbol to look up"),
    file_path: str = Query("", description="Current file path for context"),
    task_id: str = Query(..., description="Task identifier"),
    db: Session = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Get symbol definition details"""
    # Get task to find project
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    ctags_service = get_ctags_service()
    result = ctags_service.find_symbol(
        project_id=project.id,
        symbol_name=symbol_name,
        context_file=file_path
    )

    response = SymbolDefinitionResponse(
        found=result.found,
        name=result.name,
        kind=result.kind,
        file_path=result.file_path,
        line_number=result.line_number,
        type_signature=result.type_signature,
        docstring=result.docstring,
        definition_snippet=result.definition_snippet,
        reason=result.reason,
        message=result.message,
        similar_symbols=result.similar_symbols
    )

    if result.matches:
        response.matches = [
            SymbolMatchItem(**m) for m in result.matches
        ]

    return response
```

- [ ] **Step 2: Commit the symbols router**

```bash
git add backend/app/routers/symbols.py
git commit -m "$(cat <<'EOF'
feat(backend): add symbols router for indexing and definition lookup

- POST /api/symbols/index - Start async indexing job
- GET /api/symbols/index/status - Poll job status
- GET /api/symbols/definition - Look up symbol definition

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Task 4: Register router in main.py

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add import and register symbols router**

Add import after other router imports (around line 12):

```python
from app.routers import auth, projects, tasks, files, git, terminals, queues, command_presets, filesystem, symbols
```

Add router registration after other routers (around line 68):

```python
app.include_router(symbols.router)
```

- [ ] **Step 2: Commit main.py changes**

```bash
git add backend/app/main.py
git commit -m "$(cat <<'EOF'
feat(backend): register symbols router in main.py

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 3: Frontend API Client

### Task 5: Create symbols API client

**Files:**
- Create: `frontend/src/api/symbols.ts`

- [ ] **Step 1: Create the API client file**

```typescript
// frontend/src/api/symbols.ts
import request from './client'

export interface IndexProgress {
  files_scanned: number
  total_files: number
  symbols_found: number
}

export interface IndexResponse {
  job_id: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  message?: string
  cached: boolean
  indexed_files?: number
  indexed_symbols?: number
  duration_seconds?: number
  error?: string
  suggestion?: string
  progress?: IndexProgress
}

export interface SymbolMatchItem {
  file_path: string
  line_number: number
  kind: string
  signature?: string
}

export interface SymbolDefinitionResponse {
  found: boolean
  name?: string
  kind?: string
  file_path?: string
  line_number?: number
  type_signature?: string
  docstring?: string
  definition_snippet?: string[]
  reason?: string
  message?: string
  similar_symbols?: string[]
  matches?: SymbolMatchItem[]
}

/**
 * Start an asynchronous indexing job for the project
 */
export async function startIndexJob(
  taskId: string,
  force: boolean = false
): Promise<IndexResponse> {
  return request<IndexResponse>('/symbols/index', {
    method: 'POST',
    body: JSON.stringify({ task_id: taskId, force })
  })
}

/**
 * Get the status of an indexing job
 */
export async function getIndexStatus(jobId: string): Promise<IndexResponse> {
  return request<IndexResponse>(`/symbols/index/status?job_id=${encodeURIComponent(jobId)}`)
}

/**
 * Get symbol definition details
 */
export async function getSymbolDefinition(
  symbolName: string,
  filePath: string,
  taskId: string
): Promise<SymbolDefinitionResponse> {
  const params = new URLSearchParams({
    symbol_name: symbolName,
    file_path: filePath,
    task_id: taskId
  })
  return request<SymbolDefinitionResponse>(`/symbols/definition?${params}`)
}

export const symbolsApi = {
  startIndexJob,
  getIndexStatus,
  getSymbolDefinition
}
```

- [ ] **Step 2: Commit the API client**

```bash
git add frontend/src/api/symbols.ts
git commit -m "$(cat <<'EOF'
feat(frontend): add symbols API client

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 4: Frontend SymbolOutline Component Extension

### Task 6: Extend SymbolOutline with preview panel and index button

**Files:**
- Modify: `frontend/src/components/Monaco/SymbolOutline.vue`

- [ ] **Step 1: Replace the entire SymbolOutline.vue with extended version**

The file should be completely replaced with:

```vue
<!-- frontend/src/components/Monaco/SymbolOutline.vue -->
<script setup lang="ts">
import { ref, watch, computed, onUnmounted } from 'vue'
import type { SymbolInfo } from '@/composables/useSymbolOutline'
import { symbolsApi, type IndexResponse, type SymbolDefinitionResponse, type SymbolMatchItem } from '@/api/symbols'

interface Props {
  symbols: SymbolInfo[]
  collapsed: boolean
  taskId?: string
  currentFilePath?: string
}

interface Emits {
  (e: 'select', symbol: SymbolInfo): void
  (e: 'toggle'): void
  (e: 'navigate', filePath: string, lineNumber: number): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const currentIndex = ref(-1)

// Indexing state
const isIndexing = ref(false)
const indexStatus = ref<IndexResponse | null>(null)
const indexError = ref<string | null>(null)

// Preview state
const previewSymbol = ref<SymbolInfo | null>(null)
const previewData = ref<SymbolDefinitionResponse | null>(null)
const previewLoading = ref(false)
const previewError = ref<string | null>(null)
const previewCollapsed = ref(false)
const selectedMatchIndex = ref(0)

// Polling for index status
let pollInterval: ReturnType<typeof setInterval> | null = null

// Reset index when symbols change
watch(() => props.symbols, () => {
  currentIndex.value = -1
})

// Cleanup polling on unmount
onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
})

function handleSymbolClick(symbol: SymbolInfo, index: number) {
  currentIndex.value = index
  emit('select', symbol)
  loadPreview(symbol)
}

function handleToggle() {
  emit('toggle')
}

function handleNext() {
  if (props.symbols.length === 0) return
  currentIndex.value = (currentIndex.value + 1) % props.symbols.length
  emit('select', props.symbols[currentIndex.value])
}

async function handleIndexClick() {
  if (!props.taskId) return

  indexError.value = null
  isIndexing.value = true

  try {
    const response = await symbolsApi.startIndexJob(props.taskId, false)
    indexStatus.value = response

    if (response.cached) {
      // Already indexed
      isIndexing.value = false
      return
    }

    if (response.status === 'failed') {
      indexError.value = response.error || 'Indexing failed'
      isIndexing.value = false
      return
    }

    // Start polling for status
    pollInterval = setInterval(async () => {
      try {
        const status = await symbolsApi.getIndexStatus(response.job_id)
        indexStatus.value = status

        if (status.status === 'completed' || status.status === 'failed') {
          if (pollInterval) {
            clearInterval(pollInterval)
            pollInterval = null
          }
          isIndexing.value = false
          if (status.status === 'failed') {
            indexError.value = status.error || 'Indexing failed'
          }
        }
      } catch (e) {
        console.error('Failed to poll index status:', e)
      }
    }, 2000)
  } catch (e) {
    indexError.value = e instanceof Error ? e.message : 'Failed to start indexing'
    isIndexing.value = false
  }
}

async function loadPreview(symbol: SymbolInfo) {
  if (!props.taskId) {
    previewData.value = {
      found: false,
      reason: 'no_task',
      message: 'No task selected'
    }
    return
  }

  previewSymbol.value = symbol
  previewLoading.value = true
  previewError.value = null
  previewData.value = null

  try {
    const response = await symbolsApi.getSymbolDefinition(
      symbol.name,
      props.currentFilePath || '',
      props.taskId
    )
    previewData.value = response
    selectedMatchIndex.value = 0
  } catch (e) {
    previewError.value = e instanceof Error ? e.message : 'Failed to load preview'
  } finally {
    previewLoading.value = false
  }
}

function handleNavigateToSymbol(match?: SymbolMatchItem) {
  const data = match || (previewData.value?.matches?.[selectedMatchIndex.value])
  if (data?.file_path && data.line_number) {
    emit('navigate', data.file_path, data.line_number)
  } else if (previewData.value?.file_path && previewData.value?.line_number) {
    emit('navigate', previewData.value.file_path, previewData.value.line_number)
  }
}

function handleSelectMatch(index: number) {
  selectedMatchIndex.value = index
}

function getSymbolClass(kind: SymbolInfo['kind']): string {
  return `symbol-${kind}`
}

function getSymbolIcon(kind: SymbolInfo['kind']): string {
  switch (kind) {
    case 'function': return 'ƒ'
    case 'class': return '◼'
    case 'variable': return 'v'
    case 'import': return '📥'
    case 'constant': return 'C'
    default: return '•'
  }
}

function formatFilePath(filePath: string): string {
  // Show only the last 2-3 path segments
  const parts = filePath.split('/')
  if (parts.length <= 3) return filePath
  return '.../' + parts.slice(-3).join('/')
}

const indexButtonText = computed(() => {
  if (isIndexing.value && indexStatus.value?.progress) {
    const { files_scanned, symbols_found } = indexStatus.value.progress
    return `${files_scanned} files`
  }
  return 'Index'
})

const indexButtonTitle = computed(() => {
  if (isIndexing.value) {
    return 'Indexing in progress...'
  }
  if (indexStatus.value?.cached) {
    return `Indexed: ${indexStatus.value.indexed_files} files, ${indexStatus.value.indexed_symbols} symbols`
  }
  return 'Index project for symbol preview'
})
</script>

<template>
  <div class="symbol-outline" :class="{ 'is-collapsed': collapsed }">
    <!-- Header -->
    <div class="outline-header">
      <button class="outline-toggle" @click="handleToggle" :title="collapsed ? 'Expand' : 'Collapse'">
        <span v-if="collapsed">&#9654;</span>
        <span v-else>&#9660;</span>
      </button>
      <span class="outline-title">SYMBOLS</span>
      <span v-if="symbols.length > 0" class="outline-count">({{ symbols.length }})</span>
      <button
        v-if="taskId"
        class="outline-index"
        :class="{ 'is-indexing': isIndexing }"
        @click="handleIndexClick"
        :disabled="isIndexing"
        :title="indexButtonTitle"
      >
        {{ indexButtonText }}
      </button>
      <button
        v-if="symbols.length > 0"
        class="outline-next"
        @click="handleNext"
        title="Go to next symbol"
      >
        ↓
      </button>
    </div>

    <!-- Content -->
    <div v-if="!collapsed" class="outline-content">
      <!-- Index error -->
      <div v-if="indexError" class="index-error">
        {{ indexError }}
        <button @click="indexError = null" class="error-dismiss">×</button>
      </div>

      <!-- Symbol list -->
      <div v-if="symbols.length === 0" class="no-symbols">
        No symbols found
      </div>
      <div v-else class="symbol-tags">
        <button
          v-for="(symbol, index) in symbols"
          :key="`${symbol.kind}-${symbol.name}-${index}`"
          class="symbol-tag"
          :class="[getSymbolClass(symbol.kind), { 'is-active': index === currentIndex }]"
          @click="handleSymbolClick(symbol, index)"
          :title="`${symbol.name} (line ${symbol.lineNumber})`"
        >
          <span class="symbol-icon">{{ getSymbolIcon(symbol.kind) }}</span>
          <span class="symbol-name">{{ symbol.name }}</span>
          <span class="symbol-line">{{ symbol.lineNumber }}</span>
        </button>
      </div>

      <!-- Preview Panel -->
      <div v-if="previewSymbol" class="preview-panel" :class="{ 'is-collapsed': previewCollapsed }">
        <div class="preview-header" @click="previewCollapsed = !previewCollapsed">
          <span class="preview-toggle">{{ previewCollapsed ? '▶' : '▼' }}</span>
          <span class="preview-title">Symbol Preview</span>
          <span class="preview-name">{{ previewSymbol.name }}</span>
        </div>

        <div v-if="!previewCollapsed" class="preview-content">
          <!-- Loading state -->
          <div v-if="previewLoading" class="preview-loading">
            Loading...
          </div>

          <!-- Error state -->
          <div v-else-if="previewError" class="preview-error">
            {{ previewError }}
          </div>

          <!-- Not indexed -->
          <div v-else-if="previewData?.reason === 'not_indexed'" class="preview-not-indexed">
            {{ previewData.message }}
          </div>

          <!-- Not found -->
          <div v-else-if="previewData?.found === false" class="preview-not-found">
            <span>Symbol not found</span>
            <div v-if="previewData.similar_symbols?.length" class="similar-symbols">
              <span>Similar:</span>
              <button
                v-for="name in previewData.similar_symbols"
                :key="name"
                class="similar-btn"
                @click="loadPreview({ name, kind: 'variable', lineNumber: 0 })"
              >
                {{ name }}
              </button>
            </div>
          </div>

          <!-- Multiple matches -->
          <div v-else-if="previewData?.matches?.length" class="preview-matches">
            <div class="matches-label">{{ previewData.matches.length }} definitions found:</div>
            <div class="matches-list">
              <button
                v-for="(match, idx) in previewData.matches"
                :key="`${match.file_path}-${match.line_number}`"
                class="match-item"
                :class="{ 'is-selected': idx === selectedMatchIndex }"
                @click="handleSelectMatch(idx)"
              >
                <span class="match-kind">{{ match.kind }}</span>
                <span class="match-file">{{ formatFilePath(match.file_path) }}:{{ match.line_number }}</span>
              </button>
            </div>
            <button class="navigate-btn" @click="handleNavigateToSymbol()">
              Go to {{ previewData.matches[selectedMatchIndex]?.kind || 'definition' }}
            </button>
          </div>

          <!-- Single match - show details -->
          <template v-else-if="previewData?.found">
            <!-- Definition snippet -->
            <div v-if="previewData.definition_snippet?.length" class="preview-snippet">
              <pre><code v-for="(line, idx) in previewData.definition_snippet" :key="idx">{{ line }}
</code></pre>
            </div>

            <!-- Docstring -->
            <div v-if="previewData.docstring" class="preview-docstring">
              <span class="docstring-label">Docs:</span>
              <p>{{ previewData.docstring }}</p>
            </div>

            <!-- File location -->
            <div v-if="previewData.file_path" class="preview-location">
              <button class="location-link" @click="handleNavigateToSymbol()">
                📄 {{ formatFilePath(previewData.file_path) }}:{{ previewData.line_number }}
              </button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.symbol-outline {
  background: var(--bg-primary);
  border-top: 1px solid var(--border-color);
  font-size: 12px;
}

.outline-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-bottom: 1px solid var(--border-color);
}

.outline-toggle {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0;
  font-size: 10px;
  line-height: 1;
  width: 16px;
}

.outline-toggle:hover {
  color: var(--text-primary);
}

.outline-title {
  color: var(--text-primary);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.outline-count {
  color: var(--text-muted);
  font-size: 11px;
}

.outline-index {
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 3px;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 2px 6px;
  font-size: 11px;
  line-height: 1;
  transition: all 0.15s ease;
  margin-left: 4px;
}

.outline-index:hover:not(:disabled) {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: white;
}

.outline-index.is-indexing {
  opacity: 0.6;
  cursor: wait;
}

.outline-next {
  margin-left: auto;
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 3px;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 2px 6px;
  font-size: 11px;
  line-height: 1;
  transition: all 0.15s ease;
}

.outline-next:hover {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: white;
}

.outline-content {
  padding: 8px 12px;
  max-height: 300px;
  overflow-y: auto;
}

/* Custom scrollbar for outline content */
.outline-content::-webkit-scrollbar {
  width: 6px;
}

.outline-content::-webkit-scrollbar-track {
  background: transparent;
}

.outline-content::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.outline-content::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

.index-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fee2e2;
  color: #dc2626;
  padding: 4px 8px;
  border-radius: 4px;
  margin-bottom: 8px;
  font-size: 11px;
}

.error-dismiss {
  background: none;
  border: none;
  color: #dc2626;
  cursor: pointer;
  font-size: 14px;
  padding: 0 4px;
}

.no-symbols {
  color: var(--text-muted);
  font-style: italic;
  font-size: 11px;
}

.symbol-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.symbol-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 11px;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.symbol-tag:hover {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: white;
}

.symbol-tag:hover .symbol-icon,
.symbol-tag:hover .symbol-name,
.symbol-tag:hover .symbol-line {
  color: white;
}

.symbol-tag.is-active {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: white;
}

.symbol-tag.is-active .symbol-icon,
.symbol-tag.is-active .symbol-name,
.symbol-tag.is-active .symbol-line {
  color: white;
}

.symbol-icon {
  font-size: 10px;
  opacity: 0.8;
}

.symbol-name {
  font-family: monospace;
  color: var(--text-primary);
}

.symbol-line {
  color: var(--text-muted);
  font-size: 10px;
  margin-left: 2px;
}

/* Preview Panel */
.preview-panel {
  margin-top: 8px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  background: var(--bg-tertiary);
  cursor: pointer;
  user-select: none;
}

.preview-header:hover {
  background: var(--bg-secondary);
}

.preview-toggle {
  font-size: 8px;
  color: var(--text-muted);
}

.preview-title {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.preview-name {
  font-family: monospace;
  font-size: 11px;
  color: var(--text-primary);
  margin-left: auto;
}

.preview-content {
  padding: 8px;
  max-height: 200px;
  overflow-y: auto;
}

.preview-loading,
.preview-error,
.preview-not-indexed,
.preview-not-found {
  color: var(--text-muted);
  font-size: 11px;
  font-style: italic;
}

.preview-error {
  color: #dc2626;
}

.similar-symbols {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.similar-btn {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 3px;
  padding: 2px 6px;
  font-size: 10px;
  cursor: pointer;
  font-family: monospace;
}

.similar-btn:hover {
  background: var(--accent-color);
  color: white;
}

/* Preview snippet */
.preview-snippet {
  background: var(--bg-tertiary);
  border-radius: 4px;
  padding: 8px;
  margin-bottom: 8px;
  overflow-x: auto;
}

.preview-snippet pre {
  margin: 0;
  font-family: monospace;
  font-size: 11px;
  line-height: 1.4;
  color: var(--text-primary);
}

.preview-snippet code {
  background: none;
}

/* Preview docstring */
.preview-docstring {
  margin-bottom: 8px;
  font-size: 11px;
}

.docstring-label {
  font-weight: 600;
  color: var(--text-secondary);
  margin-right: 4px;
}

.preview-docstring p {
  margin: 4px 0 0 0;
  color: var(--text-primary);
  white-space: pre-wrap;
}

/* Preview location */
.preview-location {
  margin-top: 8px;
}

.location-link {
  background: none;
  border: none;
  color: var(--accent-color);
  cursor: pointer;
  font-size: 11px;
  padding: 0;
  text-decoration: underline;
}

.location-link:hover {
  color: var(--text-primary);
}

/* Multiple matches */
.preview-matches .matches-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.matches-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.match-item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  padding: 6px 8px;
  cursor: pointer;
  text-align: left;
  width: 100%;
}

.match-item:hover,
.match-item.is-selected {
  border-color: var(--accent-color);
  background: var(--bg-secondary);
}

.match-kind {
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
  min-width: 60px;
}

.match-file {
  font-family: monospace;
  font-size: 11px;
  color: var(--text-primary);
}

.navigate-btn {
  background: var(--accent-color);
  border: none;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  font-size: 11px;
  padding: 6px 12px;
  width: 100%;
}

.navigate-btn:hover {
  opacity: 0.9;
}

/* Symbol type colors - default (light) theme */
.symbol-function {
  color: #795e26;
}

.symbol-class {
  color: #267f99;
}

.symbol-variable {
  color: #001080;
}

.symbol-import {
  color: #af00db;
}

.symbol-constant {
  color: #a31515;
}

.is-collapsed .outline-content {
  display: none;
}
</style>

<style>
/* Theme-specific symbol colors - must be non-scoped to access parent theme class */
/* Dark theme */
.theme-dark .symbol-outline .symbol-function {
  color: #dcdcaa;
}

.theme-dark .symbol-outline .symbol-class {
  color: #4ec9b0;
}

.theme-dark .symbol-outline .symbol-variable {
  color: #9cdcfe;
}

.theme-dark .symbol-outline .symbol-import {
  color: #c586c0;
}

.theme-dark .symbol-outline .symbol-constant {
  color: #ce9178;
}

/* Green theme */
.theme-green .symbol-outline .symbol-function {
  color: #2d5a3d;
}

.theme-green .symbol-outline .symbol-class {
  color: #1a5276;
}

.theme-green .symbol-outline .symbol-variable {
  color: #1e8449;
}

.theme-green .symbol-outline .symbol-import {
  color: #7b1fa2;
}

.theme-green .symbol-outline .symbol-constant {
  color: #bf360c;
}

/* Parchment theme */
.theme-parchment .symbol-outline .symbol-function {
  color: #8b6914;
}

.theme-parchment .symbol-outline .symbol-class {
  color: #1565c0;
}

.theme-parchment .symbol-outline .symbol-variable {
  color: #2e7d32;
}

.theme-parchment .symbol-outline .symbol-import {
  color: #7b1fa2;
}

.theme-parchment .symbol-outline .symbol-constant {
  color: #d84315;
}

/* Light theme */
.theme-light .symbol-outline .symbol-function {
  color: #795e26;
}

.theme-light .symbol-outline .symbol-class {
  color: #267f99;
}

.theme-light .symbol-outline .symbol-variable {
  color: #001080;
}

.theme-light .symbol-outline .symbol-import {
  color: #af00db;
}

.theme-light .symbol-outline .symbol-constant {
  color: #a31515;
}
</style>
```

- [ ] **Step 2: Commit the extended SymbolOutline component**

```bash
git add frontend/src/components/Monaco/SymbolOutline.vue
git commit -m "$(cat <<'EOF'
feat(frontend): extend SymbolOutline with preview panel and indexing

- Add Index button with async status polling
- Add preview panel showing definition, docstring, and location
- Support multiple symbol matches with selection
- Add navigation event for clicking file location

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 5: Frontend Integration with CodeReviewView

### Task 7: Integrate SymbolOutline with CodeReviewView

**Files:**
- Modify: `frontend/src/views/CodeReviewView.vue`

- [ ] **Step 1: Find the SymbolOutline usage and add required props and handler**

In `frontend/src/views/CodeReviewView.vue`, find the `<SymbolOutline>` component usage (around line 1875) and update it:

1. Add `taskId` prop (the `taskId` computed ref already exists at line 45)
2. Add `currentFilePath` prop (use `currentFile` which is the ref for the current file path)
3. Add `@navigate` handler

Current usage (around line 1875):

```vue
<SymbolOutline
  v-if="isSupportedFileType"
  :symbols="symbols"
  :collapsed="outlineCollapsed"
  class="flex-shrink-0"
  @select="handleSymbolSelect"
  @toggle="handleOutlineToggle"
/>
```

Update to:

```vue
<SymbolOutline
  v-if="isSupportedFileType"
  :symbols="symbols"
  :collapsed="outlineCollapsed"
  :task-id="taskId"
  :current-file-path="currentFile || ''"
  class="flex-shrink-0"
  @select="handleSymbolSelect"
  @toggle="handleOutlineToggle"
  @navigate="handleSymbolNavigate"
/>
```

- [ ] **Step 2: Add the navigation handler function**

Add this function in the script section (after the existing `handleSymbolSelect` function around line 782):

```typescript
async function handleSymbolNavigate(filePath: string, lineNumber: number) {
  // If the file is different from current, load it first
  if (currentFile.value !== filePath) {
    await loadFile(filePath, 'editor')
  }
  // Then navigate to the line after the file loads
  nextTick(() => {
    if (editorRef.value) {
      editorRef.value.goToLine(lineNumber)
    }
  })
}
```

Note: The `loadFile` function already exists at line 592 and handles all file loading logic including caching. The `editorRef.value.goToLine()` method already exists and is used by `handleSymbolSelect` at line 784.

- [ ] **Step 3: Verify taskId is available**

The `taskId` computed ref already exists at line 45:

```typescript
const taskId = computed(() => route.params.id as string)
```

No changes needed - just verify it exists.

- [ ] **Step 4: Commit CodeReviewView changes**

```bash
git add frontend/src/views/CodeReviewView.vue
git commit -m "$(cat <<'EOF'
feat(frontend): integrate symbol preview navigation in CodeReviewView

- Pass taskId and currentFilePath to SymbolOutline
- Handle navigate event to load files and jump to lines
- Reuse existing loadFile function and goToLine method

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 6: Testing and Final Verification

### Task 8: Manual testing checklist

- [ ] **Step 1: Verify ctags is installed**

```bash
ctags --version
# Should show "Universal Ctags"
```

If not installed:
```bash
sudo apt install universal-ctags
```

- [ ] **Step 2: Start the development servers**

```bash
./deploy.sh restart
```

- [ ] **Step 3: Test indexing flow**

1. Open a task in CodeReviewView
2. Click the "Index" button in the symbol outline
3. Verify indexing starts and shows progress
4. Wait for indexing to complete
5. Click "Index" again - should show "Using cached index"

- [ ] **Step 4: Test symbol preview**

1. Open a file with symbols (functions, classes)
2. Click on a symbol in the symbol outline
3. Verify preview panel appears with:
   - Definition snippet
   - Docstring (if present)
   - File path and line number
4. Click the file path link
5. Verify it navigates to the correct file and line

- [ ] **Step 5: Test multiple matches**

1. Find a symbol that exists in multiple files
2. Click on it
3. Verify multiple matches are shown
4. Click different matches to select
5. Click "Go to definition" button

- [ ] **Step 6: Test error cases**

1. Try indexing without ctags installed (uninstall temporarily)
2. Verify error message shows installation instructions
3. Reinstall ctags
4. Try to preview symbol without indexing first
5. Verify "not indexed" message appears

- [ ] **Step 7: Final commit with any fixes**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat: complete symbol preview implementation

Full implementation of symbol preview feature using universal-ctags:
- Async project indexing with progress tracking
- Cross-file symbol resolution
- Definition snippet, docstring, and signature display
- Multiple match disambiguation
- Navigation to symbol location

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Summary

This plan implements the symbol preview feature in 6 chunks:

1. **Chunk 1**: Backend CtagsService - core indexing and lookup logic
2. **Chunk 2**: Backend router and schemas - API endpoints
3. **Chunk 3**: Frontend API client - TypeScript interfaces and functions
4. **Chunk 4**: Extended SymbolOutline component - UI for preview
5. **Chunk 5**: CodeReviewView integration - connect all pieces
6. **Chunk 6**: Testing and verification

Each task produces self-contained, testable changes with clear commit points.
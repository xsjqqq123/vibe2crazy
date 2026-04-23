"""
CtagsService - Symbol indexing and lookup using universal-ctags.

This service provides:
- Async symbol indexing with job tracking
- Symbol lookup with definition extraction
- Support for multiple programming languages
- SQLite-based storage with incremental indexing
"""

import json
import logging
import os
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Status of an indexing job."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IndexJob:
    """Represents an indexing job."""
    job_id: str
    task_id: str
    worktree_path: str
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    indexed_files: int = 0
    indexed_symbols: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    suggestion: Optional[str] = None
    cached: bool = False
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the IndexJob to a dictionary for API serialization."""
        return {
            "job_id": self.job_id,
            "task_id": self.task_id,
            "worktree_path": self.worktree_path,
            "status": self.status.value if isinstance(self.status, JobStatus) else self.status,
            "progress": self.progress,
            "indexed_files": self.indexed_files,
            "indexed_symbols": self.indexed_symbols,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "suggestion": self.suggestion,
            "cached": self.cached,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class SymbolMatch:
    """Represents a symbol match from the database."""
    name: str
    file_path: str
    line_number: int
    kind: str
    signature: Optional[str] = None
    scope: Optional[str] = None
    pattern: Optional[str] = None
    is_header: bool = False  # True if from C/C++ header file


@dataclass
class SymbolDefinition:
    """Represents a symbol definition with extracted details."""
    found: bool
    name: Optional[str] = None
    kind: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    type_signature: Optional[str] = None
    signature_file_path: Optional[str] = None
    signature_line_number: Optional[int] = None
    docstring: Optional[str] = None
    definition_snippet: Optional[str] = None
    snippet_highlight_index: Optional[int] = None
    reason: Optional[str] = None
    message: Optional[str] = None
    similar_symbols: List[SymbolMatch] = field(default_factory=list)
    matches: List[SymbolMatch] = field(default_factory=list)


# Header file extensions for C/C++ (used for priority in symbol lookup)
HEADER_EXTENSIONS = {'.h', '.hpp', '.hxx', '.hh', '.h++', '.inc'}


def is_header_file(file_path: str) -> bool:
    """Check if a file is a C/C++ header file."""
    return Path(file_path).suffix.lower() in HEADER_EXTENSIONS


# SQLite schema for symbol storage
SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    mtime REAL NOT NULL,
    symbol_count INTEGER DEFAULT 0,
    indexed_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    kind TEXT NOT NULL,
    signature TEXT,
    scope TEXT,
    pattern TEXT,
    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_name_lower ON symbols(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_symbols_file_id ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_files_path ON files(file_path);
"""


class CtagsService:
    """Service for symbol indexing and lookup using universal-ctags."""

    # Languages supported by universal-ctags that we care about
    SUPPORTED_LANGUAGES = [
        "Python",
        "JavaScript",
        "TypeScript",
        "Vue",
        "Go",
        "Rust",
        "C",
        "C++",
    ]

    # Patterns to exclude from indexing
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
        ".mypy_cache",
        ".pytest_cache",
        ".idea",
        ".vscode",
        "*.pyc",
        "*.pyo",
        "target",
        "Cargo.lock",
        "package-lock.json",
        "yarn.lock",
        ".tags",
    ]

    # Maximum number of lines to extract for a definition snippet
    MAX_SNIPPET_LINES = 15

    # Maximum file size to process (500KB)
    MAX_FILE_SIZE = 500 * 1024

    # Batch size for database inserts
    BATCH_SIZE = 100

    def __init__(self, projects_dir: str):
        """
        Initialize the CtagsService.

        Args:
            projects_dir: Base directory for project worktrees
        """
        self.projects_dir = Path(projects_dir).resolve()
        self._jobs: Dict[str, IndexJob] = {}
        self._lock = threading.Lock()
        self._active_indexing: Dict[str, str] = {}  # worktree_path -> job_id

    def _validate_worktree_path(self, worktree_path: str) -> Path:
        """
        Validate worktree_path for security and existence.

        Args:
            worktree_path: The worktree path to validate

        Returns:
            The validated and resolved Path object

        Raises:
            ValueError: If worktree_path is invalid or doesn't exist
        """
        if not worktree_path:
            raise ValueError("worktree_path is required")

        resolved_path = Path(worktree_path).resolve()

        # Check for directory traversal attempts
        if ".." in worktree_path:
            logger.warning(f"Path traversal attempt in worktree_path: {worktree_path}")
            raise ValueError(f"Invalid worktree_path: {worktree_path}")

        # Verify the path exists
        if not resolved_path.exists():
            raise ValueError(f"Worktree path does not exist: {worktree_path}")

        if not resolved_path.is_dir():
            raise ValueError(f"Worktree path is not a directory: {worktree_path}")

        return resolved_path

    def _get_tags_dir(self, worktree_path: str) -> Path:
        """
        Get the tags directory path within the worktree.

        Args:
            worktree_path: The worktree root path

        Returns:
            Path to the .tags directory within the worktree
        """
        return Path(worktree_path) / ".tags"

    def _get_db_file(self, worktree_path: str) -> Path:
        """
        Get the SQLite database file path.

        Args:
            worktree_path: The worktree root path

        Returns:
            Path to the symbols.db file
        """
        return self._get_tags_dir(worktree_path) / "symbols.db"

    def _get_metadata_file(self, worktree_path: str) -> Path:
        """
        Get the metadata JSON file path within the worktree.

        Args:
            worktree_path: The worktree root path

        Returns:
            Path to the metadata.json file
        """
        return self._get_tags_dir(worktree_path) / "metadata.json"

    def _ensure_gitignore_entry(self, worktree_path: str, entry: str) -> None:
        """
        Ensure an entry exists in the worktree's .gitignore file.

        This guarantees that the specified entry is present in .gitignore,
        creating the file if necessary. Called during indexing to prevent
        the .tags directory from being tracked by Git.

        Args:
            worktree_path: The worktree root path
            entry: The entry to ensure exists in .gitignore (e.g., ".tags/")
        """
        gitignore_path = Path(worktree_path) / ".gitignore"

        # Check if .gitignore exists
        if gitignore_path.exists():
            content = gitignore_path.read_text()

            # Check if entry already exists (check for entry as a standalone line)
            lines = content.splitlines()
            if entry in lines:
                logger.debug(f"Entry '{entry}' already in .gitignore")
                return

            # Add entry - ensure there's a newline before it if file doesn't end with one
            if content and not content.endswith('\n'):
                content += '\n'
            content += entry + '\n'
            gitignore_path.write_text(content)
            logger.info(f"Added '{entry}' to existing .gitignore")
        else:
            # Create .gitignore with the entry
            gitignore_path.write_text(entry + '\n')
            logger.info(f"Created .gitignore with '{entry}' entry")

    def _init_database(self, db_path: Path) -> None:
        """
        Initialize the SQLite database with schema.

        Args:
            db_path: Path to the database file
        """
        conn = sqlite3.connect(str(db_path))
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _get_indexed_files(self, db_path: Path) -> Dict[str, Tuple[float, int]]:
        """
        Get list of indexed files with their mtimes and file IDs.

        Args:
            db_path: Path to the database file

        Returns:
            Dictionary mapping file_path to (mtime, file_id)
        """
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT file_path, mtime, id FROM files")
            result = {}
            for row in cursor.fetchall():
                result[row[0]] = (row[1], row[2])
            return result
        finally:
            conn.close()

    def _delete_file_symbols(self, db_path: Path, file_ids: List[int]) -> None:
        """
        Delete symbols for files by file_id.

        Args:
            db_path: Path to the database file
            file_ids: List of file IDs to delete
        """
        if not file_ids:
            return

        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(file_ids))
            cursor.execute(f"DELETE FROM symbols WHERE file_id IN ({placeholders})", file_ids)
            cursor.execute(f"DELETE FROM files WHERE id IN ({placeholders})", file_ids)
            conn.commit()
        finally:
            conn.close()

    def _insert_symbols_batch(
        self,
        db_path: Path,
        file_path: str,
        mtime: float,
        symbols: List[Dict[str, Any]]
    ) -> int:
        """
        Insert symbols for a file into the database.

        Args:
            db_path: Path to the database file
            file_path: Path to the source file
            mtime: Modification time of the file
            symbols: List of symbol dictionaries from ctags

        Returns:
            Number of symbols inserted
        """
        if not symbols:
            return 0

        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()

            # Insert or update file record
            cursor.execute(
                """INSERT OR REPLACE INTO files (file_path, mtime, symbol_count, indexed_at)
                   VALUES (?, ?, ?, ?)""",
                (file_path, mtime, len(symbols), time.time())
            )

            # Get file_id
            cursor.execute("SELECT id FROM files WHERE file_path = ?", (file_path,))
            file_id = cursor.fetchone()[0]

            # Delete old symbols for this file
            cursor.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))

            # Insert symbols
            for symbol in symbols:
                cursor.execute(
                    """INSERT INTO symbols (name, file_path, line_number, kind, signature, scope, pattern, file_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        symbol.get("name", ""),
                        file_path,
                        symbol.get("line", 0),
                        symbol.get("kind", "unknown"),
                        symbol.get("signature"),
                        symbol.get("scope"),
                        symbol.get("pattern"),
                        file_id
                    )
                )

            conn.commit()
            return len(symbols)
        finally:
            conn.close()

    def _should_exclude(self, name: str) -> bool:
        """
        Check if a directory/file should be excluded from indexing.

        Args:
            name: Directory or file name

        Returns:
            True if should be excluded
        """
        for pattern in self.EXCLUDE_PATTERNS:
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    return True
            elif name == pattern:
                return True
        return False

    def check_ctags_installed(self) -> bool:
        """
        Check if universal-ctags is installed and available.

        Note: This method checks every time without caching,
        to detect runtime changes in ctags availability.

        Returns:
            True if ctags is installed, False otherwise
        """
        try:
            result = subprocess.run(
                ["ctags", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            # Check if it's universal-ctags
            if result.returncode == 0 and "Universal Ctags" in result.stdout:
                logger.info("Universal ctags is installed and available")
                return True
            else:
                logger.warning("ctags is installed but not Universal Ctags")
                return False
        except FileNotFoundError:
            logger.warning("ctags is not installed")
            return False
        except subprocess.TimeoutExpired:
            logger.error("ctags version check timed out")
            return False
        except Exception as e:
            logger.error(f"Error checking ctags installation: {e}")
            return False

    def start_index_job(self, task_id: str, worktree_path: str, force: bool = False, extra_paths: Optional[List[str]] = None) -> IndexJob:
        """
        Start an async indexing job for a worktree.

        Args:
            task_id: The task ID for tracking
            worktree_path: The path to the worktree to index (tags will be stored here)
            force: Force reindexing even if cache exists

        Returns:
            IndexJob instance with job details

        Raises:
            ValueError: If worktree_path is invalid
        """
        # Validate worktree_path for security
        worktree_dir = self._validate_worktree_path(worktree_path)

        job_id = str(uuid.uuid4())

        # Check if ctags is installed
        if not self.check_ctags_installed():
            job = IndexJob(
                job_id=job_id,
                task_id=task_id,
                worktree_path=worktree_path,
                status=JobStatus.FAILED,
                error="universal-ctags is not installed",
                suggestion="Install universal-ctags: brew install universal-ctags (macOS) or apt install universal-ctags (Ubuntu)"
            )
            self._jobs[job_id] = job
            return job

        # Check for cached database (symbols.db)
        db_file = self._get_db_file(worktree_path)
        metadata_file = self._get_metadata_file(worktree_path)

        # Check if an indexing job is already running for this worktree
        if worktree_path in self._active_indexing:
            existing_job_id = self._active_indexing[worktree_path]
            existing_job = self._jobs.get(existing_job_id)
            if existing_job and existing_job.status in (JobStatus.PENDING, JobStatus.IN_PROGRESS):
                logger.info(f"Indexing already in progress for {worktree_path}, returning existing job")
                return existing_job

        # Create job
        job = IndexJob(
            job_id=job_id,
            task_id=task_id,
            worktree_path=worktree_path,
            status=JobStatus.PENDING
        )
        self._jobs[job_id] = job

        # Mark this worktree as having an active indexing job
        self._active_indexing[worktree_path] = job_id

        # Start background thread
        thread = threading.Thread(
            target=self._run_indexing,
            args=(job_id, worktree_path, force, extra_paths),
            daemon=True
        )
        thread.start()

        return job

    def _get_symbol_count(self, db_path: Path) -> int:
        """Get total symbol count from database."""
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM symbols")
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def _get_file_count(self, db_path: Path) -> int:
        """Get total file count from database."""
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM files")
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def _run_indexing(self, job_id: str, worktree_path: str, force: bool = False, extra_paths: Optional[List[str]] = None) -> None:
        """
        Background thread for running the indexing job with incremental support.

        Args:
            job_id: The job ID
            worktree_path: The path to the worktree to index
            force: If True, clear the database and re-index all files
            extra_paths: Optional list of additional paths to index (e.g., /usr/include)
        """
        job = self._jobs.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        job.status = JobStatus.IN_PROGRESS
        job.started_at = time.time()

        try:
            # Validate and resolve worktree path
            project_dir = self._validate_worktree_path(worktree_path)

            # Create tags directory within the worktree
            tags_dir = self._get_tags_dir(worktree_path)
            tags_dir.mkdir(parents=True, exist_ok=True)

            # Ensure .tags/ is in .gitignore to prevent tracking the index database
            self._ensure_gitignore_entry(worktree_path, ".tags/")

            # Initialize database
            db_file = self._get_db_file(worktree_path)

            # If force is True, delete existing database to re-index from scratch
            if force and db_file.exists():
                logger.info(f"Force re-index: removing existing database {db_file}")
                db_file.unlink()

            if not db_file.exists():
                self._init_database(db_file)
                logger.info(f"Created new database at {db_file}")

            # Get existing indexed files
            indexed_files = self._get_indexed_files(db_file)
            logger.info(f"Found {len(indexed_files)} previously indexed files")

            # Track stats
            total_symbols = 0
            total_files = 0
            new_files = 0
            modified_files = 0
            deleted_files = 0

            # Process directory by directory for memory efficiency
            files_to_delete = []
            files_to_index = []

            for root, dirs, files in os.walk(worktree_path):
                # Filter excluded directories in-place
                dirs[:] = [d for d in dirs if not self._should_exclude(d)]

                for f in files:
                    # Skip excluded files
                    if self._should_exclude(f):
                        continue

                    file_path = os.path.join(root, f)
                    rel_path = os.path.relpath(file_path, worktree_path)

                    # Skip files in .tags directory
                    if rel_path.startswith(".tags"):
                        continue

                    try:
                        current_mtime = os.path.getmtime(file_path)

                        if file_path in indexed_files:
                            indexed_mtime, file_id = indexed_files[file_path]
                            if current_mtime > indexed_mtime:
                                # File modified, needs re-indexing
                                files_to_delete.append(file_id)
                                files_to_index.append((file_path, current_mtime))
                                modified_files += 1
                            # Remove from indexed_files to track what's still valid
                            del indexed_files[file_path]
                        else:
                            # New file
                            files_to_index.append((file_path, current_mtime))
                            new_files += 1
                    except OSError as e:
                        logger.warning(f"Error accessing file {file_path}: {e}")
                        continue

            # Remaining files in indexed_files were deleted
            for file_path, (_, file_id) in indexed_files.items():
                files_to_delete.append(file_id)
                deleted_files += 1

            # Delete symbols for removed/modified files
            if files_to_delete:
                self._delete_file_symbols(db_file, files_to_delete)
                logger.info(f"Deleted {len(files_to_delete)} files from index")

            # Index new and modified files
            if files_to_index:
                total_symbols = self._index_files(db_file, files_to_index, worktree_path)
                total_files = len(files_to_index)

            # Index extra paths if provided
            extra_symbols = 0
            extra_files = 0
            if extra_paths:
                logger.info(f"Indexing extra paths: {extra_paths}")
                extra_symbols, extra_files = self._index_extra_paths(db_file, extra_paths)
                total_symbols += extra_symbols
                total_files += extra_files

            # Update metadata
            metadata = {
                "worktree_path": worktree_path,
                "indexed_at": time.time(),
                "total_symbols": self._get_symbol_count(db_file),
                "total_files": self._get_file_count(db_file),
                "new_files": new_files,
                "modified_files": modified_files,
                "deleted_files": deleted_files,
                "languages": self.SUPPORTED_LANGUAGES,
                "exclude_patterns": self.EXCLUDE_PATTERNS,
            }
            metadata_file = self._get_metadata_file(worktree_path)
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            # Update job
            job.status = JobStatus.COMPLETED
            job.indexed_files = total_files
            job.indexed_symbols = total_symbols
            job.completed_at = time.time()
            job.duration_seconds = job.completed_at - job.started_at

            logger.info(
                f"Indexing completed for worktree {worktree_path}: "
                f"{new_files} new, {modified_files} modified, {deleted_files} deleted, "
                f"{total_symbols} symbols"
            )

        except subprocess.TimeoutExpired:
            job.status = JobStatus.FAILED
            job.error = "Indexing timed out (5 minutes)"
            job.suggestion = "Try indexing a smaller project or reduce exclude patterns"
            logger.error(f"Indexing timed out for worktree {worktree_path}")

        except FileNotFoundError as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.suggestion = "Check that the worktree directory exists"
            logger.error(f"Worktree directory not found: {e}")

        except RuntimeError as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.suggestion = "Check ctags installation and permissions"
            logger.error(f"ctags failed: {e}")

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.suggestion = "Check logs for details"
            logger.exception(f"Unexpected error during indexing: {e}")

        finally:
            job.completed_at = time.time()
            if job.started_at:
                job.duration_seconds = job.completed_at - job.started_at
            # Clean up active indexing tracking
            self._active_indexing.pop(worktree_path, None)

    def _index_files(
        self,
        db_path: Path,
        files_to_index: List[Tuple[str, float]],
        worktree_path: str
    ) -> int:
        """
        Index a list of files and store symbols in database.

        Args:
            db_path: Path to the database
            files_to_index: List of (file_path, mtime) tuples
            worktree_path: The worktree root path

        Returns:
            Total number of symbols indexed
        """
        if not files_to_index:
            return 0

        total_symbols = 0

        # Build exclude arguments
        exclude_args = []
        for pattern in self.EXCLUDE_PATTERNS:
            exclude_args.extend(["--exclude", pattern])

        languages = ",".join(self.SUPPORTED_LANGUAGES)

        # Process files in batches for memory efficiency
        batch_size = 50  # Number of files to process per ctags invocation
        for i in range(0, len(files_to_index), batch_size):
            batch = files_to_index[i:i + batch_size]
            file_paths = [f[0] for f in batch]
            file_mtimes = {f[0]: f[1] for f in batch}

            # Run ctags on this batch
            ctags_cmd = [
                "ctags",
                "--fields=+neKSt",
                "--extras=+q",
                "--kinds-C=+p",       # Include function prototypes for C
                "--kinds-C++=+p",     # Include function prototypes for C++
                "--output-format=json",
                f"--languages={languages}",
                *exclude_args,
                *file_paths
            ]

            logger.debug(f"Running ctags on {len(file_paths)} files")

            result = subprocess.run(
                ctags_cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=worktree_path
            )

            # Parse and store symbols per file
            symbols_by_file: Dict[str, List[Dict[str, Any]]] = {}
            for line in result.stdout.strip().split("\n"):
                if line:
                    try:
                        tag = json.loads(line)
                        file_path = tag.get("path", "")
                        if file_path:
                            if file_path not in symbols_by_file:
                                symbols_by_file[file_path] = []
                            symbols_by_file[file_path].append(tag)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse tag line: {e}")
                        continue

            # Insert into database
            for file_path, symbols in symbols_by_file.items():
                mtime = file_mtimes.get(file_path, time.time())
                count = self._insert_symbols_batch(db_path, file_path, mtime, symbols)
                total_symbols += count

        return total_symbols

    def _index_extra_paths(self, db_path: Path, extra_paths: List[str]) -> Tuple[int, int]:
        """
        Index additional external paths (e.g., /usr/include).

        Args:
            db_path: Path to the database
            extra_paths: List of directory paths to index

        Returns:
            Tuple of (total_symbols, total_files)
        """
        total_symbols = 0
        total_files = 0

        for path in extra_paths:
            path_obj = Path(path)
            if not path_obj.exists() or not path_obj.is_dir():
                logger.warning(f"Extra path does not exist or is not a directory: {path}")
                continue

            logger.info(f"Indexing extra path: {path}")

            # Collect files to index from this path
            files_to_index = []
            for root, dirs, files in os.walk(path):
                # Filter excluded directories in-place
                dirs[:] = [d for d in dirs if not self._should_exclude(d)]

                for f in files:
                    # Skip excluded files
                    if self._should_exclude(f):
                        continue

                    file_path = os.path.join(root, f)
                    try:
                        current_mtime = os.path.getmtime(file_path)
                        files_to_index.append((file_path, current_mtime))
                    except OSError as e:
                        logger.warning(f"Error accessing file {file_path}: {e}")
                        continue

            # Index these files
            if files_to_index:
                symbols = self._index_files(db_path, files_to_index, path)
                total_symbols += symbols
                total_files += len(files_to_index)
                logger.info(f"Indexed {len(files_to_index)} files, {symbols} symbols from {path}")

        return total_symbols, total_files

    def get_job_status(self, job_id: str) -> Optional[IndexJob]:
        """
        Get the status of an indexing job.

        Args:
            job_id: The job ID

        Returns:
            IndexJob if found, None otherwise
        """
        return self._jobs.get(job_id)

    def find_symbol(
        self,
        worktree_path: str,
        symbol_name: str,
        context_file: Optional[str] = None
    ) -> SymbolDefinition:
        """
        Find a symbol definition in the worktree using SQLite database.

        Args:
            worktree_path: The path to the worktree (tags are stored here)
            symbol_name: The symbol name to find
            context_file: Optional context file for disambiguation

        Returns:
            SymbolDefinition with match details

        Raises:
            ValueError: If worktree_path is invalid
        """
        # Validate worktree_path for security
        self._validate_worktree_path(worktree_path)

        # Check database exists
        db_file = self._get_db_file(worktree_path)
        if not db_file.exists():
            return SymbolDefinition(
                found=False,
                reason="No symbols database found for project. Run indexing first."
            )

        # Query database
        exact_matches, similar_symbols = self._find_symbol_in_db(db_file, symbol_name)

        # Resolve worktree path for converting absolute paths to relative
        worktree_dir = Path(worktree_path).resolve() if worktree_path else None

        def to_relative_path(absolute_path: str) -> str:
            """Convert absolute path to relative path within worktree."""
            if not worktree_dir:
                return absolute_path
            try:
                abs_path = Path(absolute_path).resolve()
                return str(abs_path.relative_to(worktree_dir))
            except ValueError:
                # Path is not within worktree, return as-is
                return absolute_path

        # Convert database results to SymbolMatch objects
        exact_match_objects = [
            SymbolMatch(
                name=m["name"],
                file_path=to_relative_path(m["file_path"]),
                line_number=m["line_number"],
                kind=m["kind"],
                signature=m.get("signature"),
                scope=m.get("scope"),
                pattern=m.get("pattern"),
                is_header=is_header_file(m["file_path"])
            )
            for m in exact_matches
        ]

        similar_match_objects = [
            SymbolMatch(
                name=m["name"],
                file_path=to_relative_path(m["file_path"]),
                line_number=m["line_number"],
                kind=m["kind"],
                signature=m.get("signature"),
                scope=m.get("scope"),
                pattern=m.get("pattern"),
                is_header=is_header_file(m["file_path"])
            )
            for m in similar_symbols
            if m["name"] != symbol_name  # Exclude exact matches from similar
        ]

        # If no exact matches found
        if not exact_match_objects:
            return SymbolDefinition(
                found=False,
                name=symbol_name,
                reason=f"Symbol '{symbol_name}' not found in project",
                similar_symbols=similar_match_objects[:10]
            )

        # Calculate directory distance for priority sorting
        def get_directory_distance(context_dir: str, match_dir: str) -> int:
            """
            Calculate the directory distance between context file and match file.

            Returns:
                0 = same directory
                1 = sibling directories (same parent)
                2 = cousin directories (same grandparent)
                ...
                999 = no common path
            """
            if not context_dir or not match_dir:
                return 999

            context_parts = Path(context_dir).parts
            match_parts = Path(match_dir).parts

            # Count common prefix parts
            common_depth = 0
            for c, m in zip(context_parts, match_parts):
                if c == m:
                    common_depth += 1
                else:
                    break

            # If no common path, return large number
            if common_depth == 0:
                return 999

            # Distance = levels up from common ancestor
            # Same directory: context_depth == match_depth == common_depth
            context_depth = len(context_parts)
            distance = context_depth - common_depth
            return distance

        # Get directory of context file for priority sorting
        context_dir = str(Path(context_file).parent) if context_file else None

        def sort_key(match: SymbolMatch) -> Tuple[int, int]:
            # First sort key: directory distance (lower = closer = higher priority)
            match_dir = str(Path(match.file_path).parent)
            dir_distance = get_directory_distance(context_dir, match_dir)

            # Second sort key: type priority
            if match.kind == "prototype":
                type_priority = 0
            elif match.is_header:
                type_priority = 1
            else:
                type_priority = 2

            return (dir_distance, type_priority)

        exact_match_objects.sort(key=sort_key)

        # Use first match directly (prototypes will be first after sorting)
        best_match = exact_match_objects[0]

        # Extract docstring and signature from the match
        best_match_absolute_path = best_match.file_path
        if worktree_dir and not Path(best_match.file_path).is_absolute():
            best_match_absolute_path = str(worktree_dir / best_match.file_path)

        docstring_details = self._extract_docstring_and_signature(
            best_match_absolute_path,
            best_match.line_number,
            best_match.file_path
        )

        # Extract code snippet
        function_kinds = {"function", "method"}  # Only actual implementations, not prototypes
        snippet = None
        snippet_highlight_index = None

        if best_match.kind in function_kinds:
            # For functions/methods, extract complete function body
            snippet = self._extract_function_body(
                best_match_absolute_path,
                best_match.line_number,
                worktree_path
            )
        else:
            # For non-function symbols, extract context snippet
            context_result = self._extract_context_snippet(
                best_match_absolute_path,
                best_match.line_number,
                context_lines=5,
                worktree_path=worktree_path
            )
            if context_result:
                snippet = context_result[0]
                snippet_highlight_index = context_result[1]

        return SymbolDefinition(
            found=True,
            name=best_match.name,
            kind=best_match.kind,
            file_path=best_match.file_path,
            line_number=best_match.line_number,
            type_signature=docstring_details.get("signature") or best_match.signature,
            signature_file_path=best_match.file_path,
            signature_line_number=best_match.line_number,
            docstring=docstring_details.get("docstring"),
            definition_snippet=snippet,
            snippet_highlight_index=snippet_highlight_index,
            matches=exact_match_objects
        )

    def get_symbol_at_location(
        self,
        worktree_path: str,
        file_path: str,
        line_number: int
    ) -> SymbolDefinition:
        """
        Get symbol details at a specific file location.

        Args:
            worktree_path: The path to the worktree (tags are stored here)
            file_path: The file path containing the symbol (relative to worktree)
            line_number: The exact line number of the symbol

        Returns:
            SymbolDefinition with symbol details at that exact location
        """
        # Validate worktree_path for security
        self._validate_worktree_path(worktree_path)

        # Check database exists
        db_file = self._get_db_file(worktree_path)
        if not db_file.exists():
            return SymbolDefinition(
                found=False,
                reason="No symbols database found for project. Run indexing first."
            )

        # Resolve paths
        worktree_dir = Path(worktree_path).resolve()

        # Build absolute path for the file
        if Path(file_path).is_absolute():
            absolute_file_path = file_path
        else:
            absolute_file_path = str(worktree_dir / file_path)

        # Query database for symbol at this exact location
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT name, file_path, line_number, kind, signature, scope, pattern FROM symbols WHERE file_path = ? AND line_number = ?",
                (absolute_file_path, line_number)
            )
            row = cursor.fetchone()

            if not row:
                return SymbolDefinition(
                    found=False,
                    reason=f"No symbol found at {file_path}:{line_number}"
                )

            symbol_data = dict(row)

        finally:
            conn.close()

        # Convert to relative path for frontend
        try:
            rel_file_path = str(Path(symbol_data["file_path"]).relative_to(worktree_dir))
        except ValueError:
            rel_file_path = symbol_data["file_path"]

        name = symbol_data["name"]
        kind = symbol_data["kind"]

        # Extract docstring and signature
        docstring_details = self._extract_docstring_and_signature(
            absolute_file_path,
            line_number,
            rel_file_path
        )

        # Extract code snippet
        function_kinds = {"function", "method"}  # Only actual implementations, not prototypes
        snippet = None
        snippet_highlight_index = None

        if kind in function_kinds:
            # For functions/methods, extract complete function body
            snippet = self._extract_function_body(
                absolute_file_path,
                line_number,
                worktree_path
            )
        else:
            # For non-function symbols, extract context snippet
            context_result = self._extract_context_snippet(
                absolute_file_path,
                line_number,
                context_lines=5,
                worktree_path=worktree_path
            )
            if context_result:
                snippet = context_result[0]
                snippet_highlight_index = context_result[1]

        return SymbolDefinition(
            found=True,
            name=name,
            kind=kind,
            file_path=rel_file_path,
            line_number=line_number,
            type_signature=docstring_details.get("signature") or symbol_data.get("signature"),
            signature_file_path=rel_file_path,
            signature_line_number=line_number,
            docstring=docstring_details.get("docstring"),
            definition_snippet=snippet,
            snippet_highlight_index=snippet_highlight_index
        )

    def _find_symbol_in_db(self, db_path: Path, symbol_name: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Query symbols from SQLite database.

        Args:
            db_path: Path to the database file
            symbol_name: Symbol name to search for

        Returns:
            Tuple of (exact_matches, similar_symbols)
        """
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Exact match
            cursor.execute(
                "SELECT name, file_path, line_number, kind, signature, scope, pattern FROM symbols WHERE name = ?",
                (symbol_name,)
            )
            exact_matches = [dict(row) for row in cursor.fetchall()]

            # Fuzzy match (case-insensitive substring)
            cursor.execute(
                "SELECT name, file_path, line_number, kind, signature, scope, pattern FROM symbols WHERE name LIKE ? LIMIT 20",
                (f"%{symbol_name}%",)
            )
            similar = [dict(row) for row in cursor.fetchall()]

            return exact_matches, similar
        finally:
            conn.close()

    def _extract_definition_details(
        self,
        file_path: str,
        line_number: int,
        kind: str,
        worktree_path: Optional[str] = None
    ) -> Dict[str, Optional[str]]:
        """
        Extract definition snippet, docstring, and signature from a file.

        Args:
            file_path: Path to the source file
            line_number: Line number of the symbol
            kind: Kind of the symbol
            worktree_path: Optional path to the worktree for path validation

        Returns:
            Dictionary with snippet, docstring, and signature
        """
        result = {
            "snippet": None,
            "docstring": None,
            "signature": None
        }

        try:
            # Check file size
            if os.path.getsize(file_path) > self.MAX_FILE_SIZE:
                logger.warning(f"File too large to extract definition: {file_path}")
                return result

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            if not lines or line_number < 1 or line_number > len(lines):
                return result

            # Convert to 0-indexed
            start_idx = line_number - 1

            # Extract snippet
            snippet_end = self._find_definition_end(lines, start_idx, start_idx + self.MAX_SNIPPET_LINES)
            snippet_lines = lines[start_idx:snippet_end]
            result["snippet"] = "".join(snippet_lines).strip()

            # Extract docstring
            result["docstring"] = self._extract_docstring(lines, start_idx, file_path)

            # Extract signature
            result["signature"] = self._extract_signature(lines[start_idx], file_path)

            return result

        except Exception as e:
            logger.error(f"Failed to extract definition details: {e}")
            return result

    def _extract_docstring_and_signature(
        self,
        file_path: str,
        line_number: int,
        relative_file_path: str
    ) -> Dict[str, Optional[str]]:
        """
        Extract docstring and signature from a file (typically a header file).

        Args:
            file_path: Absolute path to the source file
            line_number: Line number of the symbol
            relative_file_path: Relative file path (for language detection)

        Returns:
            Dictionary with docstring and signature
        """
        result = {
            "docstring": None,
            "signature": None
        }

        try:
            # Check file size
            if os.path.getsize(file_path) > self.MAX_FILE_SIZE:
                logger.warning(f"File too large to extract definition: {file_path}")
                return result

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            if not lines or line_number < 1 or line_number > len(lines):
                return result

            # Convert to 0-indexed
            start_idx = line_number - 1

            # Extract docstring
            result["docstring"] = self._extract_docstring(lines, start_idx, relative_file_path)

            # Extract signature
            result["signature"] = self._extract_signature(lines[start_idx], relative_file_path)

            return result

        except Exception as e:
            logger.error(f"Failed to extract docstring and signature: {e}")
            return result

    def _find_signature_start(
        self,
        lines: List[str],
        start_idx: int,
        file_path: str
    ) -> int:
        """
        Find the start of a function signature for C/C++ files.

        For multi-line declarations like:
            struct mosquitto *
            mosquitto_new(const char *id, ...)
        ctags reports the line with the function name, but we need to
        include the return type from previous lines.

        Args:
            lines: All lines in the file
            start_idx: Starting line index (0-indexed) - where ctags found the function name
            file_path: Path to the file (for language detection)

        Returns:
            Adjusted start index including return type lines
        """
        # Only applies to C/C++ files
        if not file_path.endswith(('.c', '.cpp', '.h', '.hpp')):
            return start_idx

        # Look backwards for the start of the signature
        # A line is part of the signature if it looks like a return type
        # (doesn't end with ';' or contain '{' or start with '#')
        current_idx = start_idx
        while current_idx > 0:
            prev_line = lines[current_idx - 1].strip()

            # Skip empty lines
            if not prev_line:
                current_idx -= 1
                continue

            # Stop if line ends with semicolon (previous statement)
            if prev_line.endswith(';'):
                break

            # Stop if line contains opening brace (previous function)
            if '{' in prev_line:
                break

            # Stop if line is a preprocessor directive
            if prev_line.startswith('#'):
                break

            # Stop if line looks like a complete statement
            if prev_line.endswith('}'):
                break

            # Stop if line is a comment (C-style)
            # - Line starts with /* (start of comment block)
            # - Line ends with */ (end of comment block)
            # - Line starts with * and looks like comment content
            if prev_line.startswith('/*') or prev_line.endswith('*/'):
                break
            if prev_line.startswith('*') and not prev_line.startswith('*('):
                # Likely a comment line like " * comment text"
                # But not a pointer dereference like "*(ptr)"
                break

            # This line appears to be part of the signature (return type)
            current_idx -= 1

        return current_idx

    def _find_comment_start(
        self,
        lines: List[str],
        func_start_idx: int
    ) -> int:
        """
        Find the start of comments/docstrings preceding a function.

        Args:
            lines: All lines in the file
            func_start_idx: Starting line index of the function (0-indexed)

        Returns:
            Index of the first line of the preceding comment block,
            or func_start_idx if no comment found.
        """
        # Look backwards from function start
        current_idx = func_start_idx - 1

        # Skip empty lines first
        while current_idx >= 0 and not lines[current_idx].strip():
            current_idx -= 1

        if current_idx < 0:
            return func_start_idx

        # Check if current line is a comment
        line = lines[current_idx].strip()

        # Helper to check if a line is a comment
        def is_comment_line(l: str) -> bool:
            return (
                l.startswith('#') or           # Python comment
                l.startswith('//') or          # C/C++/JS single-line comment
                l.startswith('/*') or          # C/C++ block comment start
                l.endswith('*/') or            # C/C++ block comment end
                (l.startswith('*') and not l.startswith('*(')) or  # Block comment content (not pointer)
                l.startswith('"""') or         # Python docstring
                l.startswith("'''") or         # Python docstring
                l.startswith('@')              # Decorator/annotation
            )

        if not is_comment_line(line):
            return func_start_idx

        # Found a comment, find where it starts
        comment_end_idx = current_idx

        # Walk backwards to find comment start
        while current_idx >= 0:
            line = lines[current_idx].strip()

            if not line:
                # Empty line - check if next non-empty is still a comment
                current_idx -= 1
                continue

            # Check for comment markers
            if line.startswith('#'):
                current_idx -= 1
                continue
            elif line.startswith('//'):
                current_idx -= 1
                continue
            elif line.startswith('"""') or line.startswith("'''"):
                # Python docstring - check if it's single line or start of multi-line
                if line.count('"""') >= 2 or line.count("'''") >= 2:
                    # Single line docstring
                    return current_idx
                else:
                    # Start of multi-line docstring
                    current_idx -= 1
                    continue
            elif line.startswith('/*'):
                # Start of C-style block comment
                return current_idx
            elif line.startswith('*') and not line.startswith('*('):
                # Inside block comment
                current_idx -= 1
                continue
            elif line.endswith('*/'):
                # End of C-style block comment - need to find its start
                current_idx -= 1
                continue
            elif line.startswith('@'):
                # Decorator/annotation - continue looking
                current_idx -= 1
                continue
            else:
                # Not a comment, stop
                break

        return current_idx + 1 if current_idx < comment_end_idx else func_start_idx

    def _extract_function_body(
        self,
        file_path: str,
        line_number: int,
        worktree_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Extract complete function body (no line limit for functions).

        Args:
            file_path: Path to the source file
            line_number: Line number of the function
            worktree_path: Optional path to the worktree for path validation

        Returns:
            Complete function body as string, or None if extraction fails
        """
        try:
            # Check file size
            if os.path.getsize(file_path) > self.MAX_FILE_SIZE:
                logger.warning(f"File too large to extract function body: {file_path}")
                return None

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            if not lines or line_number < 1 or line_number > len(lines):
                return None

            # Convert to 0-indexed
            start_idx = line_number - 1

            # For C/C++ files, find the actual signature start (may include return type)
            if file_path.endswith(('.c', '.cpp', '.h', '.hpp')):
                start_idx = self._find_signature_start(lines, start_idx, file_path)

            # Find preceding comments/docstrings
            comment_start_idx = self._find_comment_start(lines, start_idx)

            # Find the complete function body (no line limit)
            snippet_end = self._find_function_end(lines, start_idx)
            snippet_lines = lines[comment_start_idx:snippet_end]
            return "".join(snippet_lines).strip()

        except Exception as e:
            logger.error(f"Failed to extract function body: {e}")
            return None

    def _extract_context_snippet(
        self,
        file_path: str,
        line_number: int,
        context_lines: int = 5,
        worktree_path: Optional[str] = None
    ) -> Optional[Tuple[str, int]]:
        """
        Extract context around a symbol definition, including complete comment blocks above.

        Args:
            file_path: Path to the source file
            line_number: Line number of the symbol (1-indexed)
            context_lines: Number of lines before and after
            worktree_path: Optional path to the worktree for validation

        Returns:
            Tuple of (snippet_text, highlight_index) or None if extraction fails.
            highlight_index is the 0-indexed position of the symbol line in the result.
        """
        try:
            # Check file size
            if os.path.getsize(file_path) > self.MAX_FILE_SIZE:
                logger.warning(f"File too large to extract context: {file_path}")
                return None

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            if not lines or line_number < 1 or line_number > len(lines):
                return None

            # Convert to 0-indexed
            symbol_idx = line_number - 1

            # Find comment block start above the symbol
            comment_start_idx = self._find_comment_block_start(lines, symbol_idx)

            # Calculate start and end indices
            # If comment found, start at comment; otherwise use normal context
            if comment_start_idx is not None:
                start_idx = comment_start_idx
            else:
                start_idx = max(0, symbol_idx - context_lines)
            end_idx = min(len(lines), symbol_idx + context_lines + 1)

            # Extract context lines
            snippet_lines = lines[start_idx:end_idx]

            # Calculate highlight index (position of symbol line in snippet)
            highlight_index = symbol_idx - start_idx

            # Join lines and return
            snippet_text = "".join(snippet_lines).rstrip()
            return (snippet_text, highlight_index)

        except Exception as e:
            logger.error(f"Failed to extract context snippet: {e}")
            return None

    def _find_comment_block_start(
        self,
        lines: List[str],
        symbol_idx: int,
        max_lines: int = 30
    ) -> Optional[int]:
        """
        Find the start of a comment block preceding a symbol.
        Limited to max_lines above the symbol.

        Args:
            lines: All lines in the file
            symbol_idx: Index of the symbol line (0-indexed)
            max_lines: Maximum number of lines to search above (default 30)

        Returns:
            Index of the first line of the preceding comment block,
            or None if no comment is found.
        """
        # Lower bound for search
        min_idx = max(0, symbol_idx - max_lines)

        # Look backwards from symbol
        current_idx = symbol_idx - 1

        # Skip empty lines first
        while current_idx >= min_idx and not lines[current_idx].strip():
            current_idx -= 1

        if current_idx < min_idx:
            return None  # No comment found

        # Check if current line is a comment
        line = lines[current_idx].strip()

        # Helper to check if a line is a comment
        def is_comment_line(l: str) -> bool:
            return (
                l.startswith('#') or           # Python comment
                l.startswith('//') or          # C/C++/JS single-line comment
                l.startswith('/*') or          # C/C++ block comment start
                l.endswith('*/') or            # C/C++ block comment end
                (l.startswith('*') and not l.startswith('*(')) or  # Block comment content (not pointer)
                l.startswith('"""') or         # Python docstring
                l.startswith("'''") or        # Python docstring
                l.startswith('@')              # Decorator/annotation
            )

        if not is_comment_line(line):
            return None  # No comment found

        # Found a comment, find where it starts
        comment_end_idx = current_idx
        seen_block_end = False  # Track if we've seen a C-style block comment end (*/)

        # Walk backwards to find comment start
        while current_idx >= min_idx:
            line = lines[current_idx].strip()

            # Check for comment markers first (before empty line check)
            if line.startswith('/*'):
                # Start of C-style block comment - found it
                return current_idx
            elif line.endswith('*/'):
                # End of C-style block comment - now we're inside the block
                seen_block_end = True
                current_idx -= 1
                continue
            elif line.startswith('*') and not line.startswith('*('):
                # Block comment content - only valid if we've seen the block end
                if seen_block_end:
                    current_idx -= 1
                    continue
                else:
                    # Line starting with * but not inside a block comment - stop
                    break

            if not line:
                # Empty line
                if seen_block_end:
                    # Inside block comment, continue
                    current_idx -= 1
                    continue
                else:
                    # Not inside block, stop searching
                    break

            if line.startswith('#'):
                # Python comment
                current_idx -= 1
                continue
            elif line.startswith('//'):
                # C/C++ single-line comment
                current_idx -= 1
                continue
            elif line.startswith('"""') or line.startswith("'''"):
                # Python docstring
                if line.count('"""') >= 2 or line.count("'''") >= 2:
                    # Single line docstring
                    return current_idx
                else:
                    # Start/end of multi-line docstring
                    return current_idx
            elif line.startswith('@'):
                # Decorator/annotation - continue looking
                current_idx -= 1
                continue
            elif seen_block_end:
                # Inside a block comment (between */ and /*) but line doesn't have * prefix
                # (e.g., "This function is a possible cancellation point...")
                current_idx -= 1
                continue
            else:
                # NOT inside block comment and this is non-comment content - STOP
                break

        return current_idx + 1 if current_idx < comment_end_idx else None

    def _find_function_end(
        self,
        lines: List[str],
        start: int
    ) -> int:
        """
        Find the end of a function body (no line limit).

        Args:
            lines: All lines in the file
            start: Starting line index (0-indexed)

        Returns:
            End line index (exclusive)
        """
        if start >= len(lines):
            return len(lines)

        first_line = lines[start]
        indent_level = len(first_line) - len(first_line.lstrip())

        # For Python, look for dedent (no line limit)
        if first_line.strip().startswith(("def ", "class ", "async def ")):
            for i in range(start + 1, len(lines)):
                line = lines[i]
                # Empty line or comment, continue
                if not line.strip() or line.strip().startswith("#"):
                    continue
                # Dedent indicates end
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= indent_level and line.strip():
                    return i
            return len(lines)

        # For braces-based languages (C/C++/Java/JS/TS/Go/Rust), count braces
        # This handles the full function body including nested blocks
        if "{" in first_line:
            brace_count = first_line.count("{") - first_line.count("}")
            for i in range(start + 1, len(lines)):
                line = lines[i]
                brace_count += line.count("{") - line.count("}")
                if brace_count <= 0:
                    return i + 1
            return len(lines)

        # No brace found on first line - look for it on subsequent lines
        # (handles multi-line function signatures in C/C++)
        brace_count = 0
        found_opening_brace = False
        for i in range(start, len(lines)):
            line = lines[i]
            if "{" in line:
                found_opening_brace = True
                brace_count += line.count("{") - line.count("}")
            elif found_opening_brace:
                brace_count += line.count("{") - line.count("}")
                if brace_count <= 0:
                    return i + 1
        return len(lines)

    def _find_definition_end(
        self,
        lines: List[str],
        start: int,
        default_end: int
    ) -> int:
        """
        Find the end of a definition (function, class, etc.).

        Args:
            lines: All lines in the file
            start: Starting line index (0-indexed)
            default_end: Default end if not found

        Returns:
            End line index (exclusive)
        """
        if start >= len(lines):
            return default_end

        first_line = lines[start]
        indent_level = len(first_line) - len(first_line.lstrip())

        # For Python, look for dedent
        if first_line.strip().startswith(("def ", "class ", "async def ")):
            for i in range(start + 1, min(start + self.MAX_SNIPPET_LINES, len(lines))):
                line = lines[i]
                # Empty line or comment, continue
                if not line.strip() or line.strip().startswith("#"):
                    continue
                # Dedent indicates end
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= indent_level and line.strip():
                    return i
            return min(start + self.MAX_SNIPPET_LINES, len(lines))

        # For braces-based languages, count braces
        if "{" in first_line:
            brace_count = first_line.count("{") - first_line.count("}")
            for i in range(start + 1, min(start + self.MAX_SNIPPET_LINES, len(lines))):
                line = lines[i]
                brace_count += line.count("{") - line.count("}")
                if brace_count <= 0:
                    return i + 1
            return min(start + self.MAX_SNIPPET_LINES, len(lines))

        # Default: return MAX_SNIPPET_LINES or end of file
        return default_end

    def _extract_docstring(
        self,
        lines: List[str],
        def_line: int,
        file_path: str
    ) -> Optional[str]:
        """
        Extract docstring or JSDoc comment above a definition.

        Args:
            lines: All lines in the file
            def_line: Definition line index (0-indexed)
            file_path: Path to the file (for language detection)

        Returns:
            Docstring text or None
        """
        if def_line == 0:
            return None

        # Check for Python docstring
        if file_path.endswith(".py"):
            # Look for docstring after def line
            if def_line + 1 < len(lines):
                next_line = lines[def_line + 1].strip()
                if next_line.startswith(('"""', "'''")):
                    quote = '"""' if next_line.startswith('"""') else "'''"
                    # Single line docstring
                    if next_line.count(quote) >= 2:
                        return next_line.strip(quote).strip()
                    # Multi-line docstring
                    docstring_lines = [next_line]
                    for i in range(def_line + 2, len(lines)):
                        line = lines[i]
                        docstring_lines.append(line.rstrip())
                        if quote in line and i > def_line + 1:
                            break
                    # Clean up docstring
                    docstring = "".join(docstring_lines)
                    for q in ['"""', "'''"]:
                        docstring = docstring.replace(q, "")
                    return docstring.strip()

        # Check for JSDoc or block comment above definition
        docstring_lines = []
        in_block_comment = False
        block_comment_start_line = -1

        for i in range(def_line - 1, max(def_line - 20, -1), -1):
            line = lines[i].strip()

            # Skip empty lines (only if we haven't started collecting docstring)
            if not line:
                if docstring_lines:
                    break  # Stop at empty line after collecting some docstring
                continue

            # Single-line block comment: /* comment */
            if "/*" in line and "*/" in line:
                # Extract content between /* and */
                start_idx = line.find("/*")
                end_idx = line.rfind("*/")
                if start_idx < end_idx:
                    content = line[start_idx + 2:end_idx].strip()
                    # Clean up JSDoc style
                    content = content.lstrip("*").strip()
                    if content:
                        docstring_lines.insert(0, content)
                break  # Single-line comment is complete

            # End of block comment (found */ but not /*)
            if "*/" in line:
                if in_block_comment:
                    # Found another */ while already in comment - this shouldn't happen
                    # Reset and start fresh
                    docstring_lines = []
                    in_block_comment = True
                    block_comment_start_line = i
                else:
                    in_block_comment = True
                    block_comment_start_line = i
                # Extract text before */
                parts = line.split("*/")
                if parts[0].strip():
                    docstring_lines.insert(0, parts[0].strip())
                continue

            # Start of block comment
            if in_block_comment and "/*" in line:
                parts = line.split("/*")
                if len(parts) > 1 and parts[1].strip():
                    # Clean up JSDoc style (e.g., /** becomes clean content)
                    content = parts[1].lstrip("*").strip()
                    if content:
                        docstring_lines.insert(0, content)
                break  # Found the start, we're done

            # Inside block comment
            if in_block_comment:
                # Clean up JSDoc style (remove leading *)
                cleaned = line.lstrip("*").strip()
                if cleaned:
                    docstring_lines.insert(0, cleaned)
                continue

            # Single line comment (//)
            if line.startswith("//"):
                cleaned = line[2:].strip()
                docstring_lines.insert(0, cleaned)
                continue

            # Not a comment and not empty - stop immediately
            break

        if docstring_lines:
            return "\n".join(docstring_lines)

        return None

    def _extract_signature(self, line: str, file_path: str) -> Optional[str]:
        """
        Extract type signature from a definition line.

        Args:
            line: The definition line
            file_path: Path to the file (for language detection)

        Returns:
            Signature string or None
        """
        line = line.strip()

        # Python function
        if file_path.endswith(".py"):
            if line.startswith(("def ", "async def ")):
                # Extract function signature
                if "(" in line and ")" in line:
                    return line.split(":")[0].strip()

        # TypeScript/JavaScript
        if file_path.endswith((".ts", ".tsx", ".js", ".jsx", ".vue")):
            # Function declaration
            if "function" in line:
                return line.split("{")[0].strip().rstrip(";")
            # Arrow function or method
            if "=>" in line:
                return line.split("=>")[0].strip()
            # Method signature
            if "(" in line and (":" in line or ")" in line):
                sig = line.split("{")[0].strip().rstrip(";")
                return sig

        # Go function
        if file_path.endswith(".go"):
            if line.startswith("func "):
                return line.split("{")[0].strip()

        # Rust function
        if file_path.endswith(".rs"):
            if line.startswith(("fn ", "pub fn ", "pub async fn ")):
                return line.split("{")[0].strip()

        # C/C++
        if file_path.endswith((".c", ".cpp", ".h", ".hpp")):
            # Function signature
            if "(" in line:
                sig = line.split("{")[0].strip()
                if sig.endswith(")"):
                    return sig

        return None


# Global service instance
_ctags_service: Optional[CtagsService] = None


def get_ctags_service() -> CtagsService:
    """
    Get the singleton CtagsService instance.

    Returns:
        CtagsService instance
    """
    global _ctags_service
    if _ctags_service is None:
        from app.config import settings
        _ctags_service = CtagsService(settings.projects_dir)
    return _ctags_service
import hashlib
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from app.schemas import FileNode

logger = logging.getLogger(__name__)

# Maximum file size for text editing/diff (500KB)
MAX_FILE_SIZE = 512000

# Upload configuration for temp directory uploads
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "104857600"))  # 100MB default
TEMP_UPLOAD_DIR = os.getenv("TEMP_UPLOAD_DIR", "/tmp/vibe2crazy-upload")


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes} B"


class FileService:
    """Service for file operations"""

    @staticmethod
    def list_directory(directory: str, relative_path: str = "") -> List[FileNode]:
        """
        List immediate children of a directory (non-recursive, for lazy loading)

        Args:
            directory: Full path to the directory to list
            relative_path: Relative path from worktree root (for building node paths)

        Returns:
            List of FileNode objects (only immediate children, no grandchildren)
        """
        try:
            path = Path(directory)
            if not path.exists() or not path.is_dir():
                return []

            nodes = []
            for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                # Skip .git directory (internal Git data)
                # Allow all other files including dotfiles (.env, .gitignore, etc.)
                if item.name == ".git":
                    continue

                # Build full relative path for this node
                node_path = os.path.join(relative_path, item.name) if relative_path else item.name

                if item.is_dir():
                    # For directories, don't load children - set to empty list
                    # Frontend will request children when directory is expanded
                    node = FileNode(
                        name=item.name,
                        path=node_path,
                        type="directory",
                        children=[]  # Empty array indicates "can be expanded" but not loaded yet
                    )
                    nodes.append(node)
                else:
                    node = FileNode(
                        name=item.name,
                        path=node_path,
                        type="file",
                        children=None
                    )
                    nodes.append(node)

            return nodes
        except Exception as e:
            # Log error but don't crash - return empty list
            import logging
            logging.getLogger(__name__).error(f"Error listing directory {directory}: {e}")
            return []

    @staticmethod
    def build_file_tree(directory: str, base_path: str = "") -> List[FileNode]:
        """
        Build a file tree structure from a directory (recursive, legacy method)

        NOTE: This method is deprecated for large file trees.
        Use list_directory() for lazy loading instead.
        """
        try:
            path = Path(directory)
            if not path.exists():
                return []

            nodes = []
            for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                # Skip .git directory (internal Git data)
                # Allow all other files including dotfiles (.env, .gitignore, etc.)
                if item.name == ".git":
                    continue

                relative_path = os.path.join(base_path, item.name) if base_path else item.name

                if item.is_dir():
                    children = FileService.build_file_tree(str(item), relative_path)
                    node = FileNode(
                        name=item.name,
                        path=relative_path,
                        type="directory",
                        children=children if children else None
                    )
                    nodes.append(node)
                else:
                    node = FileNode(
                        name=item.name,
                        path=relative_path,
                        type="file",
                        children=None
                    )
                    nodes.append(node)

            return nodes
        except Exception:
            return []

    @staticmethod
    def read_file(worktree_path: str, file_path: str) -> tuple[bool, str, Optional[str]]:
        """
        Read file content
        Returns: (success, content, error_message)
        """
        try:
            full_path = Path(worktree_path) / file_path

            # Security check: ensure path is within worktree
            full_path = full_path.resolve()
            worktree = Path(worktree_path).resolve()
            if not str(full_path).startswith(str(worktree)):
                return False, "", "Path outside worktree"

            if not full_path.exists():
                return False, "", "File not found"

            if not full_path.is_file():
                return False, "", "Not a file"

            # Check file size
            file_size = full_path.stat().st_size
            if file_size > MAX_FILE_SIZE:
                size_formatted = format_file_size(file_size)
                return False, "", f"File too large to display ({size_formatted})"

            content = full_path.read_text(encoding="utf-8", errors="replace")
            return True, content, None
        except Exception as e:
            return False, "", str(e)

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

    @staticmethod
    def write_file(worktree_path: str, file_path: str, content: str) -> tuple[bool, Optional[str]]:
        """
        Write content to file
        Returns: (success, error_message)
        """
        try:
            full_path = Path(worktree_path) / file_path

            # Security check: ensure path is within worktree
            full_path = full_path.resolve()
            worktree = Path(worktree_path).resolve()
            if not str(full_path).startswith(str(worktree)):
                return False, "Path outside worktree"

            # Create parent directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            full_path.write_text(content, encoding="utf-8")
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_file_stats(worktree_path: str, file_path: str) -> dict:
        """Get file statistics"""
        try:
            full_path = Path(worktree_path) / file_path
            if not full_path.exists():
                return {}

            stat = full_path.stat()
            return {
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "is_file": full_path.is_file(),
                "is_dir": full_path.is_dir()
            }
        except Exception:
            return {}

    @staticmethod
    def delete_file(worktree_path: str, file_path: str) -> tuple[bool, Optional[str]]:
        """
        Delete a file or directory (recursive for directories).

        Args:
            worktree_path: Path to the task worktree
            file_path: Relative path to file/directory to delete

        Returns:
            (success, error_message)
        """
        try:
            full_path = Path(worktree_path) / file_path

            # Security check: ensure path is within worktree
            full_path = full_path.resolve()
            worktree = Path(worktree_path).resolve()
            try:
                full_path.relative_to(worktree)
            except ValueError:
                return False, "Path outside worktree"

            # Don't allow deleting .git directory
            if full_path.name == ".git":
                logger.warning(f"Attempted to delete .git directory in {worktree_path}")
                return False, "Cannot delete .git directory"

            if not full_path.exists():
                return False, "File not found"

            logger.info(f"Deleting {file_path} in worktree {worktree_path}")

            if full_path.is_dir():
                shutil.rmtree(full_path)
            else:
                full_path.unlink()

            return True, None
        except Exception as e:
            logger.error(f"Failed to delete {file_path}: {e}")
            return False, str(e)

    @staticmethod
    def search_files(directory: str, query: str, limit: int) -> List[str]:
        """
        Search files with server-side filtering and result limiting.
        Optimized for large projects with efficient traversal.

        Args:
            directory: Full path to the worktree directory
            query: Search query (lowercase, substring match on file path)
            limit: Maximum number of results to return

        Returns:
            Filtered and sorted list of matching file paths
        """
        try:
            results = []
            base_path = Path(directory)

            if not base_path.exists() or not base_path.is_dir():
                return []

            # Use os.scandir for efficient directory traversal (2-3x faster than Path.rglob)
            def _collect_files(current_dir: Path, current_rel: str = ""):
                nonlocal results
                # Early exit if we've reached the limit
                if len(results) >= limit:
                    return

                try:
                    with os.scandir(current_dir) as entries:
                        for entry in entries:
                            # Skip .git directory
                            if entry.name == ".git" or (current_rel and current_rel.startswith(".git")):
                                continue

                            rel_path = os.path.join(current_rel, entry.name) if current_rel else entry.name

                            if entry.is_file():
                                # Check if file matches the search query
                                if not query or query in rel_path.lower():
                                    results.append(rel_path)
                                    # Early exit if we've reached the limit
                                    if len(results) >= limit:
                                        return
                            elif entry.is_dir():
                                # Recursively collect files from subdirectories
                                _collect_files(Path(entry.path), rel_path)
                                # Early exit if we've reached the limit
                                if len(results) >= limit:
                                    return
                except (PermissionError, OSError) as e:
                    logger.warning(f"Permission error accessing {current_dir}: {e}")

            _collect_files(base_path)

            return results[:limit]
        except Exception as e:
            logger.error(f"Error searching files in {directory}: {e}")
            return []

    @staticmethod
    def list_all_files(directory: str) -> List[str]:
        """
        List all files in directory recursively (flat list of file paths).
        Uses os.scandir for better performance.

        Args:
            directory: Full path to the directory to search

        Returns:
            List of relative file paths from the directory root
        """
        try:
            path = Path(directory)
            if not path.exists() or not path.is_dir():
                return []

            files = []

            def _collect_files(current_dir: Path, current_rel: str = ""):
                try:
                    with os.scandir(current_dir) as entries:
                        for entry in entries:
                            # Skip .git directory and its contents
                            if entry.name == ".git" or (current_rel and current_rel.startswith(".git")):
                                continue

                            rel_path = os.path.join(current_rel, entry.name) if current_rel else entry.name

                            if entry.is_file():
                                files.append(rel_path)
                            elif entry.is_dir():
                                _collect_files(Path(entry.path), rel_path)
                except (PermissionError, OSError) as e:
                    logger.warning(f"Permission error accessing {current_dir}: {e}")

            _collect_files(path)
            return sorted(files)
        except Exception as e:
            logger.error(f"Error listing all files in {directory}: {e}")
            return []

    @staticmethod
    def generate_unique_filename(directory: str, filename: str) -> str:
        """Generate unique filename, appending number if needed."""
        base, ext = os.path.splitext(filename)
        counter = 1
        result = filename

        while os.path.exists(os.path.join(directory, result)):
            result = f"{base}-{counter}{ext}"
            counter += 1

        return result

    @staticmethod
    def generate_screenshot_filename() -> str:
        """Generate timestamped filename for clipboard images."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"screenshot-{timestamp}.png"

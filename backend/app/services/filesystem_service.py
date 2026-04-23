"""
FilesystemService - Secure filesystem operations for directory browsing.

This service provides secure directory listing capabilities with:
- Path validation to prevent directory traversal attacks
- Filtering of hidden directories
- Graceful error handling for permission issues
- Sorted, predictable output
"""

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class FilesystemService:
    """Service for secure filesystem operations."""

    @staticmethod
    def _validate_path(path: str) -> Path:
        """
        Validate and resolve a path to absolute.

        Args:
            path: The path to validate

        Returns:
            Resolved absolute Path object

        Raises:
            ValueError: If path contains directory traversal attempts (..)
        """
        # Check for directory traversal attempts
        if ".." in path:
            logger.warning(f"Directory traversal attempt detected: {path}")
            raise ValueError("Directory traversal not allowed: path cannot contain '..'")

        # Resolve to absolute path
        resolved_path = Path(path).resolve()
        logger.debug(f"Validated path: {path} -> {resolved_path}")

        return resolved_path

    @staticmethod
    def list_directories(path: str) -> List[str]:
        """
        List immediate child directories only (not recursive).

        Args:
            path: The directory path to list

        Returns:
            Sorted list of absolute directory paths as strings.
            Returns empty list for non-existent paths, files, or permission errors.
            Filters out hidden directories (starting with '.').
        """
        try:
            # Validate the path first
            validated_path = FilesystemService._validate_path(path)

            # Check if path exists
            if not validated_path.exists():
                logger.debug(f"Path does not exist: {validated_path}")
                return []

            # Check if path is a directory
            if not validated_path.is_dir():
                logger.debug(f"Path is not a directory: {validated_path}")
                return []

            # List child directories
            child_dirs = []
            for item in validated_path.iterdir():
                # Only include directories
                if item.is_dir():
                    # Filter out hidden directories (starting with '.')
                    if not item.name.startswith("."):
                        child_dirs.append(str(item.resolve()))

            # Sort results
            child_dirs.sort()
            logger.debug(f"Found {len(child_dirs)} directories in {validated_path}")

            return child_dirs

        except PermissionError as e:
            logger.warning(f"Permission denied accessing path: {path} - {e}")
            return []
        except ValueError:
            # Re-raise ValueError (from _validate_path)
            raise

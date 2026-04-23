import pytest
from pathlib import Path
from app.services.filesystem_service import FilesystemService


class TestFilesystemService:
    """Test suite for FilesystemService"""

    def test_list_directories_returns_immediate_children(self, tmp_path):
        """Only returns child dirs, not files or hidden dirs"""
        # Create test structure
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir2").mkdir()
        (tmp_path / ".hidden_dir").mkdir()
        (tmp_path / "file1.txt").write_text("content")
        (tmp_path / "file2.md").write_text("content")

        # Test listing
        result = FilesystemService.list_directories(str(tmp_path))

        # Should only include immediate child directories, not hidden ones or files
        assert len(result) == 2
        assert str(tmp_path / "dir1") in result
        assert str(tmp_path / "dir2") in result
        assert str(tmp_path / ".hidden_dir") not in result
        assert str(tmp_path / "file1.txt") not in result
        assert str(tmp_path / "file2.md") not in result

    def test_list_directories_returns_empty_for_nonexistent_path(self, tmp_path):
        """Returns [] for non-existent paths"""
        nonexistent = tmp_path / "does_not_exist"
        result = FilesystemService.list_directories(str(nonexistent))
        assert result == []

    def test_list_directories_returns_empty_for_file_not_directory(self, tmp_path):
        """Returns [] for files"""
        # Create a file
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        # Try to list directories on a file path
        result = FilesystemService.list_directories(str(test_file))
        assert result == []

    def test_list_directories_handles_permission_denied(self, tmp_path, monkeypatch):
        """Gracefully handles PermissionError"""
        # Create a directory
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        # Mock Path.iterdir to raise PermissionError
        def mock_iterdir(self):
            raise PermissionError("Access denied")

        monkeypatch.setattr(Path, "iterdir", mock_iterdir)

        # Should return empty list instead of crashing
        result = FilesystemService.list_directories(str(test_dir))
        assert result == []

    def test_validate_path_resolves_absolute(self, tmp_path):
        """Resolves paths to absolute"""
        # Create a test directory
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        # Test with relative path
        relative_path = str(tmp_path / "test_dir")
        result = FilesystemService._validate_path(relative_path)

        assert isinstance(result, Path)
        assert result.is_absolute()
        # Should resolve to the same absolute path

    def test_validate_path_raises_on_directory_traversal(self, tmp_path):
        """Raises ValueError for paths with .."""
        # Test various directory traversal attempts
        traversal_attempts = [
            str(tmp_path / ".."),
            str(tmp_path / "dir1" / ".." / "dir2"),
            "../etc/passwd",
            "/etc/passwd/../..",
        ]

        for attempt in traversal_attempts:
            with pytest.raises(ValueError, match="Directory traversal"):
                FilesystemService._validate_path(attempt)

    def test_list_directories_sorts_results(self, tmp_path):
        """Returns sorted results"""
        # Create directories in non-alphabetical order
        (tmp_path / "zebra").mkdir()
        (tmp_path / "apple").mkdir()
        (tmp_path / "banana").mkdir()

        result = FilesystemService.list_directories(str(tmp_path))

        # Should be sorted alphabetically
        assert result == sorted(result)
        # Verify order
        assert result[0].endswith("apple")
        assert result[1].endswith("banana")
        assert result[2].endswith("zebra")

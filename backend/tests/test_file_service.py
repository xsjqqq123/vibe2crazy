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
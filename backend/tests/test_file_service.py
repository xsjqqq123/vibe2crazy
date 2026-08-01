"""Tests for FileService methods."""
import pytest
import tempfile
import os
from pathlib import Path
from app.services.file_service import FileService, EXCLUDED_FILE_EXTENSIONS, EXCLUDED_DIR_NAMES


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


class TestSearchFilesExclusions:
    """Tests for Ctrl+P file search exclusions (compiled artifacts / temp files)."""

    def _create_sample_tree(self, tmpdir: str):
        """Create a sample directory tree with normal and excluded files."""
        root = Path(tmpdir)
        # Normal source files
        (root / "main.c").write_text("int main() { return 0; }")
        (root / "helper.py").write_text("def helper(): pass")
        (root / "normal.md").write_text("# Normal")
        # Compiled artifacts
        (root / "main.o").write_bytes(b"\x7fELF")
        (root / "lib.a").write_bytes(b"!<arch>")
        (root / "helper.pyc").write_bytes(b"\x00\x00")
        # Uppercase extension variant (case-insensitive check)
        (root / "MAIN.O").write_bytes(b"\x7fELF")
        # Cache directory (should be skipped without recursion)
        pycache = root / "__pycache__"
        pycache.mkdir()
        (pycache / "x.pyc").write_bytes(b"\x00\x00")
        return root

    def test_empty_query_excludes_compiled_artifacts(self):
        """Excluded extensions should never appear, even with empty query."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_sample_tree(tmpdir)
            results = FileService.search_files(tmpdir, "", 100)

            assert "main.c" in results
            assert "helper.py" in results
            assert "normal.md" in results
            assert "main.o" not in results
            assert "MAIN.O" not in results
            assert "lib.a" not in results
            assert "helper.pyc" not in results

    def test_cache_directory_skipped_without_recursion(self):
        """Files inside excluded directories should not appear."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_sample_tree(tmpdir)
            results = FileService.search_files(tmpdir, "", 100)

            assert "__pycache__/x.pyc" not in results

    def test_explicit_query_does_not_override_exclusion(self):
        """Searching for an excluded file by name should return nothing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_sample_tree(tmpdir)
            results = FileService.search_files(tmpdir, "main.o", 100)

            assert results == []

    def test_normal_query_still_works(self):
        """Searching for a normal file should still return it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._create_sample_tree(tmpdir)
            results = FileService.search_files(tmpdir, "helper", 100)

            assert "helper.py" in results
            assert "helper.pyc" not in results

    def test_excluded_files_do_not_consume_limit(self):
        """Excluded files should not count toward the result limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Create 3 normal files and many excluded .o files
            for i in range(3):
                (root / f"file{i}.txt").write_text("content")
            for i in range(50):
                (root / f"obj{i}.o").write_bytes(b"\x7fELF")

            results = FileService.search_files(tmpdir, "", 10)

            assert len(results) == 3
            assert all("file" in r for r in results)

    def test_all_excluded_extensions_are_filtered(self):
        """Every extension in EXCLUDED_FILE_EXTENSIONS should be filtered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for ext in EXCLUDED_FILE_EXTENSIONS:
                (root / f"sample{ext}").write_bytes(b"data")
            (root / "keep.txt").write_text("keep")

            results = FileService.search_files(tmpdir, "", 100)

            assert results == ["keep.txt"]

    def test_all_excluded_dirs_are_skipped(self):
        """Every directory in EXCLUDED_DIR_NAMES should be skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for dirname in EXCLUDED_DIR_NAMES:
                d = root / dirname
                d.mkdir()
                (d / "inner.txt").write_text("inner")
            (root / "keep.txt").write_text("keep")

            results = FileService.search_files(tmpdir, "", 100)

            assert results == ["keep.txt"]


class TestAddToGitignore:
    """Tests for the add_to_gitignore method."""

    def test_creates_gitignore_when_missing(self):
        """Should create .gitignore when it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            success, message = FileService.add_to_gitignore(tmpdir, "build/output.o")

            assert success is True
            gitignore = Path(tmpdir) / ".gitignore"
            assert gitignore.exists()
            assert "build/output.o\n" in gitignore.read_text()

    def test_appends_to_existing_gitignore(self):
        """Should append entry to an existing .gitignore."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".gitignore").write_text("node_modules/\n")
            success, _ = FileService.add_to_gitignore(tmpdir, "src/main.o")

            assert success is True
            content = (Path(tmpdir) / ".gitignore").read_text()
            assert "node_modules/\n" in content
            assert "src/main.o\n" in content

    def test_idempotent_no_duplicate(self):
        """Adding the same entry twice should not duplicate the line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            FileService.add_to_gitignore(tmpdir, "a.o")
            success, message = FileService.add_to_gitignore(tmpdir, "a.o")

            assert success is True
            content = (Path(tmpdir) / ".gitignore").read_text()
            assert content.count("a.o") == 1
            assert "already in .gitignore" in message

    def test_directory_entry_gets_trailing_slash(self):
        """Directory entries should get a trailing slash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            FileService.add_to_gitignore(tmpdir, "build", is_dir=True)

            content = (Path(tmpdir) / ".gitignore").read_text()
            assert "build/\n" in content

    def test_path_normalization(self):
        """Backslashes and leading ./ should be normalized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            FileService.add_to_gitignore(tmpdir, ".\\src\\foo.o")
            FileService.add_to_gitignore(tmpdir, "./dist/")

            content = (Path(tmpdir) / ".gitignore").read_text()
            assert "src/foo.o\n" in content
            assert "dist/\n" in content

    def test_path_outside_worktree_rejected(self):
        """Path traversal outside worktree should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with tempfile.TemporaryDirectory() as otherdir:
                success, message = FileService.add_to_gitignore(tmpdir, "../" + os.path.basename(otherdir) + "/x.o")

                assert success is False
                assert "outside worktree" in message.lower()
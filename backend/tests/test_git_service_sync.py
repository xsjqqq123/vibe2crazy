import pytest
import subprocess
import tempfile
import os
from pathlib import Path
from app.services.git_service import GitService


@pytest.fixture
def temp_repo_with_worktree():
    """Create a temporary repo with main and a worktree branch"""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "repo"
        worktree_path = Path(tmpdir) / "worktree"

        # Create directories
        repo_path.mkdir(parents=True, exist_ok=True)

        # Initialize main repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, capture_output=True)

        # Create initial commit on main
        (repo_path / "file1.txt").write_text("initial content\n")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "branch", "-M", "main"], cwd=repo_path, capture_output=True)

        # Create worktree branch
        subprocess.run(["git", "worktree", "add", str(worktree_path), "-b", "test-branch"], cwd=repo_path, capture_output=True)

        yield repo_path, worktree_path


def test_sync_main_into_worktree_no_conflicts(temp_repo_with_worktree):
    """Test sync when worktree is behind main with no conflicts"""
    repo_path, worktree_path = temp_repo_with_worktree

    # Add a commit to main
    (repo_path / "file2.txt").write_text("new file on main\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Add file2 on main"], cwd=repo_path, capture_output=True)

    # Sync main into worktree
    success, message, has_conflicts, conflict_files = GitService.sync_main_into_worktree(
        worktree_path=str(worktree_path),
        main_branch="main"
    )

    # Assert sync succeeded
    assert success is True
    assert has_conflicts is False
    assert len(conflict_files) == 0

    # Assert worktree now has the file from main
    assert (worktree_path / "file2.txt").exists()
    assert (worktree_path / "file2.txt").read_text() == "new file on main\n"


def test_sync_main_into_worktree_with_conflicts(temp_repo_with_worktree):
    """Test sync when worktree and main modified same file"""
    repo_path, worktree_path = temp_repo_with_worktree

    # Modify file1.txt in worktree
    (worktree_path / "file1.txt").write_text("worktree change\n")
    subprocess.run(["git", "add", "."], cwd=worktree_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Change in worktree"], cwd=worktree_path, capture_output=True)

    # Modify same file on main (different branch now)
    (repo_path / "file1.txt").write_text("main change\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Change in main"], cwd=repo_path, capture_output=True)

    # Sync main into worktree
    success, message, has_conflicts, conflict_files = GitService.sync_main_into_worktree(
        worktree_path=str(worktree_path),
        main_branch="main"
    )

    # Assert sync detected conflicts
    assert success is False
    assert has_conflicts is True
    assert len(conflict_files) > 0
    assert "file1.txt" in conflict_files


def test_sync_main_into_worktree_already_up_to_date(temp_repo_with_worktree):
    """Test sync when worktree is already up to date"""
    repo_path, worktree_path = temp_repo_with_worktree

    # Sync when already up to date
    success, message, has_conflicts, conflict_files = GitService.sync_main_into_worktree(
        worktree_path=str(worktree_path),
        main_branch="main"
    )

    # Assert sync reports already up to date
    assert success is True
    assert has_conflicts is False
    assert "Already up to date" in message or "Sync successful" in message

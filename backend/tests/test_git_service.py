"""
Tests for GitService, focusing on commit hash format.
"""
import pytest
import subprocess
from pathlib import Path
from app.services.git_service import GitService
from unittest.mock import patch, MagicMock


def test_get_changed_files_with_status_returns_empty_list_on_git_error():
    """Test that git command failure returns empty list"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="git error")
        result = GitService.get_changed_files_with_status("/fake/path")
        assert result == []


def test_get_changed_files_with_status_parses_porcelain_output():
    """Test parsing of git status --porcelain output"""
    porcelain_output = """M src/App.vue
A src/new.ts
D src/old.ts
R  src/orig.ts -> src/renamed.ts
?? src/untracked.ts"""

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=porcelain_output
        )
        result = GitService.get_changed_files_with_status("/fake/path")

        assert len(result) == 5
        assert {"path": "src/App.vue", "status": "M"} in result
        assert {"path": "src/new.ts", "status": "A"} in result
        assert {"path": "src/old.ts", "status": "D"} in result
        assert {"path": "src/renamed.ts", "status": "R"} in result
        assert {"path": "src/untracked.ts", "status": "?"} in result


def test_get_changed_files_with_status_filters_empty_paths():
    """Test that empty paths are filtered out"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="M src/App.vue\n\nA src/new.ts"
        )
        result = GitService.get_changed_files_with_status("/fake/path")
        assert len(result) == 2
        assert all(f["path"] for f in result)


@pytest.fixture(scope="function")
def tmp_project(tmp_path):
    """
    Create a temporary git repository for testing.
    Returns the path to the temporary repo.
    """
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_path,
        check=True
    )
    # Rename master to main for consistency
    subprocess.run(["git", "branch", "-m", "main"], cwd=repo_path, check=True)

    # Create initial commit on main branch
    (repo_path / "README.md").write_text("# Test Repository")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        check=True
    )

    yield repo_path


@pytest.fixture(scope="function")
def task_worktree(tmp_project):
    """
    Create a temporary worktree for testing.
    Returns the path to the worktree.
    """
    worktree_path = tmp_project.parent / "task-worktree"

    # Create worktree
    success, msg = GitService.create_worktree(
        repo_path=str(tmp_project),
        branch_name="test-task",
        worktree_path=str(worktree_path)
    )

    assert success, f"Failed to create worktree: {msg}"
    assert worktree_path.exists(), "Worktree directory should exist"

    yield worktree_path

    # Cleanup
    if worktree_path.exists():
        GitService.delete_worktree(str(worktree_path), str(tmp_project))
    # Delete branch
    subprocess.run(
        ["git", "branch", "-D", "test-task"],
        cwd=tmp_project,
        capture_output=True
    )


def test_get_worktree_commits_returns_full_hash(tmp_project, task_worktree):
    """
    Test that get_worktree_commits returns full 40-character SHA-1 hashes.

    This test verifies the fix for the bug where checkmark (✓) indicators
    don't appear in the Commits list. The root cause is that backend returns
    8-character short hashes but last_merge_commit_hash stores 40-character
    full hashes, so comparison never succeeds.
    """
    from app.services.git_service import GitService

    # Create a test commit in the worktree
    test_file = task_worktree / "test.txt"
    test_file.write_text("test content")

    subprocess.run(["git", "add", "."], cwd=task_worktree, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Test commit"],
        cwd=task_worktree,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@test.com"
        }
    )

    # Get commits from the worktree
    commits = GitService.get_worktree_commits(str(task_worktree), "main", limit=1)

    # Verify we have one commit
    assert len(commits) == 1, f"Should have one commit, got {len(commits)}"

    # Verify the hash is the full 40-character SHA-1 hash
    commit_hash = commits[0]['hash']
    assert len(commit_hash) == 40, (
        f"Hash should be 40 characters (full SHA-1), got {len(commit_hash)} characters: '{commit_hash}'"
    )

    # Verify the hash is lowercase hexadecimal
    assert commit_hash == commit_hash.lower(), "Hash should be lowercase hex"
    assert all(c in '0123456789abcdef' for c in commit_hash), (
        f"Hash should contain only hex characters, got: {commit_hash}"
    )

    # Verify we can get the latest commit hash and it matches
    latest_hash = GitService.get_latest_commit_hash(str(task_worktree))
    assert latest_hash is not None, "Should be able to get latest commit hash"
    assert commit_hash == latest_hash, (
        f"Commit hash from get_worktree_commits should match get_latest_commit_hash. "
        f"Got {commit_hash} vs {latest_hash}"
    )


def test_get_latest_commit_hash_returns_none_for_empty_repo(tmp_path):
    """
    Test that get_latest_commit_hash returns None for a repository with no commits.

    This test verifies the edge case handling for empty worktrees.
    When a worktree has no commits, get_latest_commit_hash should return None
    instead of crashing or returning an empty string.
    """
    # Create an empty git repo (no commits)
    empty_repo = tmp_path / "empty-repo"
    empty_repo.mkdir()

    subprocess.run(["git", "init"], cwd=empty_repo, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=empty_repo,
        check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=empty_repo,
        check=True
    )

    # Try to get latest commit hash from empty repo
    latest_hash = GitService.get_latest_commit_hash(str(empty_repo))

    # Should return None (not crash or return empty string)
    assert latest_hash is None, (
        f"get_latest_commit_hash should return None for empty repo, got: {latest_hash}"
    )


def test_get_local_branches_returns_branches_and_current(tmp_project):
    """
    Test that get_local_branches returns all local branches and identifies current branch.
    """
    # Create additional branches
    subprocess.run(["git", "branch", "develop"], cwd=tmp_project, check=True)
    subprocess.run(["git", "branch", "feature-x"], cwd=tmp_project, check=True)

    branches, current = GitService.get_local_branches(str(tmp_project))

    # Should return all branches
    assert "main" in branches
    assert "develop" in branches
    assert "feature-x" in branches

    # Should identify current branch
    assert current == "main"

    # Branches should be sorted
    assert branches == sorted(branches)


def test_get_local_branches_handles_non_git_directory(tmp_path):
    """
    Test that get_local_branches returns empty list for non-git directory.
    """
    non_git_dir = tmp_path / "non-git"
    non_git_dir.mkdir()

    branches, current = GitService.get_local_branches(str(non_git_dir))

    assert branches == []
    assert current == ""

"""
Tests for GitService pagination features.
"""
import pytest
import subprocess
from pathlib import Path
from app.services.git_service import GitService


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
def temp_worktree(tmp_project):
    """
    Create a temporary worktree for testing.
    Returns dict with path and main_branch.
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

    yield {
        "path": worktree_path,
        "main_branch": "main"
    }

    # Cleanup
    if worktree_path.exists():
        GitService.delete_worktree(str(worktree_path), str(tmp_project))
    # Delete branch
    subprocess.run(
        ["git", "branch", "-D", "test-task"],
        cwd=tmp_project,
        capture_output=True
    )


def test_count_worktree_commits(temp_worktree):
    """Test counting commits ahead of main branch."""
    # Setup: Create 5 commits
    worktree_path = temp_worktree["path"]
    main_branch = temp_worktree["main_branch"]

    for i in range(5):
        subprocess.run(
            ["git", "-C", worktree_path, "commit", "--allow-empty", "-m", f"Commit {i}"],
            capture_output=True
        )

    # Test
    count = GitService._count_worktree_commits(worktree_path, main_branch)

    # Assert
    assert count == 5


def test_count_worktree_commits_empty_repo(temp_worktree):
    """Test counting commits when worktree has no commits ahead of main."""
    worktree_path = temp_worktree["path"]
    main_branch = temp_worktree["main_branch"]

    # No new commits created, should return 0
    count = GitService._count_worktree_commits(worktree_path, main_branch)

    assert count == 0


def test_count_worktree_commits_invalid_path():
    """Test counting commits with invalid path returns 0 instead of crashing."""
    # Use a non-existent path
    invalid_path = "/tmp/nonexistent-worktree-12345"

    # Should return 0, not crash
    count = GitService._count_worktree_commits(invalid_path, "main")

    assert count == 0


def test_get_commits_page_first_page(temp_worktree):
    """Test fetching first page of commits."""
    worktree_path = temp_worktree["path"]
    main_branch = temp_worktree["main_branch"]

    # Create 5 commits
    for i in range(5):
        subprocess.run(
            ["git", "-C", worktree_path, "commit", "--allow-empty", "-m", f"Commit {i}"],
            capture_output=True
        )

    # Test: Get first page with 2 items
    commits = GitService._get_commits_page(worktree_path, main_branch, offset=0, limit=2)

    # Assert
    assert len(commits) == 2
    # Most recent commits come first
    assert commits[0]["message"] == "Commit 4"
    assert commits[1]["message"] == "Commit 3"


def test_get_commits_page_second_page(temp_worktree):
    """Test fetching second page with offset."""
    worktree_path = temp_worktree["path"]
    main_branch = temp_worktree["main_branch"]

    # Create 5 commits
    for i in range(5):
        subprocess.run(
            ["git", "-C", worktree_path, "commit", "--allow-empty", "-m", f"Commit {i}"],
            capture_output=True
        )

    # Test: Get second page
    commits = GitService._get_commits_page(worktree_path, main_branch, offset=2, limit=2)

    # Assert
    assert len(commits) == 2
    assert commits[0]["message"] == "Commit 2"
    assert commits[1]["message"] == "Commit 1"


def test_get_worktree_commits_paginated(temp_worktree):
    """Test full paginated response."""
    worktree_path = temp_worktree["path"]
    main_branch = temp_worktree["main_branch"]

    # Create 5 commits
    for i in range(5):
        subprocess.run(
            ["git", "-C", worktree_path, "commit", "--allow-empty", "-m", f"Commit {i}"],
            capture_output=True
        )

    # Test: Get first page with 2 items
    result = GitService.get_worktree_commits_paginated(
        worktree_path, main_branch, offset=0, limit=2
    )

    # Assert
    assert result["total"] == 5
    assert result["page"] == 1
    assert result["page_size"] == 2
    assert result["total_pages"] == 3  # 5 / 2 rounded up
    assert len(result["items"]) == 2


def test_get_worktree_commits_paginated_empty(temp_worktree):
    """Test paginated response with no commits."""
    worktree_path = temp_worktree["path"]
    main_branch = temp_worktree["main_branch"]

    # No commits created

    # Test
    result = GitService.get_worktree_commits_paginated(
        worktree_path, main_branch, offset=0, limit=30
    )

    # Assert
    assert result["total"] == 0
    assert result["page"] == 1
    assert result["page_size"] == 30
    assert result["total_pages"] == 0
    assert result["items"] == []


def test_page_out_of_range_returns_last_page(temp_worktree):
    """Test that requesting beyond last page returns last page."""
    worktree_path = temp_worktree["path"]
    main_branch = temp_worktree["main_branch"]

    # Create 5 commits
    for i in range(5):
        subprocess.run(
            ["git", "-C", worktree_path, "commit", "--allow-empty", "-m", f"Commit {i}"],
            capture_output=True
        )

    # Request page 999 (way beyond available)
    result = GitService.get_worktree_commits_paginated(
        worktree_path, main_branch, offset=999 * 30, limit=30
    )

    # Should return last page (page 1 with 5 items)
    assert result["total"] == 5
    assert result["page"] == 1
    assert len(result["items"]) == 5

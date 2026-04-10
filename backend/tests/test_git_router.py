"""
Tests for Git router endpoints with pagination.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, engine, Base
from app.models import Task, Project
from pathlib import Path
import subprocess
import tempfile
import shutil


@pytest.fixture
def client():
    """Create test client with authenticated session."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    tmp_dir = None

    try:
        # Create temporary git repository
        tmp_dir = tempfile.mkdtemp()
        repo_path = Path(tmp_dir) / "test-repo"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        subprocess.run(["git", "branch", "-m", "main"], cwd=repo_path, check=True, capture_output=True)

        # Create initial commit on main branch
        (repo_path / "README.md").write_text("# Test Repository")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )

        # Create worktree
        worktree_path = Path(tmp_dir) / "task-worktree"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", "test-branch"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )

        # Create 5 commits in worktree
        for i in range(5):
            (worktree_path / f"file{i}.txt").write_text(f"Content {i}")
            subprocess.run(["git", "add", "."], cwd=worktree_path, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"Commit {i}"],
                cwd=worktree_path,
                check=True,
                capture_output=True
            )

        # Create test project and task in database
        project = Project(
            id="test-project",
            name="Test",
            git_path=str(repo_path),
            main_branch="main"
        )
        db.add(project)
        task = Task(
            id="test-task",
            project_id="test-project",
            name="Test Task",
            branch_name="test-branch",
            worktree_path=str(worktree_path),
            tmux_session="test-session"
        )
        db.add(task)
        db.commit()

        # Create auth token
        from app.auth import create_access_token
        from app.models import Session as SessionModel
        from datetime import datetime, timedelta
        from app.config import settings

        token_data = {"sub": "user"}
        token = create_access_token(token_data)
        expires_at = datetime.utcnow() + timedelta(hours=settings.session_expire_hours)
        session = SessionModel(token=token, expires_at=expires_at)
        db.add(session)
        db.commit()

        headers = {"Authorization": f"Bearer {token}"}

        yield TestClient(app, headers=headers)

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        if tmp_dir and Path(tmp_dir).exists():
            shutil.rmtree(tmp_dir)


def test_get_commits_first_page(client):
    """Test fetching first page of commits via API."""
    response = client.get("/api/tasks/test-task/commits?page=1&page_size=2")

    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data

    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["total_pages"] == 3


def test_get_commits_default_parameters(client):
    """Test that defaults (page=1, page_size=30) work."""
    response = client.get("/api/tasks/test-task/commits")

    assert response.status_code == 200
    data = response.json()

    assert data["page"] == 1
    assert data["page_size"] == 30
    assert len(data["items"]) == 5  # Only 5 commits exist
    assert data["total"] == 5


def test_get_commits_second_page(client):
    """Test fetching second page with proper offset."""
    response = client.get("/api/tasks/test-task/commits?page=2&page_size=2")

    assert response.status_code == 200
    data = response.json()

    assert data["page"] == 2
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    # Most recent commits come first, so page 2 should have commits 2 and 1
    assert data["items"][0]["message"] == "Commit 2"
    assert data["items"][1]["message"] == "Commit 1"


def test_invalid_page_size(client):
    """Test that page_size over 100 is rejected."""
    response = client.get("/api/tasks/test-task/commits?page_size=150")

    assert response.status_code == 422


def test_invalid_page_zero(client):
    """Test that page=0 is rejected."""
    response = client.get("/api/tasks/test-task/commits?page=0")

    assert response.status_code == 422


def test_task_not_found(client):
    """Test that non-existent task returns 404."""
    response = client.get("/api/tasks/nonexistent-task/commits")

    assert response.status_code == 404


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary git repository for testing."""
    import subprocess
    from pathlib import Path

    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True,
        capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_path,
        check=True,
        capture_output=True
    )
    subprocess.run(["git", "branch", "-m", "main"], cwd=repo_path, check=True, capture_output=True)

    # Create initial commit on main branch
    (repo_path / "README.md").write_text("# Test Repository")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
        capture_output=True
    )

    yield str(repo_path)

    # Cleanup is handled by tmp_path fixture


def test_get_branches_endpoint_returns_branches(client, tmp_project):
    """
    Test that /api/git/branches endpoint returns branch list.
    """
    import subprocess
    from pathlib import Path

    # Create additional branches
    subprocess.run(["git", "branch", "develop"], cwd=tmp_project, check=True)

    response = client.get(f"/api/git/branches?path={tmp_project}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "main" in data["branches"]
    assert "develop" in data["branches"]
    assert data["current_branch"] == "main"


def test_get_branches_endpoint_handles_non_git(client, tmp_path):
    """
    Test that /api/git/branches returns error for non-git directory.
    """
    non_git = tmp_path / "non-git"
    non_git.mkdir()

    response = client.get(f"/api/git/branches?path={non_git}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["branches"] == []
    assert data["current_branch"] == ""

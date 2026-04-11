"""
Tests for changed files pagination endpoint.
"""
import os
import subprocess
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, engine, Base
from app.models import Session as SessionModel, Project, Task
from datetime import datetime, timedelta
from app.config import settings
from app.auth import create_access_token
import pytest
import uuid


@pytest.fixture
def git_repo_with_files(tmp_path):
    """Create a git repo with multiple changed files for testing."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Create git repo
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, capture_output=True)

        # Create and commit initial files
        for i in range(1, 51):
            (repo_dir / f"file{i}.txt").write_text(f"content {i}")
        subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, capture_output=True)

        # Modify files to create changes
        for i in range(1, 26):
            (repo_dir / f"file{i}.txt").write_text(f"modified content {i}")

        # Create session and project/task
        token_data = {"sub": "user", "jti": str(uuid.uuid4())}
        token = create_access_token(token_data)
        expires_at = datetime.utcnow() + timedelta(hours=settings.session_expire_hours)
        session = SessionModel(token=token, expires_at=expires_at)
        db.add(session)

        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            git_path=str(repo_dir),
            main_branch="main"
        )
        db.add(project)
        db.commit()

        task = Task(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="Test Task",
            branch_name="test-branch",
            worktree_path=str(repo_dir),
            tmux_session="test-session",
            status="active"
        )
        db.add(task)
        db.commit()

        headers = {"Authorization": f"Bearer {token}"}
        yield TestClient(app, headers=headers), task.id, repo_dir

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_pagination_no_files(tmp_path):
    """Test pagination when there are no changed files (total=0)."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Create clean git repo (no changes)
        repo_dir = tmp_path / "clean_repo"
        repo_dir.mkdir()
        subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, capture_output=True)
        (repo_dir / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, capture_output=True)

        # Create session and task
        token_data = {"sub": "user", "jti": str(uuid.uuid4())}
        token = create_access_token(token_data)
        expires_at = datetime.utcnow() + timedelta(hours=settings.session_expire_hours)
        session = SessionModel(token=token, expires_at=expires_at)
        db.add(session)

        project = Project(
            id=str(uuid.uuid4()),
            name="Clean Project",
            git_path=str(repo_dir),
            main_branch="main"
        )
        db.add(project)
        db.commit()

        task = Task(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="Clean Task",
            branch_name="clean-branch",
            worktree_path=str(repo_dir),
            tmux_session="clean-session",
            status="active"
        )
        db.add(task)
        db.commit()

        headers = {"Authorization": f"Bearer {token}"}
        client = TestClient(app, headers=headers)

        response = client.get(f"/api/tasks/{task.id}/changed-files")

        assert response.status_code == 200
        data = response.json()
        assert data["files"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert data["total_pages"] == 0

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_pagination_less_than_20_files(git_repo_with_files):
    """Test pagination with fewer than 20 files (no pagination needed)."""
    client, task_id, repo_dir = git_repo_with_files

    # Reset to have only 10 modified files
    subprocess.run(["git", "checkout", "."], cwd=repo_dir, capture_output=True)
    for i in range(1, 11):
        (repo_dir / f"file{i}.txt").write_text(f"modified {i}")

    response = client.get(f"/api/tasks/{task_id}/changed-files")

    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 10
    assert data["total"] == 10
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total_pages"] == 1


def test_pagination_exactly_20_files(git_repo_with_files):
    """Test pagination with exactly 20 files."""
    client, task_id, repo_dir = git_repo_with_files

    # Reset and modify exactly 20 files
    subprocess.run(["git", "checkout", "."], cwd=repo_dir, capture_output=True)
    for i in range(1, 21):
        (repo_dir / f"file{i}.txt").write_text(f"modified {i}")

    response = client.get(f"/api/tasks/{task_id}/changed-files")

    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 20
    assert data["total"] == 20
    assert data["total_pages"] == 1


def test_pagination_50_files(git_repo_with_files):
    """Test pagination with 50 files (3 pages)."""
    client, task_id, repo_dir = git_repo_with_files

    # We already have 25 modified files, add more
    for i in range(26, 51):
        (repo_dir / f"file{i}.txt").write_text(f"modified {i}")

    # Page 1
    response = client.get(f"/api/tasks/{task_id}/changed-files?page=1&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 20
    assert data["total"] == 50
    assert data["page"] == 1
    assert data["total_pages"] == 3

    # Page 2
    response = client.get(f"/api/tasks/{task_id}/changed-files?page=2&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 20
    assert data["page"] == 2

    # Page 3
    response = client.get(f"/api/tasks/{task_id}/changed-files?page=3&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 10  # Last page has 10 files
    assert data["page"] == 3


def test_pagination_invalid_page_number(git_repo_with_files):
    """Test pagination with invalid page number (negative, zero)."""
    client, task_id, repo_dir = git_repo_with_files

    # Page 0 should fail validation
    response = client.get(f"/api/tasks/{task_id}/changed-files?page=0&page_size=20")
    assert response.status_code == 422

    # Negative page should fail validation
    response = client.get(f"/api/tasks/{task_id}/changed-files?page=-1&page_size=20")
    assert response.status_code == 422


def test_pagination_page_size_limit(git_repo_with_files):
    """Test page_size limits (max 100)."""
    client, task_id, repo_dir = git_repo_with_files

    # Page size > 100 should fail
    response = client.get(f"/api/tasks/{task_id}/changed-files?page=1&page_size=150")
    assert response.status_code == 422

    # Page size = 100 should work
    response = client.get(f"/api/tasks/{task_id}/changed-files?page=1&page_size=100")
    assert response.status_code == 200
    data = response.json()
    assert data["page_size"] == 100
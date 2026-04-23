"""Tests for file hash endpoint."""
import os
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, engine, Base
from app.models import Session as SessionModel, Task, Project
from app.config import settings
from app.auth import create_access_token
import pytest


@pytest.fixture
def client(tmp_path):
    """Create test client with authenticated session."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Create test directory structure
        test_dir = tmp_path / "project"
        test_dir.mkdir()
        (test_dir / "src").mkdir()
        (test_dir / "subdir").mkdir()
        test_file = test_dir / "test.txt"
        test_file.write_text("Hello, World!")

        # Create session token with unique JWT ID
        token_data = {"sub": "user", "jti": str(uuid.uuid4())}
        token = create_access_token(token_data)

        # Store session in database
        expires_at = datetime.utcnow() + timedelta(hours=settings.session_expire_hours)
        session = SessionModel(
            token=token,
            expires_at=expires_at
        )
        db.add(session)

        # Create a project and task for the tests
        project = Project(
            id="test-project-id",
            name="Test Project",
            git_path=str(tmp_path / "repo"),
            main_branch="main"
        )
        db.add(project)

        task = Task(
            id="test-task-id",
            project_id="test-project-id",
            name="Test Task",
            branch_name="test-branch",
            worktree_path=str(test_dir),
            tmux_session="test-tmux-session"
        )
        db.add(task)

        db.commit()

        headers = {"Authorization": f"Bearer {token}"}

        yield TestClient(app, headers=headers), test_dir

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_get_file_hash_requires_auth(tmp_path):
    """Returns 401 without authentication."""
    test_dir = tmp_path / "project"
    test_dir.mkdir()

    client = TestClient(app)

    response = client.get("/api/tasks/test-task-id/files/test.txt/hash")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_get_file_hash_success(client):
    """Should return hash for existing file."""
    test_client, test_dir = client

    response = test_client.get("/api/tasks/test-task-id/files/test.txt/hash")

    assert response.status_code == 200
    data = response.json()
    assert "hash" in data
    assert data["hash"].startswith("sha256:")
    # SHA-256 hash of "Hello, World!" is 64 hex characters
    assert len(data["hash"]) == 71  # "sha256:" (7 chars) + 64 hex chars


def test_get_file_hash_not_found(client):
    """Should return 404 for non-existent file."""
    test_client, test_dir = client

    response = test_client.get("/api/tasks/test-task-id/files/nonexistent.txt/hash")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_file_hash_directory_returns_400(client):
    """Should return 400 for directory path."""
    test_client, test_dir = client

    response = test_client.get("/api/tasks/test-task-id/files/subdir/hash")

    assert response.status_code == 400
    assert "not a file" in response.json()["detail"].lower()


def test_get_file_hash_task_not_found(client):
    """Should return 404 for non-existent task."""
    test_client, test_dir = client

    response = test_client.get("/api/tasks/nonexistent-task/files/test.txt/hash")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_read_file_includes_hash(client):
    """Read endpoint should include hash in response."""
    test_client, test_dir = client

    response = test_client.get("/api/tasks/test-task-id/files/test.txt")

    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert "hash" in data
    assert data["hash"].startswith("sha256:")
    # Verify hash matches content
    import hashlib
    expected = "sha256:" + hashlib.sha256(b"Hello, World!").hexdigest()
    assert data["hash"] == expected

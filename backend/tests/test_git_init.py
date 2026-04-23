"""
Tests for git initialization in project creation.
"""
import subprocess
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, engine, Base
from app.models import Session as SessionModel
from datetime import datetime, timedelta
from app.config import settings
from app.auth import create_access_token
import pytest
import uuid


@pytest.fixture
def auth_token(tmp_path):
    """Create authenticated session token."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
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
        db.commit()

        yield token

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_create_project_with_git_init(tmp_path, auth_token):
    """Initialize git when init_git=True."""
    # Create test directory
    test_dir = tmp_path / "test_repo"
    test_dir.mkdir()

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    project_data = {
        "name": "Test Project",
        "git_path": str(test_dir),
        "main_branch": "main",
        "init_git": True
    }

    response = client.post("/api/projects", json=project_data, headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["git_path"] == str(test_dir)

    # Verify .git directory was created
    git_dir = test_dir / ".git"
    assert git_dir.exists()
    assert git_dir.is_dir()

    # Clean up
    subprocess.run(["rm", "-rf", str(test_dir)], capture_output=True)


def test_create_project_without_git_init_fails_for_non_git(tmp_path, auth_token):
    """Returns 400 when init_git=False and path not git repo."""
    # Create test directory (not a git repo)
    test_dir = tmp_path / "non_git_repo"
    test_dir.mkdir()

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    project_data = {
        "name": "Test Project",
        "git_path": str(test_dir),
        "main_branch": "main",
        "init_git": False
    }

    response = client.post("/api/projects", json=project_data, headers=headers)

    assert response.status_code == 400
    data = response.json()
    assert "detail" in data

    # Clean up
    subprocess.run(["rm", "-rf", str(test_dir)], capture_output=True)


def test_create_project_existing_git_repo_no_init_needed(tmp_path, auth_token):
    """Works with existing git repos without init."""
    # Create test directory and initialize git repo
    test_dir = tmp_path / "existing_repo"
    test_dir.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=str(test_dir), capture_output=True, check=True)

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    project_data = {
        "name": "Test Project",
        "git_path": str(test_dir),
        "main_branch": "main",
        "init_git": False
    }

    response = client.post("/api/projects", json=project_data, headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["git_path"] == str(test_dir)

    # Verify .git directory still exists
    git_dir = test_dir / ".git"
    assert git_dir.exists()

    # Clean up
    subprocess.run(["rm", "-rf", str(test_dir)], capture_output=True)

"""
Tests for filesystem router.
"""
import os
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
def client(tmp_path):
    """Create test client with authenticated session."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Create test directory structure
        test_dir = tmp_path / "project"
        test_dir.mkdir()
        (test_dir / "src").mkdir()
        (test_dir / "tests").mkdir()
        (test_dir / "README.md").write_text("# Test")

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

        headers = {"Authorization": f"Bearer {token}"}

        yield TestClient(app, headers=headers), test_dir

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_list_directories_requires_auth(tmp_path):
    """Returns 401 without authentication."""
    # Create test directory structure
    test_dir = tmp_path / "project"
    test_dir.mkdir()
    (test_dir / "src").mkdir()
    (test_dir / "tests").mkdir()

    client = TestClient(app)

    response = client.get(f"/api/filesystem/directories?path={test_dir}")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_list_directories_success(client):
    """Returns list of child directories with authentication."""
    test_client, test_dir = client

    response = test_client.get(f"/api/filesystem/directories?path={test_dir}")

    assert response.status_code == 200
    data = response.json()
    assert "directories" in data
    assert len(data["directories"]) == 2
    # Check that the full absolute paths are returned
    assert str(test_dir / "src") in data["directories"]
    assert str(test_dir / "tests") in data["directories"]


def test_list_directories_invalid_path(client):
    """Returns 400 for directory traversal paths."""
    test_client, test_dir = client

    # Try to access parent directory using ../
    response = test_client.get(f"/api/filesystem/directories?path={test_dir}/../sensitive")

    assert response.status_code == 400
    assert "detail" in response.json()

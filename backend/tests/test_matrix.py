"""
Tests for matrix router endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, engine, Base
from app.models import Project, Task, TaskStatus, Session as SessionModel
from app.auth import create_access_token
from datetime import datetime, timedelta
from app.config import settings


@pytest.fixture
def client():
    """Create test client with authentication"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Create auth token
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


@pytest.fixture
def sample_project(client):
    """Create a sample project for testing"""
    db = SessionLocal()
    project = Project(
        id="test-project-1",
        name="TestProject",
        git_path="/tmp/test_repo",
        main_branch="main"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project
    # Cleanup
    db.delete(project)
    db.commit()
    db.close()


@pytest.fixture
def sample_tasks(sample_project):
    """Create sample tasks for testing"""
    db = SessionLocal()
    tasks = []
    for i in range(3):
        task = Task(
            id=f"test-task-{i}",
            project_id=sample_project.id,
            name=f"Task{i}",
            branch_name=f"task-{i}-branch",
            worktree_path=f"/tmp/test_repo/worktrees/task{i}",
            tmux_session=f"v2d-task-{i}",
            status=TaskStatus.active
        )
        db.add(task)
        tasks.append(task)
    db.commit()
    for t in tasks:
        db.refresh(t)
    yield tasks
    # Cleanup
    for t in tasks:
        db.delete(t)
    db.commit()
    db.close()


def test_get_all_tasks(client, sample_tasks):
    """Test GET /api/tasks/all returns all tasks with project info"""
    response = client.get("/api/tasks/all")
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert len(data["tasks"]) >= 3
    for task in data["tasks"]:
        assert "id" in task
        assert "name" in task
        assert "project_id" in task
        assert "project_name" in task
        assert "status" in task


def test_get_all_tasks_unauthorized():
    """Test GET /api/tasks/all requires authentication"""
    unauthorized_client = TestClient(app)
    response = unauthorized_client.get("/api/tasks/all")
    assert response.status_code == 401


def test_create_matrix_sessions(client):
    """Test POST /api/matrix/sessions creates sessions"""
    response = client.post(
        "/api/matrix/sessions",
        json={"count": 4}
    )
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert len(data["sessions"]) == 4
    for session in data["sessions"]:
        assert "index" in session
        assert "session_name" in session
        assert "exists" in session
        assert session["session_name"].startswith("v2d-matrix-")


def test_create_matrix_sessions_unauthorized():
    """Test POST /api/matrix/sessions requires authentication"""
    unauthorized_client = TestClient(app)
    response = unauthorized_client.post("/api/matrix/sessions", json={"count": 4})
    assert response.status_code == 401
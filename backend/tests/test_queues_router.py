import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, engine, Base
from app.models import Task, Project

@pytest.fixture
def client():
    """Create test client"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Create test project and task
        project = Project(id="test-project", name="Test", git_path="/tmp/test")
        db.add(project)
        task = Task(
            id="test-task",
            project_id="test-project",
            name="Test Task",
            branch_name="test-branch",
            worktree_path="/tmp/test",
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

def test_get_queue_empty(client):
    """Test GET /api/tasks/{task_id}/queue when empty"""
    response = client.get("/api/tasks/test-task/queue")
    # This will fail because endpoint doesn't exist yet
    assert response.status_code == 200
    assert response.json() == []

def test_add_to_queue(client):
    """Test POST /api/tasks/{task_id}/queue"""
    response = client.post(
        "/api/tasks/test-task/queue",
        json={"content": "npm install"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "npm install"
    assert data["status"] == "pending"
    assert "id" in data

def test_remove_from_queue(client):
    """Test DELETE /api/tasks/{task_id}/queue/{message_id}"""
    # First add a message
    add_response = client.post(
        "/api/tasks/test-task/queue",
        json={"content": "to be deleted"}
    )
    message_id = add_response.json()["id"]

    # Then delete it
    response = client.delete(f"/api/tasks/test-task/queue/{message_id}")
    assert response.status_code == 204

def test_clear_queue(client):
    """Test DELETE /api/tasks/{task_id}/queue"""
    # Add multiple messages
    client.post("/api/tasks/test-task/queue", json={"content": "msg1"})
    client.post("/api/tasks/test-task/queue", json={"content": "msg2"})

    # Clear all
    response = client.delete("/api/tasks/test-task/queue")
    assert response.status_code == 204

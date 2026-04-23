import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Base, CommandQueue, CommandQueueStatus
from app.database import SessionLocal, engine

@pytest.fixture
def db_session():
    """Create a test database session"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def test_command_queue_creation(db_session: Session):
    """Test that CommandQueue model can be created with all fields"""
    queue = CommandQueue(
        task_id="test-task-1",
        content="echo 'hello world'",
        status=CommandQueueStatus.pending
    )
    db_session.add(queue)
    db_session.flush()  # Apply server_default for created_at

    assert queue.content == "echo 'hello world'"
    assert queue.status == CommandQueueStatus.pending
    assert queue.created_at is not None

def test_command_queue_status_enum():
    """Test that CommandQueueStatus enum has correct values"""
    assert CommandQueueStatus.pending.value == "pending"
    assert CommandQueueStatus.executing.value == "executing"
    assert CommandQueueStatus.completed.value == "completed"

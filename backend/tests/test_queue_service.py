import pytest
from sqlalchemy.orm import Session
from app.models import CommandQueue, CommandQueueStatus
from app.services.queue_service import QueueService

def test_get_queue_empty(db_session: Session):
    """Test getting queue when empty"""
    result = QueueService.get_queue(db_session, "nonexistent-task")
    assert result == []

def test_get_queue_with_items(db_session: Session):
    """Test getting queue with items"""
    queue = CommandQueue(
        task_id="task-1",
        content="echo 'test'",
        status=CommandQueueStatus.pending
    )
    db_session.add(queue)
    db_session.commit()

    result = QueueService.get_queue(db_session, "task-1")
    assert len(result) == 1
    assert result[0].content == "echo 'test'"

def test_add_message(db_session: Session):
    """Test adding a message to queue"""
    queue = QueueService.add_message(db_session, "task-1", "npm test")
    assert queue.id is not None
    assert queue.content == "npm test"
    assert queue.status == CommandQueueStatus.pending

def test_remove_message(db_session: Session):
    """Test removing a message from queue"""
    queue = QueueService.add_message(db_session, "task-1", "echo 'test'")
    result = QueueService.remove_message(db_session, "task-1", queue.id)
    assert result is True

    # Verify it's gone
    queues = QueueService.get_queue(db_session, "task-1")
    assert len(queues) == 0

def test_clear_queue(db_session: Session):
    """Test clearing all messages from queue"""
    QueueService.add_message(db_session, "task-1", "cmd1")
    QueueService.add_message(db_session, "task-1", "cmd2")
    QueueService.add_message(db_session, "task-1", "cmd3")

    count = QueueService.clear_queue(db_session, "task-1")
    assert count == 3

    queues = QueueService.get_queue(db_session, "task-1")
    assert len(queues) == 0

def test_get_next_pending(db_session: Session):
    """Test getting next pending message"""
    QueueService.add_message(db_session, "task-1", "first")
    QueueService.add_message(db_session, "task-1", "second")

    next_msg = QueueService.get_next_pending(db_session, "task-1")
    assert next_msg is not None
    assert next_msg.content == "first"

def test_mark_executing(db_session: Session):
    """Test marking message as executing"""
    queue = QueueService.add_message(db_session, "task-1", "test")
    result = QueueService.mark_executing(db_session, queue.id)
    assert result is True

    db_session.refresh(queue)
    assert queue.status == CommandQueueStatus.executing

def test_mark_completed(db_session: Session):
    """Test marking message as completed"""
    queue = QueueService.add_message(db_session, "task-1", "test")
    QueueService.mark_executing(db_session, queue.id)

    result = QueueService.mark_completed(db_session, queue.id)
    assert result is True

    db_session.refresh(queue)
    assert queue.status == CommandQueueStatus.completed
    assert queue.executed_at is not None

def test_mark_pending(db_session: Session):
    """Test marking message as pending (for retry)"""
    queue = QueueService.add_message(db_session, "task-1", "test")
    QueueService.mark_executing(db_session, queue.id)

    result = QueueService.mark_pending(db_session, queue.id)
    assert result is True

    db_session.refresh(queue)
    assert queue.status == CommandQueueStatus.pending
    assert queue.executed_at is None

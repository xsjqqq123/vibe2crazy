import pytest
import tempfile
from unittest.mock import Mock
from app.services.task_monitor_service import TaskMonitorService
from app.services.queue_service import QueueService
from app.services.tmux_service import TmuxService
from app.models import Task, CommandQueueStatus, Project, TaskStatusType
from app.database import SessionLocal, Base, engine


@pytest.fixture
def monitor():
    return TaskMonitorService()


def test_execute_next_queued_message_pending(monitor):
    """Test executing next pending message when idle"""
    # This will fail because execute_next_queued_message doesn't exist
    mock_task = Mock(id="test-task", tmux_session="test-session")
    mock_db = Mock()

    result = monitor.execute_next_queued_message(mock_task, mock_db)
    # Should not crash, return None if no pending messages
    assert result is None


def test_queue_execution_integration(monitor):
    """Integration test: queue message executes when idle"""
    # Setup database
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Create test project and task
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(id="test-project-queue", name="Test", git_path=tmpdir)
            db.add(project)

            # Create tmux session
            session_name = "test-queue-session"
            TmuxService.create_session(session_name, tmpdir)

            task = Task(
                id="test-task-queue",
                project_id="test-project-queue",
                name="Test Task",
                branch_name="test-branch",
                worktree_path=tmpdir,
                tmux_session=session_name,
                task_status=TaskStatusType.idle
            )
            db.add(task)
            db.commit()

            # Add message to queue
            queue = QueueService.add_message(db, task.id, "echo 'queue test'")
            db.commit()

            # Execute queue
            monitor.execute_next_queued_message(task, db)

            # Verify message was marked as executing
            db.refresh(queue)
            assert queue.status == CommandQueueStatus.executing

            # Clean up
            TmuxService.kill_session(session_name)

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

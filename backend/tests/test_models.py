"""
Tests for database models, focusing on Task status tracking fields.
"""
import pytest
from sqlalchemy import inspect
from app.models import Task, TaskStatusType, CodeStatusType, Base
from app.database import engine


class TestTaskStatusFields:
    """Test that Task model has new status tracking fields."""

    def test_task_has_task_status_column(self):
        """Verify Task model has task_status column."""
        mapper = inspect(Task)
        columns = [c.key for c in mapper.columns]

        assert 'task_status' in columns, "Task model should have task_status column"

    def test_task_has_code_status_column(self):
        """Verify Task model has code_status column."""
        mapper = inspect(Task)
        columns = [c.key for c in mapper.columns]

        assert 'code_status' in columns, "Task model should have code_status column"

    def test_task_has_last_task_status_check_column(self):
        """Verify Task model has last_task_status_check column."""
        mapper = inspect(Task)
        columns = [c.key for c in mapper.columns]

        assert 'last_task_status_check' in columns, "Task model should have last_task_status_check column"

    def test_task_has_last_code_status_check_column(self):
        """Verify Task model has last_code_status_check column."""
        mapper = inspect(Task)
        columns = [c.key for c in mapper.columns]

        assert 'last_code_status_check' in columns, "Task model should have last_code_status_check column"


class TestTaskStatusTypeEnum:
    """Test TaskStatusType enum values."""

    def test_task_status_type_has_running(self):
        """Verify TaskStatusType has running value."""
        assert TaskStatusType.running.value == "running"

    def test_task_status_type_has_idle(self):
        """Verify TaskStatusType has idle value."""
        assert TaskStatusType.idle.value == "idle"


class TestCodeStatusTypeEnum:
    """Test CodeStatusType enum values."""

    def test_code_status_type_has_pending_review(self):
        """Verify CodeStatusType has pending_review value."""
        assert CodeStatusType.pending_review.value == "pending_review"

    def test_code_status_type_has_ready_to_merge(self):
        """Verify CodeStatusType has ready_to_merge value."""
        assert CodeStatusType.ready_to_merge.value == "ready_to_merge"

    def test_code_status_type_has_no_changes(self):
        """Verify CodeStatusType has no_changes value."""
        assert CodeStatusType.no_changes.value == "no_changes"


class TestTaskStatusDefaults:
    """Test default values for new status fields."""

    def test_task_status_defaults_to_idle(self, db_session):
        """Verify task_status defaults to idle when saved to database."""
        # Create a task with minimal required fields and save to database
        task = Task(
            project_id="test-project",
            name="Test Task",
            branch_name="feature/test-task",
            worktree_path="/tmp/test",
            tmux_session="v2d-test-task"
        )
        db_session.add(task)
        db_session.flush()  # Flush to apply defaults

        assert task.task_status == TaskStatusType.idle, "task_status should default to idle"
        assert task.code_status == CodeStatusType.no_changes, "code_status should default to no_changes"

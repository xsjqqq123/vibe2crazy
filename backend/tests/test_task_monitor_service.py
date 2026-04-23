import pytest
from app.services.task_monitor_service import TaskMonitorService
from app.models import TaskStatusType, CodeStatusType

def test_task_monitor_service_initializes():
    """Test that TaskMonitorService initializes correctly"""
    monitor = TaskMonitorService()
    assert monitor.content_hashes == {}
    assert hasattr(monitor, '_hash_lock')  # Thread lock exists

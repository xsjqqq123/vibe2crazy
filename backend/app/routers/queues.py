import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import CommandQueue
from app.schemas import CommandQueueCreate, CommandQueueResponse
from app.services.queue_service import QueueService

router = APIRouter(prefix="/tasks/{task_id}/queue", tags=["queue"])
logger = logging.getLogger(__name__)


@router.get("", response_model=List[CommandQueueResponse])
def get_queue(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Get all messages in the queue for a task

    Args:
        task_id: Task identifier
        db: Database session

    Returns:
        List of queued messages ordered by creation time
    """
    queues = QueueService.get_queue(db, task_id)
    return queues


@router.post("", response_model=CommandQueueResponse, status_code=201)
def add_to_queue(
    task_id: str,
    message: CommandQueueCreate,
    db: Session = Depends(get_db)
):
    """
    Add a message to the queue

    Args:
        task_id: Task identifier
        message: Message content
        db: Database session

    Returns:
        Created queue item
    """
    try:
        queue = QueueService.add_message(db, task_id, message.content)
        return queue
    except Exception as e:
        logger.error(f"Failed to add message to queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{message_id}", status_code=204)
def remove_from_queue(
    task_id: str,
    message_id: str,
    db: Session = Depends(get_db)
):
    """
    Remove a message from the queue

    Args:
        task_id: Task identifier (for validation)
        message_id: Message identifier to remove
        db: Database session
    """
    success = QueueService.remove_message(db, task_id, message_id)
    if not success:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return None


@router.delete("", status_code=204)
def clear_queue(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Clear all messages from the queue

    Args:
        task_id: Task identifier
        db: Database session

    Returns:
        Number of messages cleared
    """
    count = QueueService.clear_queue(db, task_id)
    return None

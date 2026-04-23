import logging
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models import CommandQueue, CommandQueueStatus

logger = logging.getLogger(__name__)


class QueueService:
    """Service for managing command queue operations"""

    @staticmethod
    def get_queue(db: Session, task_id: str) -> List[CommandQueue]:
        """
        Get all queue items for a task, ordered by creation time
        Args:
            db: Database session
            task_id: Task identifier
        Returns:
            List of CommandQueue objects ordered by created_at ASC
        """
        try:
            return db.query(CommandQueue)\
                .filter(CommandQueue.task_id == task_id)\
                .order_by(CommandQueue.created_at.asc())\
                .all()
        except Exception as e:
            logger.error(f"Failed to get queue for task {task_id}: {e}")
            raise

    @staticmethod
    def add_message(db: Session, task_id: str, content: str) -> CommandQueue:
        """
        Add a new message to the queue
        Args:
            db: Database session
            task_id: Task identifier
            content: Message content (multi-line supported)
        Returns:
            Created CommandQueue object
        """
        try:
            queue = CommandQueue(
                task_id=task_id,
                content=content,
                status=CommandQueueStatus.pending
            )
            db.add(queue)
            db.commit()
            db.refresh(queue)
            logger.info(f"Added message to queue for task {task_id}: {queue.id}")
            return queue
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to add message to queue for task {task_id}: {e}")
            raise

    @staticmethod
    def remove_message(db: Session, task_id: str, message_id: str) -> bool:
        """
        Remove a message from the queue
        Args:
            db: Database session
            task_id: Task identifier (for validation)
            message_id: Message identifier to remove
        Returns:
            True if removed, False if not found
        """
        try:
            queue = db.query(CommandQueue)\
                .filter(
                    and_(
                        CommandQueue.id == message_id,
                        CommandQueue.task_id == task_id
                    )
                )\
                .first()

            if not queue:
                return False

            db.delete(queue)
            db.commit()
            logger.info(f"Removed message {message_id} from queue")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to remove message {message_id} from queue: {e}")
            raise

    @staticmethod
    def clear_queue(db: Session, task_id: str) -> int:
        """
        Clear all messages from a task's queue
        Args:
            db: Database session
            task_id: Task identifier
        Returns:
            Number of messages cleared
        """
        try:
            count = db.query(CommandQueue)\
                .filter(CommandQueue.task_id == task_id)\
                .delete()
            db.commit()
            logger.info(f"Cleared {count} messages from queue for task {task_id}")
            return count
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to clear queue for task {task_id}: {e}")
            raise

    @staticmethod
    def get_next_pending(db: Session, task_id: str) -> Optional[CommandQueue]:
        """
        Get the next pending message from queue with row-level lock
        Args:
            db: Database session
            task_id: Task identifier
        Returns:
            Next pending CommandQueue or None
        """
        try:
            return db.query(CommandQueue)\
                .filter(
                    and_(
                        CommandQueue.task_id == task_id,
                        CommandQueue.status == CommandQueueStatus.pending
                    )
                )\
                .order_by(CommandQueue.created_at.asc())\
                .with_for_update()\
                .first()
        except Exception as e:
            logger.error(f"Failed to get next pending message for task {task_id}: {e}")
            raise

    @staticmethod
    def mark_executing(db: Session, message_id: str) -> bool:
        """
        Mark a message as executing
        Args:
            db: Database session
            message_id: Message identifier
        Returns:
            True if updated, False if not found
        """
        try:
            queue = db.query(CommandQueue)\
                .filter(CommandQueue.id == message_id)\
                .first()

            if not queue:
                return False

            queue.status = CommandQueueStatus.executing
            db.commit()
            logger.info(f"Marked message {message_id} as executing")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark message {message_id} as executing: {e}")
            raise

    @staticmethod
    def mark_completed(db: Session, message_id: str) -> bool:
        """
        Mark a message as completed
        Args:
            db: Database session
            message_id: Message identifier
        Returns:
            True if updated, False if not found
        """
        try:
            queue = db.query(CommandQueue)\
                .filter(CommandQueue.id == message_id)\
                .first()

            if not queue:
                return False

            queue.status = CommandQueueStatus.completed
            queue.executed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Marked message {message_id} as completed")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark message {message_id} as completed: {e}")
            raise

    @staticmethod
    def mark_pending(db: Session, message_id: str) -> bool:
        """
        Mark a message as pending (for retry)
        Args:
            db: Database session
            message_id: Message identifier
        Returns:
            True if updated, False if not found
        """
        try:
            queue = db.query(CommandQueue)\
                .filter(CommandQueue.id == message_id)\
                .first()

            if not queue:
                return False

            queue.status = CommandQueueStatus.pending
            queue.executed_at = None
            db.commit()
            logger.info(f"Marked message {message_id} as pending for retry")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark message {message_id} as pending: {e}")
            raise

import hashlib
import logging
import threading
import asyncio
import time
import subprocess
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import Task, Project, TaskStatus, TaskStatusType, CodeStatusType, CommandQueue, CommandQueueStatus
from sqlalchemy import and_
from app.services.tmux_service import TmuxService
from app.services.git_service import GitService
from app.services.queue_service import QueueService

logger = logging.getLogger(__name__)


class TaskMonitorService:
    """Background service to monitor task statuses"""

    POLL_INTERVAL = 10  # seconds
    IDLE_THRESHOLD = 45  # seconds
    RAW_WINDOW_SIZE = 1500  # characters to capture before removing newlines
    HASH_WINDOW_SIZE = 1000  # characters to hash after removing newlines
    NEWLINE_DELAY = 0.5  # seconds delay before sending newline

    def __init__(self):
        self.content_hashes = {}  # task_id -> (hash, first_seen_time)
        self._hash_lock = threading.Lock()  # Protect content_hashes for thread safety
        self._main_loop = None  # Main asyncio event loop (set from async context)

    def set_main_loop(self, loop):
        """Set the main event loop reference. Must be called from the async context."""
        self._main_loop = loop

    def _schedule_coroutine(self, coro_func, *args):
        """Schedule a coroutine on the main event loop (thread-safe).

        Pass the method and its args; we build the coroutine object
        inside this method so Python's await checker sees it is used.
        """
        if self._main_loop and self._main_loop.is_running():
            asyncio.run_coroutine_threadsafe(coro_func(*args), self._main_loop)
        else:
            logger.warning("Main event loop not available, skipping coroutine scheduling")

    async def _broadcast_queue_update(self, task_id: str):
        """Broadcast queue update via WebSocket"""
        try:
            from app.websocket.manager import manager
            await manager.broadcast_to_task(task_id, {
                "type": "queue_updated",
                "task_id": task_id
            })
            logger.debug(f"Broadcast queue_updated for task {task_id}")
        except Exception as e:
            logger.error(f"Failed to broadcast queue update for task {task_id}: {e}")

    def check_all_tasks(self):
        """Check and update status for all active tasks.

        Designed to be called from a thread pool (via asyncio.to_thread)
        so that the subprocess calls do not block the asyncio event loop.
        """
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            tasks = db.query(Task).filter(Task.status != TaskStatus.merged).all()

            for task in tasks:
                self.update_task_status(task, db)
                self.update_code_status(task, db)

            db.commit()
        finally:
            db.close()

    def update_task_status(self, task: Task, db: Session):
        """Update task running/idle status by monitoring tmux output"""
        # Capture last 100 lines from tmux
        success, content = TmuxService.capture_history(task.tmux_session)

        if not success:
            # Session doesn't exist or error - mark as idle
            task.task_status = TaskStatusType.idle
            task.last_task_status_check = datetime.now(timezone.utc)
            logger.debug(f"Task {task.id}: tmux capture failed, marking as idle")
            return

        # Calculate hash using size-independent approach:
        # 1. Take last RAW_WINDOW_SIZE characters
        # 2. Remove all newlines (which change with terminal resizing due to wrapping)
        # 3. Take last HASH_WINDOW_SIZE characters for hashing
        raw_window = content[-self.RAW_WINDOW_SIZE:] if len(content) >= self.RAW_WINDOW_SIZE else content
        stripped_content = raw_window.replace('\n', '')
        window_content = stripped_content[-self.HASH_WINDOW_SIZE:] if len(stripped_content) >= self.HASH_WINDOW_SIZE else stripped_content
        current_hash = hashlib.md5(window_content.encode()).hexdigest()

        # Track consecutive identical hashes (thread-safe)
        now = datetime.now(timezone.utc)
        with self._hash_lock:
            if task.id in self.content_hashes:
                prev_hash, first_seen = self.content_hashes[task.id]

                if current_hash == prev_hash:
                    # Content hasn't changed - check how long
                    elapsed = (now - first_seen).total_seconds()
                    if elapsed >= self.IDLE_THRESHOLD:
                        task.task_status = TaskStatusType.idle
                        logger.debug(f"Task {task.id}: idle for {elapsed:.0f}s")
                    else:
                        task.task_status = TaskStatusType.running
                        logger.debug(f"Task {task.id}: unchanged but not idle yet ({elapsed:.0f}s)")
                else:
                    # Content changed - reset tracking
                    self.content_hashes[task.id] = (current_hash, now)
                    task.task_status = TaskStatusType.running
                    logger.debug(f"Task {task.id}: content changed, marking as running")
            else:
                # First time seeing this task
                self.content_hashes[task.id] = (current_hash, now)
                task.task_status = TaskStatusType.running
                logger.debug(f"Task {task.id}: first check, marking as running")

        task.last_task_status_check = now

        # Execute next queued message if idle
        if task.task_status == TaskStatusType.idle:
            # Mark any executing messages as completed
            # (terminal became idle again after executing a command)
            executing_messages = db.query(CommandQueue)\
                .filter(
                    and_(
                        CommandQueue.task_id == task.id,
                        CommandQueue.status == CommandQueueStatus.executing
                    )
                )\
                .all()

            queue_updated = False
            for msg in executing_messages:
                QueueService.mark_completed(db, msg.id)
                logger.info(f"Task {task.id}: Marked message {msg.id} as completed")
                queue_updated = True

            # Broadcast queue update if status changed
            if queue_updated:
                self._schedule_coroutine(self._broadcast_queue_update, task.id)

            # Execute next pending message
            self.execute_next_queued_message(task, db)

    def update_code_status(self, task: Task, db: Session):
        """Update code status by checking git state"""
        project = db.query(Project).filter(Project.id == task.project_id).first()
        if not project:
            logger.warning(f"Task {task.id}: project not found")
            return

        try:
            # Check for uncommitted changes
            changed_files = GitService.get_changed_files(task.worktree_path, project.main_branch)
            has_uncommitted = len(changed_files) > 0

            # For direct_on_branch tasks, skip ready_to_merge status
            if task.direct_on_branch:
                if has_uncommitted:
                    task.code_status = CodeStatusType.pending_review
                    logger.debug(f"Task {task.id}: pending_review ({len(changed_files)} uncommitted files)")
                else:
                    task.code_status = CodeStatusType.no_changes
                    logger.debug(f"Task {task.id}: no_changes (direct on branch)")

                task.last_code_status_check = datetime.now(timezone.utc)
                return

            # Normal mode: check for commits ahead of main
            branch_status = GitService.get_branch_status(task.worktree_path)
            has_unmerged = branch_status["commits_ahead"] > 0

            # Determine code status (pending_review takes priority)
            if has_uncommitted:
                task.code_status = CodeStatusType.pending_review
                logger.debug(f"Task {task.id}: pending_review ({len(changed_files)} uncommitted files)")
            elif has_unmerged:
                task.code_status = CodeStatusType.ready_to_merge
                logger.debug(f"Task {task.id}: ready_to_merge ({branch_status['commits_ahead']} commits ahead)")
            else:
                task.code_status = CodeStatusType.no_changes
                logger.debug(f"Task {task.id}: no_changes")

            task.last_code_status_check = datetime.now(timezone.utc)

        except Exception as e:
            logger.error(f"Task {task.id}: error updating code status: {e}")
            # Don't crash the monitoring loop

    async def _send_newline_delayed(self, session_name: str, message_id: str, task_id: str):
        """
        Send newline to tmux session after a delay.
        Runs on the main event loop; the subprocess call is offloaded to a thread.
        """
        await asyncio.sleep(self.NEWLINE_DELAY)
        # Run the blocking tmux send_keys in a thread to avoid blocking the event loop
        newline_success = await asyncio.to_thread(
            TmuxService.send_keys, session_name, "C-m"
        )
        if newline_success:
            logger.info(f"Task {task_id}: Sent newline for message {message_id}")
        else:
            logger.warning(f"Task {task_id}: Failed to send newline for message {message_id}")
            # Mark as pending for retry
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                QueueService.mark_pending(db, message_id)
                # Broadcast queue update
                await self._broadcast_queue_update(task_id)
            finally:
                db.close()

    def execute_next_queued_message(self, task: Task, db: Session):
        """
        Execute next message from queue when terminal is idle

        Args:
            task: Task object
            db: Database session
        """
        from app.models import TaskStatusType

        # Only execute if task is idle
        if task.task_status != TaskStatusType.idle:
            return

        # Get next pending message with row-level lock
        message = QueueService.get_next_pending(db, task.id)
        if not message:
            # No pending messages
            return

        logger.info(f"Task {task.id}: Executing queued message {message.id}")

        # Mark as executing
        if not QueueService.mark_executing(db, message.id):
            logger.warning(f"Task {task.id}: Failed to mark message {message.id} as executing")
            return

        # Broadcast queue update - message now executing
        self._schedule_coroutine(self._broadcast_queue_update, task.id)

        # Send content first
        success, _ = TmuxService.send_keys(
            task.tmux_session,
            message.content
        )

        if success:
            logger.info(f"Task {task.id}: Sent message {message.id} content to tmux")
            # Schedule newline to be sent with delay on the main event loop
            self._schedule_coroutine(
                self._send_newline_delayed, task.tmux_session, message.id, task.id
            )
        else:
            logger.warning(f"Task {task.id}: Failed to send message {message.id} content to tmux")
            # Mark as pending for retry
            QueueService.mark_pending(db, message.id)

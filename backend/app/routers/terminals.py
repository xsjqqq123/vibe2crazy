import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Task
from app.auth import require_auth
from app.services.tmux_service import TmuxService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/terminals", tags=["terminals"])


@router.get("/{task_id}/history", response_class=PlainTextResponse)
async def get_terminal_history(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Get terminal history from tmux session"""
    logger.debug(f"Fetching terminal history for task {task_id}")

    # Get task from database
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        logger.warning(f"Task {task_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Capture history from tmux session
    success, content = TmuxService.capture_history(task.tmux_session)

    if not success:
        logger.error(f"Failed to capture terminal history for task {task_id}: {content}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=content
        )

    logger.debug(f"Terminal history captured for task {task_id}: {len(content)} characters")
    return content

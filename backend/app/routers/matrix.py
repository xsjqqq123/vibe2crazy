"""
Matrix router for terminal matrix view endpoints.
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import Project, Task
from app.auth import require_auth
from app.services.tmux_service import TmuxService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["matrix"])


class MatrixSessionsRequest(BaseModel):
    count: int


class MatrixSessionInfo(BaseModel):
    index: int
    session_name: str
    exists: bool


@router.get("/tasks/all")
async def get_all_tasks(
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """Get all tasks across all projects for matrix view"""
    logger.info("Fetching all tasks for matrix view")

    tasks = db.query(Task).join(Project).order_by(
        Project.name,
        Task.created_at
    ).all()

    result = []
    for task in tasks:
        project = task.project
        result.append({
            "id": task.id,
            "name": task.name,
            "project_id": task.project_id,
            "project_name": project.name if project else "",
            "status": task.task_status.value if task.task_status else "idle",
            "tmux_session": task.tmux_session
        })

    logger.info(f"Found {len(result)} tasks")
    return {"tasks": result}


@router.post("/matrix/sessions")
async def create_matrix_sessions(
    request: MatrixSessionsRequest,
    current_user = Depends(require_auth)
):
    """Create or verify matrix terminal sessions"""
    logger.info(f"Creating/verifying {request.count} matrix sessions")

    sessions = []
    for i in range(1, request.count + 1):
        session_name = f"v2d-matrix-{i}"
        exists = TmuxService.session_exists(session_name)

        if not exists:
            success, msg = TmuxService.create_session(session_name, "~")
            if not success:
                logger.error(f"Failed to create matrix session {session_name}: {msg}")
                # Continue anyway, session might be created on reconnect

        sessions.append({
            "index": i,
            "session_name": session_name,
            "exists": exists or TmuxService.session_exists(session_name)
        })

    logger.info(f"Prepared {len(sessions)} matrix sessions")
    return {"sessions": sessions}
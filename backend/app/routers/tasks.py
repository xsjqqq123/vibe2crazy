import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Project, Task, TaskStatus, TaskStatusType, CodeStatusType
from app.schemas import TaskCreate, TaskUpdate, TaskResponse, TaskStatusResponse, AcceptRequest, AcceptResponse
from app.auth import require_auth
from app.services.git_service import GitService
from app.services.tmux_service import TmuxService
from app.config import settings
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects/{project_id}/tasks", tags=["tasks"])


def generate_branch_name(task_name: str) -> str:
    """Generate a branch name from task name"""
    # Convert to lowercase, replace spaces with hyphens, remove special chars
    branch = task_name.lower().replace(" ", "-")
    branch = "".join(c for c in branch if c.isalnum() or c == "-")
    # Add random suffix for uniqueness
    return f"{branch}-{uuid.uuid4().hex[:8]}"


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: str,
    task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: Project = Depends(require_auth)
):
    """Create a new task with git worktree and tmux session"""
    logger.info(f"Creating task '{task.name}' for project {project_id}")

    # Get project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        logger.warning(f"Task creation failed: Project {project_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Generate unique identifiers
    task_id = str(uuid.uuid4())
    tmux_session = f"{settings.tmux_session_prefix}{project.name}-{task_id}"

    logger.info(f"Task ID: {task_id}")
    logger.info(f"Tmux session: {tmux_session}")

    if task.direct_on_branch:
        # Direct on branch mode: work on main branch directly
        branch_name = f"direct-{project.main_branch}-{task_id[:8]}"
        worktree_path = project.git_path

        logger.info(f"Direct on branch mode")
        logger.info(f"Branch name: {branch_name}")
        logger.info(f"Worktree path: {worktree_path}")

        # Create tmux session only (no worktree/branch creation)
        logger.info(f"Creating tmux session: {tmux_session}")
        tmux_success, tmux_msg = TmuxService.create_session(tmux_session, worktree_path)
        if not tmux_success:
            logger.error(f"Failed to create tmux session: {tmux_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create tmux session: {tmux_msg}"
            )
        logger.info(f"Tmux session created successfully")
    else:
        # Normal mode: create new branch and worktree
        branch_name = generate_branch_name(task.name)

        # Create worktrees directory alongside the original repository
        repo_path = Path(project.git_path).resolve()
        worktrees_base = repo_path.parent / f"{repo_path.name}-worktrees"
        worktree_path = str((worktrees_base / branch_name).resolve())

        logger.info(f"Normal mode")
        logger.info(f"Branch name: {branch_name}")
        logger.info(f"Worktree path: {worktree_path}")

        # Create git worktree
        logger.info(f"Creating git worktree at {worktree_path}")
        worktree_success, worktree_msg = GitService.create_worktree(
            repo_path=project.git_path,
            branch_name=branch_name,
            worktree_path=worktree_path
        )

        if not worktree_success:
            logger.error(f"Failed to create worktree: {worktree_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create worktree: {worktree_msg}"
            )
        logger.info(f"Worktree created successfully")

        # Create tmux session
        logger.info(f"Creating tmux session: {tmux_session}")
        tmux_success, tmux_msg = TmuxService.create_session(tmux_session, worktree_path)
        if not tmux_success:
            logger.error(f"Failed to create tmux session: {tmux_msg}")
            # Rollback worktree creation
            GitService.delete_worktree(worktree_path, project.git_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create tmux session: {tmux_msg}"
            )
        logger.info(f"Tmux session created successfully")

    # Create task in database
    db_task = Task(
        id=task_id,
        project_id=project_id,
        name=task.name,
        branch_name=branch_name,
        worktree_path=worktree_path,
        tmux_session=tmux_session,
        status=TaskStatus.active,
        direct_on_branch=task.direct_on_branch
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    logger.info(f"Task '{task.name}' created successfully (ID: {task_id})")
    return db_task


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Project = Depends(require_auth)
):
    """List all tasks for a project"""
    tasks = db.query(Task).filter(Task.project_id == project_id).order_by(
        Task.created_at.desc()
    ).all()
    logger.debug(f"Listed {len(tasks)} tasks for project {project_id}")
    return tasks


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Project = Depends(require_auth)
):
    """Get a task by ID"""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.project_id == project_id
    ).first()
    if not task:
        logger.warning(f"Task {task_id} not found in project {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    project_id: str,
    task_update: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: Project = Depends(require_auth)
):
    """Update a task"""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.project_id == project_id
    ).first()
    if not task:
        logger.warning(f"Task {task_id} not found in project {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    old_status = task.status
    if task_update.name is not None:
        task.name = task_update.name

    if task_update.status is not None:
        task.status = task_update.status

    if task_update.extra_index_paths is not None:
        task.extra_index_paths = task_update.extra_index_paths

    db.commit()
    db.refresh(task)
    logger.info(f"Task {task_id} updated: status {old_status} -> {task.status}")
    return task

@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Project = Depends(require_auth)
):
    """Delete a task and cleanup resources"""
    logger.info(f"Deleting task {task_id} from project {project_id}")

    task = db.query(Task).filter(
        Task.id == task_id,
        Task.project_id == project_id
    ).first()
    if not task:
        logger.warning(f"Task {task_id} not found in project {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Protect direct tasks from deletion
    if task.direct_on_branch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default Direct task"
        )

    # Get project for worktree cleanup
    project = db.query(Project).filter(Project.id == project_id).first()

    # Kill tmux session
    logger.info(f"Killing tmux session: {task.tmux_session}")
    TmuxService.kill_session(task.tmux_session)

    # Only delete worktree for non-direct tasks
    if not task.direct_on_branch and project:
        logger.info(f"Deleting worktree: {task.worktree_path}")
        GitService.delete_worktree(task.worktree_path, project.git_path)

    # Delete from database
    db.delete(task)
    db.commit()

    logger.info(f"Task {task_id} deleted successfully")
    return {"success": True}


# Additional router for task operations without project_id prefix
task_router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@task_router.get("/{task_id}", response_model=TaskResponse)
async def get_task_by_id(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: Project = Depends(require_auth)
):
    """Get a task by ID"""
    logger.debug(f"Fetching task {task_id}")
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        logger.warning(f"Task {task_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    return task


@task_router.delete("/{task_id}")
async def delete_task_by_id(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: Project = Depends(require_auth)
):
    """Delete a task and cleanup resources"""
    logger.info(f"Deleting task {task_id} (direct access)")
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        logger.warning(f"Task {task_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Protect direct tasks from deletion
    if task.direct_on_branch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default Direct task"
        )

    # Get project for worktree cleanup
    project = db.query(Project).filter(Project.id == task.project_id).first()

    # Kill tmux session
    logger.info(f"Killing tmux session: {task.tmux_session}")
    TmuxService.kill_session(task.tmux_session)

    # Only delete worktree for non-direct tasks
    if not task.direct_on_branch and project:
        logger.info(f"Deleting worktree: {task.worktree_path}")
        GitService.delete_worktree(task.worktree_path, project.git_path)

    # Delete from database
    db.delete(task)
    db.commit()

    logger.info(f"Task {task_id} deleted successfully")
    return {"success": True}


@task_router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: Project = Depends(require_auth)
):
    """Get current task and code status"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        logger.warning(f"Task {task_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    return TaskStatusResponse(
        task_status=task.task_status,
        code_status=task.code_status,
        last_task_status_check=task.last_task_status_check,
        last_code_status_check=task.last_code_status_check
    )



@router.post("/{task_id}/accept", response_model=AcceptResponse)
async def accept_changes(
    task_id: str,
    accept_request: AcceptRequest,
    db: Session = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Accept and commit current changes in worktree without merging"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Commit all changes in the worktree
    commit_success, commit_message = GitService.auto_commit_worktree(
        worktree_path=task.worktree_path,
        message=accept_request.message or f"Accept changes for {task.name}"
    )

    if not commit_success:
        return AcceptResponse(
            success=False,
            message=commit_message,
            commit_hash=None
        )

    # Extract commit hash from message if available
    commit_hash = None
    if "(" in commit_message and ")" in commit_message:
        # Extract hash from "Committed changes (abc1234)"
        commit_hash = commit_message.split(")")[1].strip()

    # Update task status to active (this is what enables Merge button)
    task.status = TaskStatus.active
    db.commit()
    db.refresh(task)

    return AcceptResponse(
        success=True,
        message="Changes accepted and committed",
        commit_hash=commit_hash
    )


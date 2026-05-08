from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import subprocess
import logging
from pathlib import Path
from app.database import get_db
from app.models import Project
from app.schemas import ProjectCreate, ProjectUpdate, ProjectResponse
from app.auth import require_auth
from app.services.git_service import GitService
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _create_direct_task(db: Session, project_id: str, project_name: str, git_path: str) -> "Task":
    """Create the default Direct task for a newly created project."""
    import uuid
    from app.models import Task, TaskStatus
    from app.services.tmux_service import TmuxService
    from app.config import settings

    task_id = str(uuid.uuid4())
    branch_name = f"direct-{project_id[:8]}"
    tmux_session = f"{settings.tmux_session_prefix}{project_name}-{task_id}"

    # Create tmux session pointing to main repo
    tmux_success, tmux_msg = TmuxService.create_session(tmux_session, git_path)
    if not tmux_success:
        logger.warning(f"Failed to create tmux session for Direct task: {tmux_msg}")
        # Non-fatal: continue without tmux

    db_task = Task(
        id=task_id,
        project_id=project_id,
        name=project_name,
        branch_name=branch_name,
        worktree_path=git_path,
        tmux_session=tmux_session,
        status=TaskStatus.active,
        direct_on_branch=True
    )
    db.add(db_task)
    return db_task


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: Project = Depends(require_auth)
):
    """Create a new project"""
    # Check if directory exists
    project_path = Path(project.git_path)
    if not project_path.exists():
        if project.create_directory:
            # Create directory with parent directories if needed
            project_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {project.git_path}")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Directory does not exist: {project.git_path}"
            )

    # Check if git repository exists
    is_git_repo = GitService.is_git_repository(project.git_path)

    # Initialize git if needed
    if not is_git_repo and project.init_git:
        logger.info(f"Initializing git repository at {project.git_path}")
        result = subprocess.run(
            ["git", "init"],
            cwd=project.git_path,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            logger.error(f"Git init failed: {result.stderr}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize git repository: {result.stderr}"
            )

        # Rename initial branch to configured default branch name
        branch_result = subprocess.run(
            ["git", "branch", "-M", settings.git_default_branch],
            cwd=project.git_path,
            capture_output=True,
            text=True
        )
        if branch_result.returncode != 0:
            logger.warning(f"Failed to rename initial branch: {branch_result.stderr}")

        # Create initial commit to ensure branch is not empty
        # This is required for worktree creation and merge operations to work correctly
        init_commit_result = subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "Initial commit"],
            cwd=project.git_path,
            capture_output=True,
            text=True
        )
        if init_commit_result.returncode != 0:
            logger.warning(f"Failed to create initial commit: {init_commit_result.stderr}")

        logger.info(f"Git repository initialized successfully at {project.git_path}")
        is_git_repo = True

    # Validate git repository exists
    if not is_git_repo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path is not a git repository. Enable git initialization or select a different directory."
        )

    # Check if project name already exists
    existing = db.query(Project).filter(Project.name == project.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project name already exists"
        )

    # Get default branch if not specified or empty
    main_branch = project.main_branch
    if not main_branch or main_branch == settings.git_default_branch:
        main_branch = GitService.get_default_branch(project.git_path)

    # Create project
    db_project = Project(
        name=project.name,
        git_path=project.git_path,
        main_branch=main_branch
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    # Auto-create the default Direct task
    _create_direct_task(db, db_project.id, db_project.name, db_project.git_path)
    db.commit()

    return db_project


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    db: Session = Depends(get_db),
    current_user: Project = Depends(require_auth)
):
    """List all projects"""
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Project = Depends(require_auth)
):
    """Get a project by ID"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: Project = Depends(require_auth)
):
    """Update a project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    if project_update.name is not None:
        # Check if new name already exists
        existing = db.query(Project).filter(
            Project.name == project_update.name,
            Project.id != project_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project name already exists"
            )
        project.name = project_update.name

    if project_update.main_branch is not None:
        project.main_branch = project_update.main_branch

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Project = Depends(require_auth)
):
    """Delete a project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    db.delete(project)
    db.commit()

    return {"success": True}

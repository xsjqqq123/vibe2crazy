import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import Task, Project
from app.schemas import MergeRequest, MergeResponse, AcceptRequest, AcceptResponse, CommitSchema, CommitDiffSchema, PaginatedCommitsSchema, CommandExecution
from app.auth import require_auth
from app.services.git_service import GitService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["git"])


class BranchResponse(BaseModel):
    branch: str
    success: bool
    message: str | None = None


class BranchListResponse(BaseModel):
    branches: List[str]
    current_branch: str
    success: bool
    message: str | None = None


class ResetRequest(BaseModel):
    commit_hash: str
    include_commit: bool = False


class ResetResponse(BaseModel):
    success: bool
    message: str


branch_router = APIRouter(prefix="/api/git", tags=["git"])


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
        start = commit_message.rfind("(") + 1
        end = commit_message.rfind(")")
        commit_hash = commit_message[start:end]

    return AcceptResponse(
        success=True,
        message=commit_message,
        commit_hash=commit_hash
    )


@router.get("/{task_id}/commits", response_model=PaginatedCommitsSchema)
async def get_worktree_commits(
    task_id: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(30, ge=1, le=100, description="Number of items per page"),
    db: Session = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Get paginated list of commits for a task worktree.

    For normal tasks: Returns commits ahead of the main branch.
    For direct_on_branch tasks: Returns recent commits on the current branch.
    """
    # Get task with project
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Calculate offset
    offset = (page - 1) * page_size

    # Get paginated commits
    result = GitService.get_worktree_commits_paginated(
        worktree_path=task.worktree_path,
        main_branch=task.project.main_branch,
        offset=offset,
        limit=page_size,
        direct_on_branch=task.direct_on_branch
    )

    return result


@router.post("/{task_id}/merge", response_model=MergeResponse)
async def merge_task(
    task_id: str,
    merge_request: MergeRequest,
    db: Session = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Merge task branch to main"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Check for uncommitted changes first
    changed_files = GitService.get_changed_files(task.worktree_path, project.main_branch)
    if changed_files:
        return MergeResponse(
            success=False,
            message=f"Please accept changes first. Found {len(changed_files)} uncommitted file(s).",
            conflicts=None
        )

    # Capture worktree's current HEAD commit BEFORE sync and merge
    # This ensures we capture the user's actual commit, not a sync merge commit
    worktree_last_hash = GitService.get_latest_commit_hash(task.worktree_path)
    logger.info(f"[Merge {task_id}] Captured worktree last commit: {worktree_last_hash}")

    # Validate worktree hash was captured successfully
    if not worktree_last_hash:
        logger.error(f"[Merge {task_id}] Failed to get worktree commit hash")
        return MergeResponse(
            success=False,
            message="Failed to get worktree commit hash. Please check if the worktree has commits.",
            conflicts=None
        )

    # NEW: Track all command executions for debugging
    execution_log: List[CommandExecution] = []

    # NEW: Sync main into worktree first
    logger.info(f"[Merge {task_id}] Syncing {project.main_branch} into worktree")
    sync_success, sync_msg, has_conflicts, conflict_files = GitService.sync_main_into_worktree(
        worktree_path=task.worktree_path,
        main_branch=project.main_branch,
        execution_log=execution_log
    )

    if has_conflicts:
        logger.warning(f"[Merge {task_id}] Sync has conflicts: {conflict_files}")
        return MergeResponse(
            success=False,
            message=f"Conflicts detected during sync:\n" + "\n".join(conflict_files),
            conflicts="\n".join(conflict_files),
            needs_resolution=True,
            execution_log=execution_log
        )

    if not sync_success and "Already up to date" not in sync_msg and "Sync successful" not in sync_msg:
        # Sync failed for reasons other than "already up to date"
        logger.error(f"[Merge {task_id}] Sync failed: {sync_msg}")
        return MergeResponse(
            success=False,
            message=f"Sync failed: {sync_msg}",
            conflicts=None,
            execution_log=execution_log
        )

    # Sync successful (or already up to date) - proceed with squash merge
    logger.info(f"[Merge {task_id}] Sync successful, proceeding with merge to main")

    # Perform squash merge (only committed changes)
    logger.info(f"[Merge {task_id}] Starting merge of branch '{task.branch_name}' into '{project.main_branch}'")

    merge_success, merge_message, conflicts = GitService.squash_merge(
        repo_path=project.git_path,
        branch_name=task.branch_name,
        message=merge_request.message,
        target_branch=project.main_branch,
        execution_log=execution_log
    )

    logger.info(f"[Merge {task_id}] squash_merge returned: success={merge_success}, message='{merge_message}', conflicts={conflicts is not None}")

    if not merge_success:
        logger.warning(f"[Merge {task_id}] Merge FAILED, returning error response to user")
        return MergeResponse(
            success=False,
            message=merge_message,
            conflicts=conflicts,
            execution_log=execution_log
        )

    task.last_merge_commit_hash = worktree_last_hash
    task.status = "active"  # Reset to active so task can continue working
    logger.info(f"[Merge {task_id}] Updating database: last_merge_hash={worktree_last_hash}, status=active")

    db.commit()
    logger.info(f"[Merge {task_id}] Database committed successfully")

    return MergeResponse(
        success=True,
        message=merge_message
    )


@router.delete("/{task_id}/branch")
async def delete_branch(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Delete task branch"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    success, message = GitService.delete_branch(project.git_path, task.branch_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return {"success": True, "message": message}


@router.get("/{task_id}/commits/{commit_hash}/diff", response_model=CommitDiffSchema)
async def get_commit_diff(
    task_id: str,
    commit_hash: str,
    db: Session = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Get file changes for a specific commit"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    result = GitService.get_commit_diff(
        worktree_path=task.worktree_path,
        commit_hash=commit_hash
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get commit diff: {result.get('error', 'Unknown error')}"
        )

    return CommitDiffSchema(
        hash=result.get("hash", commit_hash[:8]),
        date=result.get("date", ""),
        message=result.get("message", ""),
        files=result.get("files", [])
    )


@router.post("/{task_id}/reset", response_model=ResetResponse)
async def reset_to_commit(
    task_id: str,
    reset_request: ResetRequest,
    db: Session = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Reset task worktree to a specific commit (mixed reset)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    success, message = GitService.reset_to_commit(
        worktree_path=task.worktree_path,
        commit_hash=reset_request.commit_hash,
        include_commit=reset_request.include_commit
    )

    return ResetResponse(success=success, message=message)


@branch_router.get("/branch", response_model=BranchResponse)
async def get_branch(
    path: str = Query(..., description="Path to the git repository"),
    current_user: Task = Depends(require_auth)
):
    """Get the current branch name of a git repository"""
    try:
        branch = GitService.get_default_branch(path)
        return BranchResponse(branch=branch, success=True, message=None)
    except Exception as e:
        return BranchResponse(
            branch="",
            success=False,
            message=f"Failed to detect branch: {str(e)}"
        )


@branch_router.get("/branches", response_model=BranchListResponse)
async def get_branches(
    path: str = Query(..., description="Path to the git repository"),
    current_user: Task = Depends(require_auth)
):
    """Get all local branches and current branch for a git repository"""
    try:
        branches, current_branch = GitService.get_local_branches(path)
        if not branches and not current_branch:
            return BranchListResponse(
                branches=[],
                current_branch="",
                success=False,
                message="Failed to get branches: not a git repository or no branches found"
            )
        return BranchListResponse(
            branches=branches,
            current_branch=current_branch,
            success=True,
            message=None
        )
    except Exception as e:
        logger.error(f"Error getting branches: {e}")
        return BranchListResponse(
            branches=[],
            current_branch="",
            success=False,
            message=f"Failed to get branches: {str(e)}"
        )

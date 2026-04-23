# backend/app/routers/symbols.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Task
from app.schemas import (
    IndexRequest, IndexResponse, IndexProgress,
    SymbolDefinitionResponse, SymbolMatchItem,
    SymbolDetailRequest
)
from app.auth import require_auth
from app.services.ctags_service import get_ctags_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


@router.post("/index", response_model=IndexResponse)
async def start_index(
    request: IndexRequest,
    db: Session = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Start an asynchronous indexing job for the task's worktree"""
    # Get task to find worktree_path
    task = db.query(Task).filter(Task.id == request.task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    if not task.worktree_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task has no worktree path"
        )

    # Parse extra_index_paths if set
    extra_paths = []
    if task.extra_index_paths:
        extra_paths = [p.strip() for p in task.extra_index_paths.split(";") if p.strip()]

    ctags_service = get_ctags_service()
    job = ctags_service.start_index_job(
        task_id=request.task_id,
        worktree_path=task.worktree_path,
        force=request.force,
        extra_paths=extra_paths
    )

    response = IndexResponse(
        job_id=job.job_id,
        status=job.status.value,
        cached=job.cached,
        indexed_files=job.indexed_files,
        indexed_symbols=job.indexed_symbols,
        duration_seconds=job.duration_seconds,
        error=job.error,
        suggestion=job.suggestion
    )

    if job.status.value == "failed":
        response.message = job.error
    elif job.cached:
        response.message = "Using cached index"
    else:
        response.message = "Indexing started"

    return response


@router.get("/index/status", response_model=IndexResponse)
async def get_index_status(
    job_id: str = Query(..., description="The job identifier"),
    current_user: Task = Depends(require_auth)
):
    """Get the status of an indexing job"""
    ctags_service = get_ctags_service()
    job = ctags_service.get_job_status(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    response = IndexResponse(
        job_id=job.job_id,
        status=job.status.value,
        cached=job.cached,
        indexed_files=job.indexed_files,
        indexed_symbols=job.indexed_symbols,
        duration_seconds=job.duration_seconds,
        error=job.error,
        suggestion=job.suggestion
    )

    return response


@router.get("/definition", response_model=SymbolDefinitionResponse)
async def get_symbol_definition(
    symbol_name: str = Query(..., description="Name of the symbol to look up"),
    file_path: str = Query("", description="Current file path for context"),
    task_id: str = Query(..., description="Task identifier"),
    db: Session = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Get symbol definition details"""
    # Get task to find worktree_path
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    if not task.worktree_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task has no worktree path"
        )

    ctags_service = get_ctags_service()
    result = ctags_service.find_symbol(
        worktree_path=task.worktree_path,
        symbol_name=symbol_name,
        context_file=file_path
    )

    # Convert definition_snippet from string to list of strings
    definition_snippet = None
    if result.definition_snippet:
        definition_snippet = result.definition_snippet.split('\n')

    # Convert similar_symbols from List[SymbolMatch] to List[str] (names only)
    similar_symbols = None
    if result.similar_symbols:
        similar_symbols = [s.name for s in result.similar_symbols[:5]]

    # Convert matches from List[SymbolMatch] to List[SymbolMatchItem]
    matches = None
    if result.matches:
        matches = [
            SymbolMatchItem(
                file_path=m.file_path,
                line_number=m.line_number,
                kind=m.kind,
                signature=m.signature
            ) for m in result.matches
        ]

    return SymbolDefinitionResponse(
        found=result.found,
        name=result.name,
        kind=result.kind,
        file_path=result.file_path,
        line_number=result.line_number,
        type_signature=result.type_signature,
        signature_file_path=result.signature_file_path,
        signature_line_number=result.signature_line_number,
        docstring=result.docstring,
        definition_snippet=definition_snippet,
        snippet_highlight_index=result.snippet_highlight_index,
        reason=result.reason,
        message=result.message,
        similar_symbols=similar_symbols,
        matches=matches
    )


@router.get("/detail", response_model=SymbolDefinitionResponse)
async def get_symbol_detail(
    file_path: str = Query(..., description="File path containing the symbol"),
    line_number: int = Query(..., description="Line number of the symbol"),
    task_id: str = Query(..., description="Task identifier"),
    db: Session = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Get symbol details at a specific location"""
    # Get task to find worktree_path
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    if not task.worktree_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task has no worktree path"
        )

    ctags_service = get_ctags_service()
    result = ctags_service.get_symbol_at_location(
        worktree_path=task.worktree_path,
        file_path=file_path,
        line_number=line_number
    )

    # Convert definition_snippet from string to list of strings
    definition_snippet = None
    if result.definition_snippet:
        definition_snippet = result.definition_snippet.split('\n')

    # Find all matches for this symbol to populate "All locations"
    matches = None
    similar_symbols = None
    if result.found and result.name:
        match_result = ctags_service.find_symbol(
            worktree_path=task.worktree_path,
            symbol_name=result.name,
            context_file=file_path
        )
        if match_result.matches:
            matches = [
                SymbolMatchItem(
                    file_path=m.file_path,
                    line_number=m.line_number,
                    kind=m.kind,
                    signature=m.signature
                ) for m in match_result.matches
            ]
        if match_result.similar_symbols:
            similar_symbols = [s.name for s in match_result.similar_symbols[:5]]

    return SymbolDefinitionResponse(
        found=result.found,
        name=result.name,
        kind=result.kind,
        file_path=result.file_path,
        line_number=result.line_number,
        type_signature=result.type_signature,
        signature_file_path=result.signature_file_path,
        signature_line_number=result.signature_line_number,
        docstring=result.docstring,
        definition_snippet=definition_snippet,
        snippet_highlight_index=result.snippet_highlight_index,
        reason=result.reason,
        message=result.message,
        similar_symbols=similar_symbols,
        matches=matches
    )



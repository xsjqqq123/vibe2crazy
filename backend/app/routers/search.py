import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Task
from app.services.grep_service import GrepService

router = APIRouter(prefix="/api/search", tags=["search"])
logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    task_id: str
    query: str
    page: int = 1
    per_page: int = 20


class SearchMatch(BaseModel):
    file: str
    line: int
    content: str


class SearchResult(BaseModel):
    results: list[SearchMatch]
    total: int
    cached: bool


@router.post("/grep", response_model=SearchResult)
def grep_search(request: SearchRequest, db: Session = Depends(get_db)):
    """Execute ripgrep search"""
    task = db.query(Task).filter(Task.id == request.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    data = GrepService.search(
        worktree_path=task.worktree_path,
        query=request.query,
        page=request.page,
        per_page=request.per_page
    )

    if "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])

    return SearchResult(
        results=[SearchMatch(**r) for r in data["results"]],
        total=data["total"],
        cached=data["cached"]
    )


@router.delete("/cache")
def clear_cache(task_id: str, db: Session = Depends(get_db)):
    """Clear search cache"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    GrepService.clear_cache(task_id)
    return {"success": True}

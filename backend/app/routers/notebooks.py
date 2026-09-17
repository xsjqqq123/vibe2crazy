"""
Notebook API - markdown notes stored as real files on disk.

Thin HTTP layer over NotebookService; the service owns the filesystem work and
raises stdlib exceptions that are mapped to status codes here.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.database import get_db
from app.models import Session as SessionModel
from app.schemas import (
    MoveRequest,
    NotebookContentResponse,
    NotebookContentUpdate,
    NotebookCreate,
    NotebookDetailResponse,
    NotebookGroupCreate,
    NotebookGroupResponse,
    NotebookGroupUpdate,
    NotebookReconcileResponse,
    NotebookResponse,
    NotebookSearchResponse,
    NotebookTreeResponse,
    NotebookUpdate,
    PinRequest,
)
from app.services.notebook_service import NotebookService, StaleContentError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notebooks", tags=["notebooks"])


def _translate(error: Exception) -> HTTPException:
    """Map service exceptions onto HTTP responses."""
    if isinstance(error, StaleContentError):
        # Machine-readable prefix: the client shows an "overwrite?" prompt for this
        # and treats every other 409 as a plain name conflict.
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"stale_content: {error}",
        )
    if isinstance(error, FileExistsError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, FileNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    logger.error(f"Notebook request failed: {error}")
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error))


# ---------------------------------------------------------------- groups ---

@router.get("/groups", response_model=List[NotebookGroupResponse])
def list_groups(
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        NotebookService.reconcile(db)
        return NotebookService.list_groups(db)
    except Exception as e:
        raise _translate(e)


@router.post("/groups", response_model=NotebookGroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: NotebookGroupCreate,
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        NotebookService.ensure_default_group(db)
        group = NotebookService.create_group(db, payload.name)
        return {
            "id": group.id,
            "name": group.name,
            "position": group.position,
            "is_default": group.is_default,
            "note_count": 0,
            "created_at": group.created_at,
            "updated_at": group.updated_at,
        }
    except Exception as e:
        raise _translate(e)


@router.patch("/groups/{group_id}", response_model=NotebookGroupResponse)
def rename_group(
    group_id: str,
    payload: NotebookGroupUpdate,
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        if payload.name is None:
            group = NotebookService.get_group(db, group_id)
        else:
            group = NotebookService.rename_group(db, group_id, payload.name)
        notes = NotebookService.list_group_notes(db, group.id)
        return {
            "id": group.id,
            "name": group.name,
            "position": group.position,
            "is_default": group.is_default,
            "note_count": len(notes),
            "created_at": group.created_at,
            "updated_at": group.updated_at,
        }
    except Exception as e:
        raise _translate(e)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: str,
    force: bool = Query(False, description="Delete even if the group still has notes"),
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        NotebookService.delete_group(db, group_id, force=force)
        return None
    except Exception as e:
        raise _translate(e)


@router.post("/groups/{group_id}/move", response_model=List[NotebookGroupResponse])
def move_group(
    group_id: str,
    payload: MoveRequest,
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        return NotebookService.move_group(db, group_id, payload.direction)
    except Exception as e:
        raise _translate(e)


# ----------------------------------------------------------------- notes ---

@router.get("", response_model=NotebookTreeResponse)
def list_notes(
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        NotebookService.reconcile(db)
        return NotebookService.list_notes(db)
    except Exception as e:
        raise _translate(e)


@router.get("/search", response_model=NotebookSearchResponse)
def search_notes(
    q: str = Query("", description="Search term"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        # Reconcile so results carry ids even for files added outside the app.
        NotebookService.reconcile(db)
        result = NotebookService.search(db, q, limit=limit)
        return {"query": q, **result}
    except Exception as e:
        raise _translate(e)


@router.post("/reconcile", response_model=NotebookReconcileResponse)
def reconcile(
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        return NotebookService.reconcile(db)
    except Exception as e:
        raise _translate(e)


@router.post("", response_model=NotebookDetailResponse, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NotebookCreate,
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        note = NotebookService.create_note(db, payload.group_id, payload.title, payload.content)
        result = NotebookService.read_note(db, note.id)
        return result
    except Exception as e:
        raise _translate(e)


@router.get("/{note_id}", response_model=NotebookDetailResponse)
def get_note(
    note_id: str,
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        return NotebookService.read_note(db, note_id)
    except Exception as e:
        raise _translate(e)


@router.put("/{note_id}/content", response_model=NotebookContentResponse)
def save_content(
    note_id: str,
    payload: NotebookContentUpdate,
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        return NotebookService.save_content(
            db, note_id, payload.content, base_hash=payload.base_hash
        )
    except Exception as e:
        raise _translate(e)


@router.patch("/{note_id}", response_model=NotebookResponse)
def update_note(
    note_id: str,
    payload: NotebookUpdate,
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        note = NotebookService.update_note(
            db, note_id, title=payload.title, group_id=payload.group_id
        )
        return NotebookService.note_payload(note)
    except Exception as e:
        raise _translate(e)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: str,
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        NotebookService.delete_note(db, note_id)
        return None
    except Exception as e:
        raise _translate(e)


@router.post("/{note_id}/pin", response_model=NotebookResponse)
def pin_note(
    note_id: str,
    payload: PinRequest,
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        note = NotebookService.set_pinned(db, note_id, payload.pinned)
        return NotebookService.note_payload(note)
    except Exception as e:
        raise _translate(e)


@router.post("/{note_id}/move", response_model=List[NotebookResponse])
def move_note(
    note_id: str,
    payload: MoveRequest,
    db: Session = Depends(get_db),
    session: SessionModel = Depends(require_auth),
):
    try:
        return NotebookService.move_note(db, note_id, payload.direction)
    except Exception as e:
        raise _translate(e)

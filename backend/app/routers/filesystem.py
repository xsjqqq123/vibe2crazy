"""
Filesystem router for directory listing operations.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from app.database import get_db
from app.auth import require_auth
from app.models import Session as SessionModel
from app.services.filesystem_service import FilesystemService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/filesystem", tags=["filesystem"])


class DirectoryListResponse(BaseModel):
    """Response model for directory listing."""
    directories: List[str]


@router.get("/directories", response_model=DirectoryListResponse)
async def list_directories(
    path: str = Query(..., description="Directory path to list"),
    session: SessionModel = Depends(require_auth)
):
    """
    List child directories of the given path.

    Requires authentication via session token.

    Args:
        path: Directory path to list
        session: Authenticated session (injected by require_auth)

    Returns:
        DirectoryListResponse with list of child directory names

    Raises:
        HTTPException 400: For invalid or insecure paths
        HTTPException 401: For unauthenticated requests
        HTTPException 500: For filesystem errors
    """
    try:
        logger.debug(f"Listing directories for path: {path}")

        # Use FilesystemService to list directories
        directories = FilesystemService.list_directories(path)

        logger.debug(f"Found {len(directories)} directories in {path}")
        return DirectoryListResponse(directories=directories)

    except ValueError as e:
        # Path validation failed (e.g., directory traversal attempt)
        logger.warning(f"Invalid path requested: {path} - {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Filesystem errors
        logger.error(f"Error listing directories for {path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list directories: {str(e)}"
        )

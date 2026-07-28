import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_auth
from app.services.tmux_service import TmuxService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/global-terminal", tags=["global-terminal"])


@router.post("/session")
async def get_or_create_session(
    instance: int = Query(0, ge=0, le=3),
    session = Depends(require_auth)
):
    """Create or retrieve a global terminal tmux session for the given instance (0-3)."""
    session_name = f"v2d-global-{instance}"
    tmux = TmuxService()
    exists = tmux.session_exists(session_name)

    if not exists:
        logger.info(f"Creating global terminal session: {session_name}")
        success, msg = tmux.create_session(session_name, "~")
        if not success:
            raise HTTPException(status_code=500, detail=msg)

    return {"session_name": session_name, "instance": instance, "created": not exists}

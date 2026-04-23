import logging

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_auth
from app.services.tmux_service import TmuxService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/global-terminal", tags=["global-terminal"])

GLOBAL_SESSION_NAME = "v2d-global"


@router.post("/session")
async def get_or_create_session(session = Depends(require_auth)):
    """Create or retrieve the global terminal tmux session."""
    tmux = TmuxService()
    exists = tmux.session_exists(GLOBAL_SESSION_NAME)

    if not exists:
        logger.info(f"Creating global terminal session: {GLOBAL_SESSION_NAME}")
        success, msg = tmux.create_session(GLOBAL_SESSION_NAME, "~")
        if not success:
            raise HTTPException(status_code=500, detail=msg)

    return {"session_name": GLOBAL_SESSION_NAME, "created": not exists}

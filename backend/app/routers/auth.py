import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from app.database import get_db
from app.models import Session as SessionModel
from app.schemas import (
    LoginRequest, LoginResponse, SessionResponse,
    PasswordStatusResponse, ChangePasswordRequest, ChangePasswordResponse
)
from app.auth import verify_password, create_access_token, get_password_status, set_password
from app.config import settings

# Import rate limiters from rate_limiters module
from app.rate_limiters import auth_rate_limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(auth_rate_limiter)])
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """Login with password"""
    logger.info(f"Login attempt from remote")

    # Check if password is set
    if not get_password_status(db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password not set"
        )

    if not verify_password(request.password, db):
        logger.warning(f"Login failed: Invalid password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )

    # Create session token with unique JWT ID (jti)
    # This ensures each login generates a unique token even if called in the same second
    token_data = {"sub": "user", "jti": str(uuid.uuid4())}
    token = create_access_token(token_data)

    # Store session in database
    expires_at = datetime.utcnow() + timedelta(hours=settings.session_expire_hours)
    session = SessionModel(
        token=token,
        expires_at=expires_at
    )

    try:
        db.add(session)
        db.commit()
    except IntegrityError:
        # Fallback: if token somehow already exists, delete old session and retry
        logger.warning(f"Token collision detected, removing old session and retrying")
        db.rollback()
        db.query(SessionModel).filter(SessionModel.token == token).delete()
        db.add(session)
        db.commit()

    logger.info(f"Login successful, session expires at {expires_at}")
    return LoginResponse(token=token)


@router.delete("/logout")
async def logout(
    session: SessionModel = Depends(lambda: None),  # We'll use proper auth in main
    db: Session = Depends(get_db)
):
    """Logout and invalidate session"""
    # For now, this is a placeholder
    logger.info("Logout requested")
    return {"success": True}


@router.get("/me", response_model=SessionResponse)
async def get_session(
    session: SessionModel = Depends(lambda: None)  # Placeholder
):
    """Get current session info"""
    # Placeholder - will be replaced with proper auth dependency
    authenticated = session is not None
    logger.debug(f"Session check: authenticated={authenticated}")
    return SessionResponse(
        authenticated=authenticated,
        expires_at=session.expires_at if session else None
    )


# Public endpoint - no authentication required
@router.get("/password-status", response_model=PasswordStatusResponse)
async def get_password_status_endpoint(db: Session = Depends(get_db)):
    """Check if password is set - no auth required"""
    return PasswordStatusResponse(is_set=get_password_status(db))


@router.post("/change-password", response_model=ChangePasswordResponse, dependencies=[Depends(auth_rate_limiter)])
async def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db)
):
    """Set or change the system password"""
    # Check if password is already set
    has_password = get_password_status(db)

    # Verify old password if password is already set
    if has_password:
        if not request.old_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Old password is required"
            )
        if not verify_password(request.old_password, db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid old password"
            )

    # Validate new password
    if not request.new_password or len(request.new_password) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password cannot be empty"
        )

    if len(request.new_password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 4 characters"
        )

    try:
        set_password(db, request.new_password)
        logger.info("Password changed successfully")
        return ChangePasswordResponse(success=True, message="Password changed successfully")
    except Exception as e:
        logger.error(f"Failed to change password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )
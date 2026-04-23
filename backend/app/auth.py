from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from app.database import get_db
from app.models import Session as SessionModel, SystemSettings
from app.config import settings

# API Key header for authentication
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.session_expire_hours)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
    return encoded_jwt


def verify_token(token: str) -> bool:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        exp = payload.get("exp")
        if exp is None:
            return False
        if datetime.fromtimestamp(exp) < datetime.utcnow():
            return False
        return True
    except JWTError:
        return False


async def get_current_token(
    authorization: Optional[str] = Depends(api_key_header),
    db: Session = Depends(get_db)
) -> Optional[SessionModel]:
    """Get current session from token"""
    if authorization is None:
        return None

    if not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]  # Remove "Bearer " prefix

    # Verify token signature and expiration
    if not verify_token(token):
        return None

    # Check if session exists in database
    session = db.query(SessionModel).filter(SessionModel.token == token).first()
    if not session:
        return None

    # Check if session expired
    if session.expires_at < datetime.utcnow():
        db.delete(session)
        db.commit()
        return None

    return session


async def require_auth(
    session: Optional[SessionModel] = Depends(get_current_token)
) -> SessionModel:
    """Require authentication - raise 401 if not authenticated"""
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return session


async def optional_auth(
    session: Optional[SessionModel] = Depends(get_current_token)
) -> Optional[SessionModel]:
    """Optional authentication - returns None if not authenticated"""
    return session


def get_password_status(db: Session) -> bool:
    """Check if password is set (not None or empty)"""
    settings_record = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if not settings_record:
        return False  # No password set
    return settings_record.password_hash is not None and settings_record.password_hash != ""


def set_password(db: Session, password: str) -> None:
    """Set password in database"""
    settings_record = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if not settings_record:
        settings_record = SystemSettings(id=1, password_hash=password)
        db.add(settings_record)
    else:
        settings_record.password_hash = password
    db.commit()


def verify_password(password: str, db: Session) -> bool:
    """Verify password against database"""
    settings_record = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if not settings_record or not settings_record.password_hash:
        # No password set - should never happen in normal flow
        return False
    return password == settings_record.password_hash

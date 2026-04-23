import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.models import CommandPreset
from app.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(tags=["command-presets"])


class CommandPresetCreate(BaseModel):
    command: str


class CommandPresetResponse(BaseModel):
    id: int
    command: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[CommandPresetResponse])
async def list_presets(
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """List all command presets"""
    presets = db.query(CommandPreset).order_by(
        CommandPreset.created_at.desc()
    ).all()
    logger.debug(f"Listed {len(presets)} command presets")
    return presets


@router.post("", response_model=CommandPresetResponse, status_code=status.HTTP_201_CREATED)
async def create_preset(
    preset: CommandPresetCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """Create a new command preset"""
    # Validate command is not empty
    if not preset.command or not preset.command.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Command cannot be empty"
        )

    # Validate command length
    if len(preset.command) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Command must be 1000 characters or less"
        )

    # Trim whitespace
    command = preset.command.strip()

    new_preset = CommandPreset(command=command)
    db.add(new_preset)
    db.commit()
    db.refresh(new_preset)

    logger.info(f"Created command preset {new_preset.id}")
    return new_preset


@router.delete("/{preset_id}")
async def delete_preset(
    preset_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """Delete a command preset"""
    preset = db.query(CommandPreset).filter(CommandPreset.id == preset_id).first()
    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command preset not found"
        )

    db.delete(preset)
    db.commit()

    logger.info(f"Deleted command preset {preset_id}")
    return {"success": True}

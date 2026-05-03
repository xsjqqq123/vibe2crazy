"""Tunnel API endpoints."""

import logging
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TunnelConfig
from app.config import settings
from app.schemas import (
    TunnelStatusResponse,
    TunnelConfigUpdate,
    TunnelConfigResponse,
    LocalInfoResponse,
    TokenHashResponse,
    CertInfoResponse,
)
from app.services.network_service import network_service
import hashlib
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tunnel", tags=["tunnel"])

# Global tunnel service instance
_tunnel_service = None


def get_tunnel_service():
    """Get the global tunnel service instance."""
    return _tunnel_service


def set_tunnel_service(service):
    """Set the global tunnel service instance."""
    global _tunnel_service
    _tunnel_service = service


def get_tunnel_config(db: Session = Depends(get_db)) -> TunnelConfig:
    """Get or create tunnel config (single row with id=1)."""
    config = db.query(TunnelConfig).filter(TunnelConfig.id == 1).first()
    if not config:
        config = TunnelConfig(id=1, status="disabled", use_tls=True)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("/status", response_model=TunnelStatusResponse)
async def get_status(
    config: TunnelConfig = Depends(get_tunnel_config)
):
    """Get current tunnel status."""
    # Get server URL without port for display
    server_url = config.server_url or settings.tunnel_server_url
    if server_url:
        # Remove port from URL for "Get token" link
        parsed = urlparse(server_url)
        server_url = f"{parsed.scheme}://{parsed.hostname}"

    return TunnelStatusResponse(
        status=config.status,
        remote_url=config.remote_url,
        token=config.token,
        last_error=config.last_error,
        server_url=server_url
    )


@router.put("/config", response_model=TunnelConfigResponse)
async def update_config(
    request: TunnelConfigUpdate,
    db: Session = Depends(get_db),
    config: TunnelConfig = Depends(get_tunnel_config)
):
    """Save tunnel token and configuration."""
    service = get_tunnel_service()
    was_running = service and service.is_running

    # Stop service if running
    if was_running:
        logger.info("Stopping tunnel service for config update")
        await service.stop()

    # Update config
    config.token = request.token
    if request.use_tls is not None:
        config.use_tls = request.use_tls
    if request.verify_tls is not None:
        config.verify_tls = request.verify_tls
    config.status = "disabled"
    config.last_error = None
    db.commit()

    # Schedule async restart if was running (don't wait for it)
    if was_running:
        import asyncio
        async def delayed_restart():
            await asyncio.sleep(2)  # Wait 2 seconds before restart
            logger.info("Restarting tunnel service with new config")
            await service.start()
        asyncio.create_task(delayed_restart())

    logger.info(f"Tunnel config updated, token={request.token[:8]}...")
    return TunnelConfigResponse(success=True, message="Configuration saved")


@router.post("/start")
async def start_tunnel(
    db: Session = Depends(get_db),
    config: TunnelConfig = Depends(get_tunnel_config)
):
    """Start tunnel service."""
    service = get_tunnel_service()

    if not service:
        raise HTTPException(status_code=500, detail="Tunnel service not initialized")

    if not config.token:
        raise HTTPException(status_code=400, detail="No tunnel token configured")

    if service.is_running:
        return {"success": True, "message": "Tunnel service already running"}

    success = await service.start()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start tunnel service")

    return {"success": True, "message": "Tunnel service started"}


@router.post("/stop")
async def stop_tunnel():
    """Stop tunnel service."""
    service = get_tunnel_service()

    if not service:
        return {"success": True, "message": "Tunnel service not initialized"}

    if not service.is_running:
        return {"success": True, "message": "Tunnel service not running"}

    await service.stop()
    return {"success": True, "message": "Tunnel service stopped"}


@router.post("/restart")
async def restart_tunnel():
    """Restart tunnel service."""
    service = get_tunnel_service()

    if not service:
        raise HTTPException(status_code=500, detail="Tunnel service not initialized")

    await service.restart()
    return {"success": True, "message": "Tunnel service restarted"}


@router.get("/localinfo", response_model=LocalInfoResponse)
async def get_local_info():
    """Get local network information for LAN detection.

    This endpoint returns all local IPs and a token hash for verification.
    No authentication required - this is used by frontend to detect LAN availability.
    """
    return LocalInfoResponse(
        ips=network_service.get_local_ips(),
        port=network_service.port,
        token_hash=network_service.generate_token_hash()
    )


@router.get("/token_hash", response_model=TokenHashResponse)
async def get_token_hash():
    """Get token hash for backend identity verification.

    This endpoint is used to verify that the connected backend is the same instance.
    No authentication required - this is used for LAN detection probing.
    """
    return TokenHashResponse(
        token_hash=network_service.generate_token_hash()
    )


@router.get("/cert_info", response_model=CertInfoResponse)
async def get_cert_info():
    """Get TLS certificate information for the backend.

    Returns the SHA-256 fingerprint of the self-signed certificate if available.
    This allows the frontend to know whether it's connecting to a TLS-enabled backend
    and to accept self-signed certificates when probing LAN addresses.
    """
    # Get cert path from settings database location
    db_path = settings.database_url.replace("sqlite:///", "")
    data_dir = Path(db_path).parent
    cert_path = data_dir / "cert.pem"

    if cert_path.exists():
        try:
            with open(cert_path, "rb") as f:
                cert_data = f.read()
            fingerprint = hashlib.sha256(cert_data).hexdigest()
            return CertInfoResponse(has_tls=True, fingerprint=fingerprint)
        except Exception as e:
            logger.warning(f"Failed to read certificate: {e}")

    return CertInfoResponse(has_tls=False, fingerprint=None)
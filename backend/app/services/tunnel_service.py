"""Tunnel service for managing remote access connection."""

import asyncio
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.models import TunnelConfig
from app.config import settings

logger = logging.getLogger(__name__)


class TunnelService:
    """Manages tunnel client lifecycle as async background task."""

    def __init__(self, db: Session, local_port: int, config: TunnelConfig):
        self.db = db
        self.local_port = local_port
        self.config = config
        self._task: Optional[asyncio.Task] = None
        self._client_task: Optional[asyncio.Task] = None
        self._client = None
        self._running = False
        self._connected = False

    async def start(self) -> bool:
        """Start tunnel client as background task."""
        if self._running:
            logger.info("Tunnel service already running")
            return True

        # Refresh config from database to get latest token
        try:
            self.db.refresh(self.config)
        except Exception as e:
            logger.error(f"Failed to refresh config: {e}")

        if not self.config.token:
            logger.warning("No tunnel token configured")
            return False

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Tunnel service started")
        return True

    async def stop(self):
        """Stop tunnel client."""
        logger.info("Stopping tunnel service...")
        self._running = False

        if self._client:
            try:
                await self._client.stop()
            except Exception as e:
                logger.error(f"Error stopping tunnel client: {e}")
            self._client = None

        if self._client_task:
            self._client_task.cancel()
            try:
                await self._client_task
            except asyncio.CancelledError:
                pass
            self._client_task = None

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        self._update_status("disabled")
        logger.info("Tunnel service stopped")

    async def restart(self):
        """Restart tunnel client."""
        await self.stop()
        await self.start()

    @property
    def is_running(self) -> bool:
        """Check if service is running."""
        return self._running

    @property
    def is_connected(self) -> bool:
        """Check if tunnel is connected."""
        return self._connected

    async def _run_loop(self):
        """Main loop with infinite retry."""
        delay = 5.0

        while self._running:
            try:
                await self._connect()
                delay = 5.0  # Reset on success
                await self._wait_disconnect()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Tunnel connection error: {e}")
                self._update_status("disconnected", str(e))
                delay = min(delay * 2, 60.0)
                logger.info(f"Retrying in {delay:.1f} seconds...")
                await asyncio.sleep(delay)

    async def _connect(self):
        """Connect to tunnel server."""
        self._update_status("connecting")

        try:
            # Import tunnel client package
            from client import TunnelClient
            from client.config import TunnelClientConfig
            from client.node_discovery import NodeDiscovery

            # Get server URL
            server_url = self.config.server_url or settings.tunnel_server_url
            if not server_url:
                raise ValueError("No tunnel server URL configured")

            # Node discovery
            logger.info(f"Discovering tunnel node via {server_url}")
            discovery = NodeDiscovery(server_url, self.config.token)
            node_info = await discovery.get_node_info()

            # Create client config
            client_config = TunnelClientConfig(
                backend_api_url=server_url,
                token=self.config.token,
                local_host="127.0.0.1",
                local_port=self.local_port,
                use_tls=self.config.use_tls,
                verify_tls=self.config.verify_tls,
                reconnect_max_retries=0,  # Disable client retry, managed by TunnelService
            )

            # Create and start client
            self._client = TunnelClient(client_config)

            # Override discovered node info
            self._client.config.server_host = node_info["node_domain"]
            self._client.config.server_port = node_info["node_tunnel_port"]
            self._client._assigned_port = node_info["assigned_port"]

            # Start client (this spawns its own background task)
            self._client_task = asyncio.create_task(self._client.start())

            # Wait for connection to become active (up to 30s handshake timeout)
            for _ in range(30):
                if self._client._connection and self._client._connection.is_active:
                    break
                await asyncio.sleep(1)

            # Check if client connected successfully
            if self._client._connection and self._client._connection.is_active:
                self._connected = True
                remote_url = f"http://{node_info['node_domain']}:{node_info['assigned_port']}"
                self._update_status("connected", remote_url=remote_url)
                logger.info(f"Tunnel connected: {remote_url}")
            else:
                # Connection failed, will be retried
                raise RuntimeError("Tunnel client failed to connect")

        except Exception as e:
            self._connected = False
            raise

    async def _wait_disconnect(self):
        """Wait for connection to disconnect."""
        while self._running and self._connected:
            if self._client and hasattr(self._client, '_connection'):
                conn = self._client._connection
                if conn and hasattr(conn, 'is_active') and not conn.is_active:
                    logger.info("Tunnel connection lost")
                    self._connected = False
                    break
            await asyncio.sleep(1)

    def _update_status(self, status: str, error: str = None, remote_url: str = None):
        """Update database status."""
        try:
            self.config.status = status
            # Clear error when connected, otherwise update if provided
            if status == "connected":
                self.config.last_error = None
            elif error is not None:
                self.config.last_error = error
            if remote_url is not None:
                self.config.remote_url = remote_url
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update tunnel status: {e}")
            self.db.rollback()
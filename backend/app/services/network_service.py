# backend/app/services/network_service.py
"""Network information service for LAN detection."""

import hashlib
import socket
import logging
from typing import List
from app.config import settings

logger = logging.getLogger(__name__)


class NetworkService:
    """Service for getting network information."""

    def __init__(self, port: int = None):
        self.port = port or settings.port

    def get_local_ips(self) -> List[str]:
        """Get all local network IP addresses.

        Returns:
            List of IPv4 addresses (excluding 127.0.0.1 and public IPs)
        """
        ips = []
        try:
            # Get hostname and all associated IPs
            hostname = socket.gethostname()
            all_ips = socket.gethostbyname_ex(hostname)[2]

            for ip in all_ips:
                # Filter: exclude loopback and keep only private IPs
                if ip == "127.0.0.1":
                    continue
                if self._is_private_ip(ip):
                    ips.append(ip)

        except Exception as e:
            logger.error(f"Failed to get local IPs: {e}")

        return ips

    def _is_private_ip(self, ip: str) -> bool:
        """Check if IP is a private/local network address.

        Private IP ranges:
        - 10.0.0.0/8
        - 172.16.0.0/12
        - 192.168.0.0/16
        - 169.254.0.0/16 (link-local)
        """
        parts = [int(p) for p in ip.split(".")]

        # 10.0.0.0/8
        if parts[0] == 10:
            return True
        # 172.16.0.0/12
        if parts[0] == 172 and 16 <= parts[1] <= 31:
            return True
        # 192.168.0.0/16
        if parts[0] == 192 and parts[1] == 168:
            return True
        # 169.254.0.0/16 (link-local)
        if parts[0] == 169 and parts[1] == 254:
            return True

        return False

    def generate_token_hash(self) -> str:
        """Generate a hash for verifying backend identity.

        Uses a combination of:
        - Server port
        - First local IP (if available)
        - A random session identifier

        Returns:
            SHA256 hash string prefixed with 'sha256:'
        """
        # Create unique identifier for this backend instance
        identifier = f"{self.port}:{','.join(self.get_local_ips() or ['none'])}"
        hash_value = hashlib.sha256(identifier.encode()).hexdigest()[:16]
        return f"sha256:{hash_value}"


# Global instance
network_service = NetworkService()
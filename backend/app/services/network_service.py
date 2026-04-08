# backend/app/services/network_service.py
"""Network information service for LAN detection."""

import hashlib
import socket
import logging
import platform
import subprocess
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
            # Use 'ip addr' command on Linux, works reliably
            ips = self._get_ips_from_ip_command()

            # Filter: exclude loopback, docker bridges, and keep only private IPs
            ips = [ip for ip in ips
                   if ip != "127.0.0.1"
                   and not ip.startswith("172.17.")  # Docker default bridge
                   and not ip.startswith("172.18.")  # Docker custom bridge
                   and self._is_private_ip(ip)]

        except Exception as e:
            logger.error(f"Failed to get local IPs: {e}")

        return ips

    def _get_ips_from_ip_command(self) -> List[str]:
        """Get IP addresses using 'ip addr' command (Linux)."""
        ips = []
        try:
            result = subprocess.run(
                ['ip', 'addr', 'show'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line.startswith('inet ') and not line.startswith('inet 127.'):
                        # Parse: "inet 192.168.1.100/24 brd 192.168.1.255 scope global ..."
                        parts = line.split()
                        if len(parts) >= 2:
                            # Get IP without CIDR
                            ip_cidr = parts[1]
                            if '/' in ip_cidr:
                                ip = ip_cidr.split('/')[0]
                                # Skip network address (.0) and broadcast (.255)
                                last_octet = int(ip.split('.')[-1])
                                if last_octet != 0 and last_octet != 255:
                                    ips.append(ip)
        except Exception as e:
            logger.error(f"Failed to run 'ip addr': {e}")
            # Fallback to hostname method
            try:
                hostname = socket.gethostname()
                all_ips = socket.gethostbyname_ex(hostname)[2]
                ips.extend(all_ips)
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")

        return list(set(ips))  # Remove duplicates

    def _is_private_ip(self, ip: str) -> bool:
        """Check if IP is a private/local network address.

        Private IP ranges:
        - 10.0.0.0/8
        - 172.16.0.0/12 (excluding Docker bridges 172.17-18)
        - 192.168.0.0/16
        - 169.254.0.0/16 (link-local)
        """
        try:
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
        except:
            pass

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
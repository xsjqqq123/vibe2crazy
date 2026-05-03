"""Self-signed certificate utilities and dual-stack HTTP/HTTPS proxy."""

import os
import socket
import struct
import ssl
import sys
import threading
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _clean_env_for_subprocess() -> dict:
    """Clean environment for subprocess to avoid PyInstaller library pollution.

    When running as a PyInstaller bundle, LD_LIBRARY_PATH and LD_PRELOAD
    may point to the extracted temp directory, causing system binaries like
    openssl to load incompatible bundled libraries.
    """
    env = os.environ.copy()

    pyinstaller_tmp = None
    if getattr(sys, 'frozen', False):
        pyinstaller_tmp = getattr(sys, '_MEIPASS', None)

    for var in [
        'LD_LIBRARY_PATH', 'LD_PRELOAD', 'LD_AUDIT', 'LD_BIND_NOW',
        'LD_DEBUG', 'LD_DYNAMIC_WEAK', 'LD_ORIGIN', 'LD_PROFILE',
        'LD_SHOW_AUXV', 'LD_TRACE_LOADED_OBJECTS', 'LD_USE_LOAD_CACHE',
        'LD_VERBOSE', 'LD_WARN', 'LD_WRAPPER_PATH',
    ]:
        env.pop(var, None)

    if 'PYTHONPATH' in env:
        paths = env['PYTHONPATH'].split(':')
        if pyinstaller_tmp:
            paths = [p for p in paths if p and not p.startswith(pyinstaller_tmp) and not p.startswith('/tmp/_ME')]
        env['PYTHONPATH'] = ':'.join(paths) if paths else env.pop('PYTHONPATH')

    return env

# Internal port for uvicorn
INTERNAL_PORT = 18863


def ensure_self_signed_cert(data_dir: Path) -> tuple[Path, Path]:
    """Generate self-signed certificate if not exists.

    Returns (cert_path, key_path).
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    cert_path = data_dir / "cert.pem"
    key_path = data_dir / "key.pem"

    if cert_path.exists() and key_path.exists():
        logger.info("Using existing TLS certificate at %s", cert_path)
        return cert_path, key_path

    logger.info("Generating self-signed TLS certificate...")

    # Use openssl to generate a self-signed cert
    try:
        subprocess.run([
            "openssl", "req", "-x509",
            "-newkey", "rsa:2048",
            "-keyout", str(key_path),
            "-out", str(cert_path),
            "-days", "3650",
            "-nodes",
            "-subj", "/CN=localhost/O=vibe2crazy/C=CN"
        ], check=True, capture_output=True, text=True,
            env=_clean_env_for_subprocess())
        logger.info("TLS certificate generated successfully")
        return cert_path, key_path
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error("Failed to generate TLS certificate: %s", e)
        raise RuntimeError(
            "Failed to generate TLS certificate. "
            "Please install openssl: sudo apt install openssl"
        ) from e


def create_ssl_context(cert_path: Path, key_path: Path) -> ssl.SSLContext:
    """Create SSL context from cert and key files."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert_path), str(key_path))
    # Allow all ciphers for compatibility
    ctx.set_ciphers("DEFAULT")
    return ctx


class DualStackProxy:
    """TCP proxy that serves both HTTP and HTTPS on the same port.

    For each incoming connection:
    1. Peek at the first byte
    2. If TLS record (0x16): wrap with SSL, forward to HTTPS handler
    3. Otherwise: forward as plain HTTP
    """

    def __init__(
        self,
        external_port: int,
        internal_host: str,
        internal_port: int,
        ssl_ctx: Optional[ssl.SSLContext] = None,
    ):
        self.external_port = external_port
        self.internal_host = internal_host
        self.internal_port = internal_port
        self.ssl_ctx = ssl_ctx
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._server_sock: Optional[socket.socket] = None

    def start(self):
        """Start the proxy in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="DualStackProxy")
        self._thread.start()
        logger.info(
            "Dual-stack proxy started on port %d -> %s:%d",
            self.external_port, self.internal_host, self.internal_port
        )

    def stop(self):
        """Stop the proxy."""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Dual-stack proxy stopped")

    def _run(self):
        """Main accept loop."""
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(("0.0.0.0", self.external_port))
        self._server_sock.listen(128)
        self._server_sock.settimeout(1.0)  # Allow periodic checks for shutdown

        while self._running:
            try:
                client_sock, addr = self._server_sock.accept()
                t = threading.Thread(
                    target=self._handle,
                    args=(client_sock,),
                    daemon=True,
                    name=f"ProxyConn-{addr[1]}"
                )
                t.start()
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    logger.warning("Accept error in dual-stack proxy")
                break

    def _handle(self, client_sock: socket.socket):
        """Handle a single connection: detect TLS and proxy to internal server."""
        try:
            client_sock.settimeout(10.0)

            # Peek at first byte to detect TLS ClientHello
            # TLS record always starts with 0x16 (handshake)
            first_byte = client_sock.recv(1, socket.MSG_PEEK)
            if not first_byte:
                client_sock.close()
                return

            is_tls = (first_byte == b"\x16")

            if is_tls:
                # TLS connection: wrap the socket
                try:
                    wrapped = self.ssl_ctx.wrap_socket(
                        client_sock, server_side=True, do_handshake_on_connect=False
                    )
                    # Handshake in background to not block
                    threading.Thread(
                        target=self._ssl_handshake,
                        args=(wrapped,),
                        daemon=True
                    ).start()
                except ssl.SSLError as e:
                    logger.debug("SSL handshake error (likely non-TLS client): %s", e)
                    client_sock.close()
                    return
            else:
                # Plain HTTP: proxy directly
                self._proxy_data(client_sock, None, False)

        except Exception as e:
            logger.debug("Error handling proxy connection: %s", e)
            try:
                client_sock.close()
            except OSError:
                pass

    def _ssl_handshake(self, ssl_sock: ssl.SSLSocket):
        """Perform SSL handshake, then proxy data."""
        try:
            ssl_sock.do_handshake()
            self._proxy_data(ssl_sock, ssl_sock, True)
        except ssl.SSLError as e:
            logger.debug("SSL handshake failed: %s", e)
        except OSError as e:
            logger.debug("SSL connection error: %s", e)
        finally:
            try:
                ssl_sock.close()
            except OSError:
                pass

    def _proxy_data(self, client_sock, ssl_sock: Optional[ssl.SSLSocket], is_ssl: bool):
        """Bidirectional proxy between client and internal server.

        Args:
            client_sock: The client socket (plain or SSL-wrapped)
            ssl_sock: The SSL socket if is_ssl, else None
            is_ssl: Whether the client connection is SSL
        """
        internal_sock = None
        try:
            # Connect to internal uvicorn
            internal_sock = socket.create_connection(
                (self.internal_host, self.internal_port), timeout=10.0
            )
            internal_sock.settimeout(30.0)

            # Use select for efficient bidirectional proxying
            import select

            while True:
                readable, _, exceptional = select.select(
                    [client_sock, internal_sock], [], [client_sock, internal_sock], 60.0
                )

                if exceptional:
                    # Connection error
                    break

                if not readable:
                    # Timeout - check if both sides are still alive
                    continue

                for sock in readable:
                    try:
                        data = sock.recv(65536)
                        if not data:
                            # Connection closed
                            return

                        dest = internal_sock if sock is client_sock else client_sock
                        dest.sendall(data)
                    except (ssl.SSLError, OSError):
                        # Connection error
                        return

        except (ssl.SSLError, OSError, ConnectionRefusedError) as e:
            logger.debug("Proxy connection closed: %s", e)
        finally:
            try:
                if internal_sock:
                    internal_sock.close()
            except OSError:
                pass
            if not is_ssl:  # SSL socket already closed in _ssl_handshake
                try:
                    client_sock.close()
                except OSError:
                    pass


# Global proxy instance for cleanup
_proxy_instance: Optional[DualStackProxy] = None


def start_dual_stack_proxy(
    cert_path: Path, key_path: Path, external_port: int
) -> int:
    """Start the dual-stack proxy and return the internal port.

    This starts the proxy AND an internal uvicorn in a single function.
    Call this instead of running uvicorn directly.

    Args:
        cert_path: Path to TLS certificate
        key_path: Path to TLS key
        external_port: External port (8863)

    Returns:
        The internal port where uvicorn is running
    """
    import uvicorn
    import asyncio

    ssl_ctx = create_ssl_context(cert_path, key_path)

    # Start uvicorn internally on a random port
    # We use a fresh event loop for the internal server
    internal_port = INTERNAL_PORT

    async def run_uvicorn():
        config = uvicorn.Config(
            "app:app",
            host="127.0.0.1",
            port=internal_port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()

    # Start proxy in a separate thread (uses blocking sockets)
    global _proxy_instance
    _proxy_instance = DualStackProxy(
        external_port=external_port,
        internal_host="127.0.0.1",
        internal_port=internal_port,
        ssl_ctx=ssl_ctx,
    )
    _proxy_instance.start()

    # Run uvicorn in the main thread's event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_uvicorn())
    finally:
        loop.close()


def stop_dual_stack_proxy():
    """Stop the dual-stack proxy. Called on shutdown."""
    global _proxy_instance
    if _proxy_instance:
        _proxy_instance.stop()
        _proxy_instance = None

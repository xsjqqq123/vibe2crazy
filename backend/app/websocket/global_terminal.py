# backend/app/websocket/global_terminal.py
import asyncio
import json
import pty
import os
import select
import subprocess
import fcntl
import struct
import logging
from typing import Optional
from fastapi import WebSocket, Query
from app.auth import verify_token
from app.services.tmux_service import TmuxService, _clean_env_for_subprocess

logger = logging.getLogger(__name__)

SIZE_COLS = 80
SIZE_ROWS = 24
GLOBAL_SESSION_NAME = "v2d-global"


class GlobalWebSocketTerminal:
    """WebSocket terminal handler for the global tmux session"""

    def __init__(self, websocket: WebSocket, session_name: str = GLOBAL_SESSION_NAME, initial_cols: int = SIZE_COLS, initial_rows: int = SIZE_ROWS):
        self.websocket = websocket
        self.session_name = session_name
        self.fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.running = False
        self.cols = initial_cols
        self.rows = initial_rows

    async def start(self):
        """Start terminal session"""
        try:
            # Ensure tmux session exists
            if not TmuxService.session_exists(self.session_name):
                logger.info(f"Creating global tmux session: {self.session_name}")
                success, msg = TmuxService.create_session(self.session_name, "~")
                if not success:
                    logger.error(f"Failed to create global tmux session: {msg}")
                    await self.send_error(f"Failed to create tmux session: {msg}")
                    await self.close()
                    return

            # Create pseudoterminal
            self.fd, slave_fd = pty.openpty()
            self._set_pty_size(self.fd, self.rows, self.cols)
            logger.info(f"Global terminal PTY created: {self.cols}x{self.rows}")

            # Attach to tmux session
            # Use clean environment to avoid PyInstaller library pollution
            cmd = ["tmux", "attach", "-t", self.session_name]
            self.pid = subprocess.Popen(
                cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True,
                env=_clean_env_for_subprocess()
            ).pid

            os.close(slave_fd)
            self.running = True
            logger.info(f"Global terminal started: fd={self.fd}, pid={self.pid}")

            asyncio.create_task(self._read_from_pty())

        except Exception as e:
            logger.error(f"Failed to start global terminal: {e}")
            await self.send_error(f"Failed to start terminal: {str(e)}")
            await self.close()

    def _set_pty_size(self, fd, rows, cols):
        try:
            import termios
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        except Exception as e:
            logger.warning(f"Failed to set PTY size: {e}")

    async def _read_from_pty(self):
        loop = asyncio.get_event_loop()
        max_read_bytes = 1024 * 1024

        try:
            while self.running and self.fd is not None:
                try:
                    data = await loop.run_in_executor(
                        None,
                        lambda: os.read(self.fd, max_read_bytes) if self._select() else b""
                    )

                    if data:
                        decoded = data.decode("utf-8", errors="replace")
                        await self.send_output(decoded)
                    else:
                        await asyncio.sleep(0.05)

                except OSError:
                    logger.info("Global terminal PTY closed (OSError)")
                    break

        except Exception as e:
            logger.error(f"Error reading from global PTY: {e}")
        finally:
            self.running = False

    def _select(self) -> bool:
        try:
            return select.select([self.fd], [], [], 0.1)[0] != []
        except:
            return False

    async def handle_input(self, data: str):
        try:
            if self.fd is not None:
                os.write(self.fd, data.encode("utf-8"))
        except Exception as e:
            await self.send_error(f"Write error: {str(e)}")

    async def handle_resize(self, cols: int, rows: int):
        try:
            if not (10 <= cols <= 500 and 5 <= rows <= 200):
                return

            if self.fd is not None:
                self._set_pty_size(self.fd, rows, cols)
                self.cols = cols
                self.rows = rows

                try:
                    subprocess.run(
                        ["tmux", "resize-pane", "-t", self.session_name, "-x", str(cols), "-y", str(rows)],
                        capture_output=True,
                        timeout=1,
                        env=_clean_env_for_subprocess()
                    )
                except:
                    pass

                if self.pid is not None:
                    try:
                        import signal
                        os.killpg(os.getpgid(self.pid), signal.SIGWINCH)
                    except:
                        pass

        except Exception as e:
            logger.warning(f"Error during global terminal resize: {e}")

    async def handle_scroll_mode(self, action: str):
        try:
            if action == 'enter':
                subprocess.run(
                    ['tmux', 'copy-mode', '-t', self.session_name],
                    capture_output=True, text=True, timeout=2, env=_clean_env_for_subprocess()
                )
            elif action == 'exit':
                subprocess.run(
                    ['tmux', 'send-keys', '-t', self.session_name, 'Escape'],
                    capture_output=True, text=True, timeout=2, env=_clean_env_for_subprocess()
                )
        except Exception as e:
            logger.error(f"Error during scroll mode {action}: {e}")

    async def handle_scroll(self, direction: str, page: bool = False):
        try:
            if page:
                cmd = 'page-up' if direction == 'up' else 'page-down'
            else:
                cmd = 'cursor-up' if direction == 'up' else 'cursor-down'

            subprocess.run(
                ['tmux', 'send-keys', '-t', self.session_name, '-X', cmd],
                capture_output=True, text=True, timeout=2, env=_clean_env_for_subprocess()
            )
        except Exception as e:
            logger.error(f"Error during scroll {direction}: {e}")

    async def send_output(self, data: str):
        try:
            await self.websocket.send_json({"type": "output", "data": data})
        except Exception as e:
            logger.warning(f"Failed to send output: {e}")
            self.running = False

    async def send_error(self, message: str):
        try:
            await self.websocket.send_json({"type": "error", "message": message})
        except:
            pass

    async def close(self):
        self.running = False
        if self.fd is not None:
            try:
                os.close(self.fd)
            except:
                pass
            self.fd = None
        if self.pid is not None:
            try:
                os.killpg(os.getpgid(self.pid), 9)
            except:
                pass
            self.pid = None
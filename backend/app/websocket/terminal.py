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
from fastapi import WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Task
from app.auth import verify_token
from app.services.tmux_service import TmuxService, _clean_env_for_subprocess
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

SIZE_COLS = 80
SIZE_ROWS = 24


class WebSocketTerminal:
    """WebSocket terminal handler for tmux sessions"""

    def __init__(self, websocket: WebSocket, task: Task):
        self.websocket = websocket
        self.task = task
        self.fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.running = False
        self.cols = SIZE_COLS
        self.rows = SIZE_ROWS

    async def start(self):
        """Start terminal session"""
        try:
            # Check if tmux session exists, recreate if needed
            session_name = self.task.tmux_session
            if not TmuxService.session_exists(session_name):
                logger.warning(f"Tmux session '{session_name}' not found, attempting to recreate...")
                success, msg = TmuxService.create_session(
                    session_name,
                    self.task.worktree_path
                )
                if not success:
                    logger.error(f"Failed to recreate tmux session '{session_name}': {msg}")
                    await self.send_error(f"Failed to create tmux session: {msg}")
                    await self.close()
                    return
                logger.info(f"Tmux session '{session_name}' recreated successfully")

            # Create pseudoterminal
            self.fd, slave_fd = pty.openpty()

            # Set terminal size to default initially
            self._set_pty_size(self.fd, SIZE_ROWS, SIZE_COLS)
            logger.info(f"PTY created with default size: {SIZE_COLS}x{SIZE_ROWS}")

            # Attach to existing tmux session (do NOT create grouped session)
            # Using 'tmux attach' connects to the existing window with its history intact
            # The session was already created by TmuxService.create_session with proper history-limit
            # Use clean environment to avoid PyInstaller library pollution
            cmd = ["tmux", "attach", "-t", self.task.tmux_session]
            self.pid = subprocess.Popen(
                cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True,
                env=_clean_env_for_subprocess()
            ).pid

            # Close slave fd in parent
            os.close(slave_fd)

            self.running = True
            logger.info(f"Terminal started: fd={self.fd}, pid={self.pid}, tmux_session={self.task.tmux_session}")

            # Start reading from pty
            asyncio.create_task(self._read_from_pty())

        except Exception as e:
            logger.error(f"Failed to start terminal: {e}")
            await self.send_error(f"Failed to start terminal: {str(e)}")
            await self.close()

    def _set_pty_size(self, fd, rows, cols):
        """Set PTY window size"""
        try:
            # TIOCSWINSZ = 0x5414
            # struct winsize { unsigned short ws_row, ws_col, ws_xpixel, ws_ypixel; }
            import termios
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
            logger.debug(f"Set PTY size: {rows}x{cols}")
        except Exception as e:
            logger.warning(f"Failed to set PTY size: {e}")

    async def _read_from_pty(self):
        """Read output from PTY and send to WebSocket"""
        loop = asyncio.get_event_loop()
        max_read_bytes = 1024 * 1024
        bytes_read = 0

        try:
            while self.running and self.fd is not None:
                # Use asyncio to wait for data
                try:
                    data = await loop.run_in_executor(
                        None,
                        lambda: os.read(self.fd, max_read_bytes) if self._select() else b""
                    )

                    if data:
                        # Successfully read data
                        bytes_read += len(data)
                        if bytes_read <= 100:  # Log first few reads
                            logger.debug(f"Read {len(data)} bytes from PTY")
                        decoded = data.decode("utf-8", errors="replace")
                        await self.send_output(decoded)
                    else:
                        # No data - short sleep to avoid busy waiting
                        await asyncio.sleep(0.05)

                except OSError:
                    # PTY closed
                    logger.info("PTY closed (OSError)")
                    break

        except Exception as e:
            # Log error but don't send to WebSocket (might be closed)
            logger.error(f"Error reading from PTY: {e}")
        finally:
            # Ensure running is set to False
            logger.debug(f"_read_from_pty ending, total bytes read: {bytes_read}")
            self.running = False

    def _select(self) -> bool:
        """Check if PTY has data to read (blocking with timeout)"""
        try:
            return select.select([self.fd], [], [], 0.1)[0] != []
        except:
            return False

    async def handle_input(self, data: str):
        """Handle input from WebSocket and write to PTY"""
        try:
            if self.fd is not None:
                os.write(self.fd, data.encode("utf-8"))
        except Exception as e:
            await self.send_error(f"Write error: {str(e)}")

    async def handle_resize(self, cols: int, rows: int):
        """Handle terminal resize - update PTY size and notify tmux"""
        try:
            # Validate size bounds
            if not (10 <= cols <= 500):
                logger.warning(f"Invalid cols value {cols}, must be between 10 and 500")
                return
            if not (5 <= rows <= 200):
                logger.warning(f"Invalid rows value {rows}, must be between 5 and 200")
                return

            # Update PTY size if fd is available
            if self.fd is not None:
                self._set_pty_size(self.fd, rows, cols)
                self.cols = cols
                self.rows = rows

                # Resize tmux pane explicitly (this is the critical step!)
                # tmux doesn't automatically resize the pane when PTY size changes
                session_name = self.task.tmux_session
                try:
                    # Use tmux resize-pane command to set the pane size
                    subprocess.run(
                        ["tmux", "resize-pane", "-t", session_name, "-x", str(cols), "-y", str(rows)],
                        capture_output=True,
                        timeout=1,
                        env=_clean_env_for_subprocess()
                    )
                    logger.info(f"tmux pane resized: {cols}x{rows}")
                except subprocess.TimeoutExpired:
                    logger.warning("tmux resize-pane timed out")
                except Exception as e:
                    logger.warning(f"Failed to resize tmux pane: {e}")

                # Also send SIGWINCH to ensure processes in the pane are notified
                if self.pid is not None:
                    try:
                        import signal
                        os.killpg(os.getpgid(self.pid), signal.SIGWINCH)
                    except ProcessLookupError:
                        pass
                    except Exception as e:
                        logger.warning(f"Failed to send SIGWINCH: {e}")

        except Exception as e:
            logger.warning(f"Error during terminal resize: {e}")

    async def handle_scroll_mode(self, action: str):
        """Handle scroll mode enter/exit commands"""
        session_name = self.task.tmux_session

        try:
            if action == 'enter':
                # Enter tmux copy-mode for scrolling history
                # Use -e flag to position at the bottom of history
                # This way we can scroll up into history
                result = subprocess.run(
                    ['tmux', 'copy-mode', '-e', '-t', session_name],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    env=_clean_env_for_subprocess()
                )
                if result.returncode != 0:
                    logger.warning(f"Failed to enter copy-mode: {result.stderr}")
                else:
                    logger.info(f"Entered copy-mode for session {session_name}")

            elif action == 'exit':
                # Exit tmux copy-mode by sending Escape
                result = subprocess.run(
                    ['tmux', 'send-keys', '-t', session_name, 'Escape'],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    env=_clean_env_for_subprocess()
                )
                if result.returncode != 0:
                    logger.warning(f"Failed to exit copy-mode: {result.stderr}")
                else:
                    logger.info(f"Exited copy-mode for session {session_name}")

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout during scroll mode {action}")
        except Exception as e:
            logger.error(f"Error during scroll mode {action}: {e}")

    async def handle_scroll(self, direction: str, page: bool = False):
        """Handle scroll commands in copy-mode"""
        session_name = self.task.tmux_session

        try:
            # Use tmux send-keys -X to execute copy-mode commands directly
            if page:
                if direction == 'up':
                    # page-up scrolls by one full page
                    result = subprocess.run(
                        ['tmux', 'send-keys', '-t', session_name, '-X', 'page-up'],
                        capture_output=True,
                        text=True,
                        timeout=2,
                        env=_clean_env_for_subprocess()
                    )
                else:
                    # page-down scrolls by one full page
                    result = subprocess.run(
                        ['tmux', 'send-keys', '-t', session_name, '-X', 'page-down'],
                        capture_output=True,
                        text=True,
                        timeout=2,
                        env=_clean_env_for_subprocess()
                    )
            else:
                # Line by line scrolling
                if direction == 'up':
                    result = subprocess.run(
                        ['tmux', 'send-keys', '-t', session_name, '-X', 'cursor-up'],
                        capture_output=True,
                        text=True,
                        timeout=2,
                        env=_clean_env_for_subprocess()
                    )
                else:
                    result = subprocess.run(
                        ['tmux', 'send-keys', '-t', session_name, '-X', 'cursor-down'],
                        capture_output=True,
                        text=True,
                        timeout=2,
                        env=_clean_env_for_subprocess()
                    )

            if result.returncode != 0:
                logger.warning(f"Failed to scroll {direction}: {result.stderr}")
            else:
                logger.debug(f"Scroll {direction} (page={page}) sent successfully")

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout during scroll {direction}")
        except Exception as e:
            logger.error(f"Error during scroll {direction}: {e}")

    async def send_output(self, data: str):
        """Send output to WebSocket"""
        try:
            await self.websocket.send_json({
                "type": "output",
                "data": data
            })
            logger.debug(f"Sent {len(data)} chars to WebSocket")
        except Exception as e:
            logger.warning(f"Failed to send output to WebSocket: {e}")
            self.running = False

    async def send_error(self, message: str):
        """Send error to WebSocket"""
        try:
            await self.websocket.send_json({
                "type": "error",
                "message": message
            })
        except:
            pass

    async def close(self):
        """Close terminal session and cleanup resources (does not close WebSocket)"""
        self.running = False

        if self.fd is not None:
            try:
                os.close(self.fd)
            except:
                pass
            self.fd = None

        if self.pid is not None:
            try:
                os.killpg(os.getpgid(self.pid), 9)  # Kill process group
            except:
                pass
            self.pid = None

        # Unregister from connection manager
        manager.disconnect(self.task.id, self.websocket)


async def get_websocket_terminal(
    websocket: WebSocket,
    token: str = Query(...),
    task_id: str = Query(...),
    db: Session = Depends(get_db)
) -> Optional[WebSocketTerminal]:
    """Authenticate and get WebSocket terminal handler"""

    # Verify token
    if not verify_token(token):
        await websocket.close(code=1008, reason="Unauthorized")
        return None

    # Get task
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        await websocket.close(code=1008, reason="Task not found")
        return None

    return WebSocketTerminal(websocket, task)

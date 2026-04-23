import subprocess
import logging
import os
import sys
from typing import List
from app.config import settings

logger = logging.getLogger(__name__)


def _clean_env_for_subprocess() -> dict:
    """
    Clean environment for subprocess to avoid PyInstaller library pollution.
    When running as a PyInstaller bundle, LD_LIBRARY_PATH and LD_PRELOAD
    may point to extracted temp directory containing bundled libraries that
    conflict with system binaries (e.g., tmux requiring a specific libtinfo).

    This function completely strips library-related environment variables
    to ensure system binaries use system libraries.
    """
    env = os.environ.copy()

    # Get PyInstaller temp directory if running as bundle
    pyinstaller_tmp = None
    if getattr(sys, 'frozen', False):
        pyinstaller_tmp = getattr(sys, '_MEIPASS', None)

    # Strip ALL library-related environment variables to prevent bundled
    # libraries from interfering with system binaries (like tmux)
    library_env_vars = [
        'LD_LIBRARY_PATH',
        'LD_PRELOAD',
        'LD_AUDIT',
        'LD_BIND_NOW',
        'LD_DEBUG',
        'LD_DYNAMIC_WEAK',
        'LD_ELFINFO',
        'LD_GCjv',
        'LD_HWCAP_PLAT',
        'LD_LIBRARY_PATH',
        'LD_ORIGIN',
        'LD_PRELOAD',
        'LD_PROFILE',
        'LD_SHOW_AUXV',
        'LD_TRACE_LOADED_OBJECTS',
        'LD_USE_LOAD_CACHE',
        'LD_VERBOSE',
        'LD_WARN',
        'LD_WRAPPER_PATH',
    ]

    for var in library_env_vars:
        if var in env:
            del env[var]

    # Also remove PyInstaller-specific PYTHONPATH entries
    if 'PYTHONPATH' in env:
        paths = env['PYTHONPATH'].split(':')
        if pyinstaller_tmp:
            paths = [p for p in paths if p and not p.startswith(pyinstaller_tmp) and not p.startswith('/tmp/_ME')]
        if paths:
            env['PYTHONPATH'] = ':'.join(paths)
        else:
            del env['PYTHONPATH']

    # Ensure TERM is set (systemd services don't have a terminal)
    if 'TERM' not in env or not env['TERM']:
        env['TERM'] = 'xterm-256color'

    return env


class TmuxService:
    """Service for tmux session management"""

    @staticmethod
    def session_exists(session_name: str) -> bool:
        """Check if a tmux session exists"""
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", session_name],
                capture_output=True,
                text=True,
                env=_clean_env_for_subprocess()
            )
            exists = result.returncode == 0
            logger.debug(f"Checking if tmux session '{session_name}' exists: {exists}")
            return exists
        except Exception as e:
            logger.error(f"Error checking tmux session: {e}")
            return False

    @staticmethod
    def create_session(session_name: str, working_dir: str) -> tuple[bool, str]:
        """
        Create a new tmux session with history limit set to 50000 lines
        Returns: (success, message)
        """
        logger.info(f"Creating tmux session: {session_name}")
        logger.debug(f"  Working directory: {working_dir}")

        # Check if session already exists
        if TmuxService.session_exists(session_name):
            logger.info(f"Tmux session '{session_name}' already exists")
            return True, "Session already exists"

        try:
            # Create session with working directory
            # Set both global (-g) and window (-w) history-limit to ensure all windows have 50000 lines
            # Global setting affects new windows, window setting affects current window
            # Use clean environment to avoid PyInstaller library pollution
            # Quote the session name to handle spaces and special characters
            import shlex
            quoted_session = shlex.quote(session_name)
            quoted_dir = shlex.quote(working_dir)
            # For send-keys cd command, ~ needs shell expansion so don't quote it
            # Use double quotes to handle spaces while allowing ~ expansion
            if working_dir.startswith('~'):
                cd_dir = f'"{working_dir}"'  # Double quotes allow ~ expansion
            else:
                cd_dir = quoted_dir
            cmd = f'tmux new-session -d -s {quoted_session} -c {quoted_dir} \\; set-option -g history-limit 50000 \\; set-option -w history-limit 50000 \\; set -g status off \\; send-keys "cd {cd_dir}" C-m'
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                env=_clean_env_for_subprocess()
            )

            if result.returncode != 0:
                logger.error(f"Failed to create tmux session: {result.stderr}")
                return False, result.stderr or "Failed to create session"

            logger.info(f"Tmux session created: {session_name} with history-limit 50000, cd to {working_dir}")
            return True, "Session created successfully"
        except Exception as e:
            logger.exception(f"Exception creating tmux session: {e}")
            return False, str(e)

    @staticmethod
    def kill_session(session_name: str) -> tuple[bool, str]:
        """
        Kill a tmux session
        Returns: (success, message)
        """
        logger.info(f"Killing tmux session: {session_name}")
        try:
            if not TmuxService.session_exists(session_name):
                logger.info(f"Tmux session '{session_name}' does not exist")
                return True, "Session does not exist"

            result = subprocess.run(
                ["tmux", "kill-session", "-t", session_name],
                capture_output=True,
                text=True,
                env=_clean_env_for_subprocess()
            )

            if result.returncode == 0:
                logger.info(f"Tmux session killed: {session_name}")
                return True, "Session killed successfully"
            else:
                logger.error(f"Failed to kill tmux session: {result.stderr}")
                return False, result.stderr or "Failed to kill session"
        except Exception as e:
            logger.exception(f"Exception killing tmux session: {e}")
            return False, str(e)

    @staticmethod
    def list_sessions() -> List[str]:
        """List all tmux sessions"""
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
                env=_clean_env_for_subprocess()
            )

            if result.returncode == 0:
                sessions = result.stdout.strip().split("\n")
                logger.debug(f"Found {len(sessions)} tmux sessions")
                return [s for s in sessions if s]
            return []
        except Exception as e:
            logger.error(f"Error listing tmux sessions: {e}")
            return []

    @staticmethod
    def get_session_prefix_sessions() -> List[str]:
        """Get all sessions with our prefix"""
        all_sessions = TmuxService.list_sessions()
        return [s for s in all_sessions if s.startswith(settings.tmux_session_prefix)]

    @staticmethod
    def capture_history(session_name: str) -> tuple[bool, str]:
        """
        Capture terminal history from tmux session
        Returns: (success, history_content or error_message)
        """
        logger.debug(f"Capturing history from tmux session: {session_name}")

        # Check if session exists
        if not TmuxService.session_exists(session_name):
            logger.warning(f"Cannot capture history: session '{session_name}' does not exist")
            return False, "Session does not exist"

        import tempfile
        import os

        try:
            # Create a temporary file to store the captured output
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp_file:
                tmp_path = tmp_file.name

            # Use tmux capture-pane to capture the entire scrollback history
            # -S - captures all history (starting from the beginning)
            # -p prints to stdout
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", session_name, "-S", "-", "-p"],
                capture_output=True,
                text=True,
                check=False,
                env=_clean_env_for_subprocess()
            )

            if result.returncode != 0:
                logger.error(f"Failed to capture tmux history: {result.stderr}")
                return False, result.stderr or "Failed to capture history"

            # Write captured content to temp file
            with open(tmp_path, 'w') as f:
                f.write(result.stdout)

            # Read the content back
            with open(tmp_path, 'r') as f:
                history_content = f.read()

            # Clean up temp file
            os.unlink(tmp_path)

            logger.debug(f"Captured {len(history_content)} characters from session '{session_name}'")
            return True, history_content

        except Exception as e:
            logger.exception(f"Exception capturing tmux history: {e}")
            # Clean up temp file if it exists
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            return False, str(e)

    @staticmethod
    def send_keys(session_name: str, keys: str) -> tuple[bool, str]:
        """
        Send keys to a tmux session
        Args:
            session_name: tmux session name
            keys: Keys to send to the session
        Returns:
            (success, message) tuple
        """
        logger.info(f"Sending keys to tmux session: {session_name}")

        # Check if session exists
        if not TmuxService.session_exists(session_name):
            logger.warning(f"Cannot send keys: session '{session_name}' does not exist")
            return False, f"Session '{session_name}' does not exist"

        try:
            # Use send-keys to send the keys to the session
            result = subprocess.run(
                ["tmux", "send-keys", "-t", session_name, keys],
                capture_output=True,
                text=True,
                check=False,
                env=_clean_env_for_subprocess()
            )

            if result.returncode != 0:
                logger.error(f"Failed to send keys to tmux session: {result.stderr}")
                return False, result.stderr or "Failed to send keys"

            logger.info(f"Keys sent to session '{session_name}' successfully")
            return True, "Keys sent successfully"

        except Exception as e:
            logger.exception(f"Exception sending keys to tmux session: {e}")
            return False, str(e)

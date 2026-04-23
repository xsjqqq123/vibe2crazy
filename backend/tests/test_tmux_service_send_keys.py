import pytest
from app.services.tmux_service import TmuxService

def test_send_keys_to_session():
    """Test sending keys to tmux session"""
    success, msg = TmuxService.send_keys("test-session", "echo 'hello'")
    # Expected to fail if session doesn't exist, but method should exist
    assert isinstance(success, bool)
    assert isinstance(msg, str)
    assert success is False  # Session doesn't exist
    assert "does not exist" in msg


def test_send_keys_integration():
    """Integration test: send keys to real tmux session"""
    import tempfile
    import os

    # Create temp dir for session
    with tempfile.TemporaryDirectory() as tmpdir:
        session_name = "test-send-keys-session"

        # Create session
        success, msg = TmuxService.create_session(session_name, tmpdir)
        assert success is True

        try:
            # Send keys
            result, msg = TmuxService.send_keys(session_name, "echo 'test'")
            assert result is True
            assert msg == "Keys sent successfully"

            # Verify keys were sent by capturing history
            success, content = TmuxService.capture_history(session_name)
            assert success is True
            assert "echo 'test'" in content

        finally:
            # Clean up
            TmuxService.kill_session(session_name)


import logging
from typing import Dict, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts messages"""

    def __init__(self):
        # task_id -> list of WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, task_id: str, websocket: WebSocket):
        """Register a WebSocket connection for a task"""
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)
        logger.debug(f"WebSocket connected for task {task_id}, total connections: {len(self.active_connections[task_id])}")

    def disconnect(self, task_id: str, websocket: WebSocket):
        """Unregister a WebSocket connection"""
        if task_id in self.active_connections:
            try:
                self.active_connections[task_id].remove(websocket)
                logger.debug(f"WebSocket disconnected for task {task_id}, remaining: {len(self.active_connections[task_id])}")

                # Clean up empty lists
                if len(self.active_connections[task_id]) == 0:
                    del self.active_connections[task_id]
                    logger.debug(f"No more connections for task {task_id}")
            except ValueError:
                # WebSocket not in list
                pass

    async def broadcast_to_task(self, task_id: str, message: dict):
        """Broadcast a message to all connected WebSockets for a task"""
        if task_id not in self.active_connections:
            logger.debug(f"No active connections for task {task_id}")
            return

        # Remove disconnected WebSockets
        self.active_connections[task_id] = [
            ws for ws in self.active_connections[task_id]
            if not ws.client_state.DISCONNECTED
        ]

        # Send to all connected WebSockets
        disconnected = []
        for websocket in self.active_connections[task_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket for task {task_id}: {e}")
                disconnected.append(websocket)

        # Clean up disconnected WebSockets
        for ws in disconnected:
            self.disconnect(task_id, ws)

        logger.debug(f"Broadcast message to task {task_id}: {len(self.active_connections[task_id])} connections")


# Global connection manager instance
manager = ConnectionManager()

"""
WebSocket Connection Manager
Handles WebSocket connections for real-time chat updates
"""
from typing import Dict, List, Set
import json
import asyncio
import time
from fastapi import WebSocket, WebSocketDisconnect
from app.core.terminal_ui import ui


class ConnectionManager:
    """WebSocket connection manager for real-time updates"""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.connection_timestamps: Dict[WebSocket, float] = {}
        self.cleanup_task: asyncio.Task = None
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        """Start the background cleanup task"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_connections())

    async def connect(self, websocket: WebSocket, project_id: str):
        """Connect a new WebSocket client"""
        await websocket.accept()

        # Initialize connection list if needed
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []

        # Add new connection to the list (allow multiple connections per project)
        self.active_connections[project_id].append(websocket)
        self.connection_timestamps[websocket] = time.time()

        ui.info(f"WebSocket connected for project {project_id}. Total connections: {len(self.active_connections[project_id])}", "WebSocket")

    async def disconnect(self, websocket: WebSocket, project_id: str):
        """Disconnect a WebSocket client"""
        if project_id in self.active_connections:
            try:
                self.active_connections[project_id].remove(websocket)
                # Remove timestamp tracking
                self.connection_timestamps.pop(websocket, None)

                ui.info(f"WebSocket disconnected for project {project_id}. Remaining connections: {len(self.active_connections[project_id])}", "WebSocket")
            except ValueError:
                # Connection was already removed
                self.connection_timestamps.pop(websocket, None)

            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
                ui.info(f"No more connections for project {project_id}, cleaned up", "WebSocket")

    async def send_message(self, project_id: str, message_data: dict):
        """Send message to all WebSocket connections for a project"""
        if project_id in self.active_connections:
            for connection in self.active_connections[project_id][:]:
                try:
                    await connection.send_text(json.dumps(message_data))
                except Exception:
                    # Connection failed - remove it silently
                    await self._remove_dead_connection(connection, project_id)

    async def broadcast_status(self, project_id: str, status: str, data: dict = None):
        """Broadcast status update to all connections"""
        message = {
            "type": "status",
            "status": status,
            "data": data or {}
        }
        await self.send_message(project_id, message)

    async def broadcast_cli_output(self, project_id: str, output: str, cli_type: str):
        """Broadcast CLI output to all connections"""
        message = {
            "type": "cli_output",
            "output": output,
            "cli_type": cli_type
        }
        await self.send_message(project_id, message)

    async def broadcast_to_project(self, project_id: str, message_data: dict):
        """Broadcast message to all connections for a project (alias for send_message)"""
        await self.send_message(project_id, message_data)

    async def _remove_dead_connection(self, websocket: WebSocket, project_id: str):
        """Remove a dead connection and clean up"""
        try:
            if project_id in self.active_connections:
                self.active_connections[project_id].remove(websocket)
        except (ValueError, KeyError):
            pass

        # Remove timestamp tracking
        self.connection_timestamps.pop(websocket, None)

        # Clean up empty project lists
        if project_id in self.active_connections and not self.active_connections[project_id]:
            del self.active_connections[project_id]

    async def _cleanup_connections(self):
        """Background task to clean up stale connections"""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                current_time = time.time()
                stale_connections = []

                # Find connections older than 5 minutes without activity
                for websocket, timestamp in self.connection_timestamps.items():
                    if current_time - timestamp > 300:  # 5 minutes
                        stale_connections.append(websocket)

                # Test stale connections with ping
                for websocket in stale_connections:
                    try:
                        await websocket.ping()
                        # Update timestamp if ping successful
                        self.connection_timestamps[websocket] = current_time
                    except Exception:
                        # Connection is dead, find and remove it
                        for project_id, connections in list(self.active_connections.items()):
                            if websocket in connections:
                                await self._remove_dead_connection(websocket, project_id)
                                ui.info(f"Cleaned up stale WebSocket connection for project {project_id}", "WebSocket")
                                break

            except Exception as e:
                ui.error(f"Error in WebSocket cleanup task: {e}", "WebSocket")
                await asyncio.sleep(60)  # Wait longer on error

    def __del__(self):
        """Cleanup when manager is destroyed"""
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()


# Global connection manager instance
manager = ConnectionManager()
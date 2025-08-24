"""
Core interfaces and protocols for dependency injection
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Protocol


class WebSocketManagerProtocol(Protocol):
    """Protocol for WebSocket manager implementations"""
    
    async def send_message(self, project_id: str, message_data: dict) -> None:
        """Send message to all WebSocket connections for a project"""
        ...
    
    async def broadcast_status(self, project_id: str, status: str, data: dict = None) -> None:
        """Broadcast status update to all connections"""
        ...
    
    async def broadcast_cli_output(self, project_id: str, output: str, cli_type: str) -> None:
        """Broadcast CLI output to all connections"""
        ...
    
    async def broadcast_to_project(self, project_id: str, message_data: dict) -> None:
        """Broadcast message to all connections for a project"""
        ...


class DatabaseSessionProtocol(Protocol):
    """Protocol for database session implementations"""
    
    def add(self, instance: Any) -> None:
        """Add an instance to the session"""
        ...
    
    def commit(self) -> None:
        """Commit the current transaction"""
        ...
    
    def rollback(self) -> None:
        """Rollback the current transaction"""
        ...
    
    def close(self) -> None:
        """Close the session"""
        ...
    
    def get(self, entity: type, ident: Any) -> Optional[Any]:
        """Get an entity by its primary key"""
        ...


class LoggerProtocol(Protocol):
    """Protocol for logger implementations"""
    
    def info(self, message: str, category: str = "General") -> None:
        """Log info message"""
        ...
    
    def error(self, message: str, category: str = "General") -> None:
        """Log error message"""
        ...
    
    def warning(self, message: str, category: str = "General") -> None:
        """Log warning message"""
        ...
    
    def debug(self, message: str, category: str = "General") -> None:
        """Log debug message"""
        ...


class CLIDependencies:
    """Container for CLI dependencies"""
    
    def __init__(
        self,
        websocket_manager: WebSocketManagerProtocol,
        database_session: Optional[DatabaseSessionProtocol] = None,
        logger: Optional[LoggerProtocol] = None
    ):
        self.websocket_manager = websocket_manager
        self.database_session = database_session
        self.logger = logger


class DependencyContainer:
    """Simple dependency injection container"""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
    
    def register(self, service_name: str, service_instance: Any) -> None:
        """Register a service instance"""
        self._services[service_name] = service_instance
    
    def get(self, service_name: str) -> Any:
        """Get a service instance"""
        if service_name not in self._services:
            raise ValueError(f"Service '{service_name}' not registered")
        return self._services[service_name]
    
    def get_cli_dependencies(self) -> CLIDependencies:
        """Get CLI dependencies bundle"""
        return CLIDependencies(
            websocket_manager=self.get("websocket_manager"),
            database_session=self.get("database_session") if "database_session" in self._services else None,
            logger=self.get("logger") if "logger" in self._services else None
        )


# Global dependency container
container = DependencyContainer()

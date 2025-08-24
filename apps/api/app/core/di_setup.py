"""
Dependency Injection Setup
Configures and initializes the dependency injection container
"""
from app.core.interfaces import container, CLIDependencies
from app.core.websocket.manager import manager as websocket_manager
from app.core.terminal_ui import ui


def setup_dependencies():
    """Setup and register all dependencies in the container"""
    
    # Register core services
    container.register("websocket_manager", websocket_manager)
    container.register("logger", ui)
    
    print("✅ Dependency injection container initialized")


def get_cli_dependencies() -> CLIDependencies:
    """Get CLI dependencies from the container"""
    return container.get_cli_dependencies()


def create_cli_dependencies_with_db(db_session) -> CLIDependencies:
    """Create CLI dependencies with a specific database session"""
    return CLIDependencies(
        websocket_manager=container.get("websocket_manager"),
        database_session=db_session,
        logger=container.get("logger")
    )


def create_cli_manager(
    project_id: str,
    project_path: str,
    session_id: str,
    conversation_id: str,
    db_session
):
    """Factory function to create UnifiedCLIManager with proper dependency injection"""
    from app.services.cli.unified_manager import UnifiedCLIManager

    dependencies = create_cli_dependencies_with_db(db_session)
    return UnifiedCLIManager(
        project_id=project_id,
        project_path=project_path,
        session_id=session_id,
        conversation_id=conversation_id,
        db=db_session,
        dependencies=dependencies
    )


# Initialize dependencies on module import
setup_dependencies()

"""
Database manager for env-doctor.

Handles SQLite connection, session management, and table creation.
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from .models import (
    CompatibilityRule,
    Package,
    PackageDependency,
    PackageVersion,
    RuntimeProfile,
    StableStack,
    StableStackPackage,
    WheelAvailability,
)


class DatabaseManager:
    """
    Manages database connections and operations.
    
    Provides:
    - SQLite engine creation
    - Table creation
    - Session management
    - Connection pooling
    """
    
    def __init__(self, db_path: str) -> None:
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file (e.g., "~/.cache/env-doctor/db.sqlite")
        """
        self.db_path = Path(db_path).expanduser().resolve()
        self._engine: Engine | None = None
        
    def get_engine(self) -> Engine:
        """
        Get or create SQLAlchemy engine.
        
        Returns:
            SQLAlchemy engine instance
            
        Note:
            Uses StaticPool for SQLite to handle concurrent access properly.
        """
        if self._engine is None:
            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create engine with proper SQLite configuration
            db_url = f"sqlite:///{self.db_path}"
            self._engine = create_engine(
                db_url,
                echo=False,  # Set to True for SQL debugging
                connect_args={"check_same_thread": False},  # Allow multi-threaded access
                poolclass=StaticPool,  # Use static pool for SQLite
            )
            
        return self._engine
    
    def create_tables(self) -> None:
        """
        Create all database tables.
        
        This is idempotent - safe to call multiple times.
        Tables will only be created if they don't exist.
        """
        engine = self.get_engine()
        SQLModel.metadata.create_all(engine)
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.
        
        Yields:
            SQLModel Session instance
            
        Example:
            >>> manager = DatabaseManager("~/.cache/env-doctor/db.sqlite")
            >>> with manager.get_session() as session:
            ...     package = session.get(Package, uid)
            ...     print(package.name)
            
        Note:
            Automatically commits on success and rolls back on exception.
        """
        engine = self.get_engine()
        session = Session(engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def close(self) -> None:
        """
        Close database connection and cleanup resources.
        
        Should be called when done with the database manager.
        """
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
    
    def __enter__(self) -> "DatabaseManager":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Context manager exit - cleanup resources."""
        self.close()


def get_default_db_path() -> str:
    """
    Get default database path.
    
    Returns:
        Default path: ~/.cache/env-doctor/env-doctor.db
    """
    return str(Path.home() / ".cache" / "env-doctor" / "env-doctor.db")


def initialize_database(db_path: str | None = None) -> DatabaseManager:
    """
    Initialize database with tables.
    
    Args:
        db_path: Optional custom database path. Uses default if None.
        
    Returns:
        Initialized DatabaseManager instance
        
    Example:
        >>> manager = initialize_database()
        >>> with manager.get_session() as session:
        ...     packages = session.query(Package).all()
    """
    if db_path is None:
        db_path = get_default_db_path()
    
    manager = DatabaseManager(db_path)
    manager.create_tables()
    return manager

# Made with Bob

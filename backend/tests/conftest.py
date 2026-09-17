"""
Pytest configuration and fixtures for testing.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.database import Base
from app.models import Task


# Use in-memory SQLite for tests
@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def tmp_notebooks(tmp_path, monkeypatch):
    """Point the notebook root at a temp directory for the duration of a test.

    Works because ``settings.notebooks_path`` is a property that re-reads
    ``notebooks_dir`` on every access.
    """
    root = tmp_path / "notebooks"
    monkeypatch.setattr(settings, "notebooks_dir", str(root))
    yield root

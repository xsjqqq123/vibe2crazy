from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path
from app.config import settings

# Create database directory if it doesn't exist
db_path = settings.database_path
db_path.parent.mkdir(parents=True, exist_ok=True)

# Create engine with connection pool settings
# For SQLite, pool_size and max_overflow are ignored, but we set them for consistency
# check_same_thread=False is required for SQLite with multiple threads
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    pool_size=20,  # Increase pool size for concurrent connections
    max_overflow=30,  # Allow additional connections when pool is full
    pool_timeout=60,  # Wait up to 60 seconds for a connection
    pool_recycle=3600  # Recycle connections after 1 hour
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    from app.models import Project, Task, Session, CommandPreset
    Base.metadata.create_all(bind=engine)

    # Seed default command preset if it doesn't exist
    db = SessionLocal()
    try:
        existing = db.query(CommandPreset).filter(
            CommandPreset.command == "claude --dangerously-skip-permissions"
        ).first()

        if not existing:
            default_preset = CommandPreset(
                command="claude --dangerously-skip-permissions"
            )
            db.add(default_preset)
            db.commit()
            print("✓ Seeded default command preset")
    finally:
        db.close()

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Text, Integer, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum
import uuid


class TaskStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    merged = "merged"


class TaskStatusType(str, enum.Enum):
    running = "running"
    idle = "idle"


class CodeStatusType(str, enum.Enum):
    pending_review = "pending_review"
    ready_to_merge = "ready_to_merge"
    no_changes = "no_changes"


class CommandQueueStatus(str, enum.Enum):
    pending = "pending"
    executing = "executing"
    completed = "completed"


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False, index=True)
    git_path = Column(String, nullable=False)
    main_branch = Column(String, default="main")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    branch_name = Column(String, unique=True, nullable=False, index=True)
    worktree_path = Column(String, nullable=False)
    tmux_session = Column(String, unique=True, nullable=False)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.active)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # New status tracking fields
    task_status = Column(SQLEnum(TaskStatusType), default=TaskStatusType.idle)
    code_status = Column(SQLEnum(CodeStatusType), default=CodeStatusType.no_changes)
    last_task_status_check = Column(DateTime(timezone=True), nullable=True)
    last_code_status_check = Column(DateTime(timezone=True), nullable=True)
    last_merge_commit_hash = Column(String, nullable=True)
    extra_index_paths = Column(Text, nullable=True)  # Semicolon-separated paths for symbol indexing
    direct_on_branch = Column(Boolean, default=False)

    # Relationship
    project = relationship("Project", back_populates="tasks")
    command_queue = relationship("CommandQueue", back_populates="task", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    token = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)


class CommandQueue(Base):
    __tablename__ = "command_queue"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    status = Column(SQLEnum(CommandQueueStatus), default=CommandQueueStatus.pending)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    executed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship
    task = relationship("Task", back_populates="command_queue")


class CommandPreset(Base):
    __tablename__ = "command_presets"

    id = Column(Integer, primary_key=True, index=True)
    command = Column(String(1000), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TunnelConfig(Base):
    """Tunnel configuration for remote access."""
    __tablename__ = "tunnel_config"

    id = Column(Integer, primary_key=True)  # Single row only (id=1)
    token = Column(String(64), nullable=True)  # 64-char hex token from server
    server_url = Column(String(255), nullable=True)  # Optional override for .env TUNNEL_SERVER_URL
    use_tls = Column(Boolean, default=True, server_default="1")
    verify_tls = Column(Boolean, default=False, server_default="0")
    status = Column(String(20), default="disabled")  # disabled, connecting, connected, disconnected
    remote_url = Column(String(255), nullable=True)  # Assigned remote access URL
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SystemSettings(Base):
    """System-wide settings stored in database."""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True)  # Single row only (id=1)
    password_hash = Column(String(128), nullable=True)  # Hashed password
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

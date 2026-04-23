"""Initial database schema

This is the initial migration that creates all core tables for Vibe2Crazy:
- projects: Git project repositories
- sessions: User authentication sessions
- tasks: Development tasks with git worktrees and tmux sessions
- command_queue: Terminal command queue for task automation

Revision ID: 6b947996d2bb
Revises:
Create Date: 2026-02-16 21:58:07.854071

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b947996d2bb'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all initial database tables."""
    # Create projects table
    op.create_table('projects',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('git_path', sa.String(), nullable=False),
    sa.Column('main_branch', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projects_name'), 'projects', ['name'], unique=True)

    # Create sessions table for authentication
    op.create_table('sessions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('token', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sessions_token'), 'sessions', ['token'], unique=True)

    # Create tasks table for development tasks
    op.create_table('tasks',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('project_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('branch_name', sa.String(), nullable=False),
    sa.Column('worktree_path', sa.String(), nullable=False),
    sa.Column('tmux_session', sa.String(), nullable=False),
    sa.Column('status', sa.Enum('active', 'completed', 'merged', name='taskstatus'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('task_status', sa.Enum('running', 'idle', name='taskstatustype'), nullable=True),
    sa.Column('code_status', sa.Enum('pending_review', 'ready_to_merge', 'no_changes', name='codestatustype'), nullable=True),
    sa.Column('last_task_status_check', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_code_status_check', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_merge_commit_hash', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tmux_session')
    )
    op.create_index(op.f('ix_tasks_branch_name'), 'tasks', ['branch_name'], unique=True)
    op.create_index(op.f('ix_tasks_project_id'), 'tasks', ['project_id'], unique=False)

    # Create command_queue table for terminal command automation
    op.create_table('command_queue',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('task_id', sa.String(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('pending', 'executing', 'completed', name='commandqueuestatus'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # Index on task_id for filtering commands by task
    op.create_index(op.f('ix_command_queue_task_id'), 'command_queue', ['task_id'], unique=False)
    # Index on status for efficient filtering by command status (pending, executing, completed)
    op.create_index(op.f('ix_command_queue_status'), 'command_queue', ['status'], unique=False)


def downgrade() -> None:
    """Drop all database tables in reverse order of creation."""
    # Drop command_queue table first (depends on tasks)
    op.drop_index(op.f('ix_command_queue_status'), table_name='command_queue')
    op.drop_index(op.f('ix_command_queue_task_id'), table_name='command_queue')
    op.drop_table('command_queue')

    # Drop tasks table (depends on projects)
    op.drop_index(op.f('ix_tasks_project_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_branch_name'), table_name='tasks')
    op.drop_table('tasks')

    # Drop sessions table
    op.drop_index(op.f('ix_sessions_token'), table_name='sessions')
    op.drop_table('sessions')

    # Drop projects table last (no dependencies)
    op.drop_index(op.f('ix_projects_name'), table_name='projects')
    op.drop_table('projects')

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vibe2Crazy is a single-user remote code editing and collaboration tool built with:
- **Frontend**: Vue 3 + Vite + TypeScript + Monaco Editor + Tailwind CSS
- **Backend**: Python + FastAPI + WebSocket + SQLAlchemy
- **Terminal**: tmux sessions with WebSocket connectivity (WebSSH2-style)
- **Isolation**: Git worktrees for per-task development environments
-
## Development Commands
8886766867
```bash
# From project root
./deploy.sh start    # Start both frontend and backend
./deploy.sh stop     # Stop both services
./deploy.sh restart  # Restart both services
./deploy.sh status   # Check running status
```

## Architecture

### Backend Structure

```
backend/app/
├── main.py              # FastAPI entry point, WebSocket terminal, background task monitor
├── config.py            # Configuration management (loads from .env)
├── database.py          # SQLAlchemy session management
├── models.py            # ORM models (Project, Task, Session, CommandQueue, CommandPreset)
├── schemas.py           # Pydantic schemas for request/response validation
├── auth.py              # Session-based authentication
├── routers/             # API endpoint modules
│   ├── auth.py          # POST /auth/login, POST /auth/logout
│   ├── projects.py      # CRUD operations for projects
│   ├── tasks.py         # CRUD operations for tasks + worktree management
│   ├── files.py         # File reading/writing operations
│   ├── git.py           # Git operations (diff, status, merge)
│   ├── filesystem.py    # Directory listing for path browser
│   ├── terminals.py     # Terminal history endpoint
│   ├── queues.py        # Command queue CRUD for tasks
│   ├── command_presets.py # Saved command presets
│   └── symbols.py       # Symbol indexing and definition lookup
├── services/            # Business logic layer
│   ├── git_service.py      # Git worktree operations (create, delete, merge, diff)
│   ├── tmux_service.py     # tmux session management (create, attach, kill)
│   ├── file_service.py     # File system operations
│   ├── filesystem_service.py # Directory listing with security validation
│   ├── queue_service.py    # Command queue management
│   ├── ctags_service.py    # Symbol indexing using ctags
│   └── task_monitor_service.py # Background task status monitoring
└── websocket/
    ├── terminal.py      # WebSocket handler for terminal I/O
    └── manager.py       # WebSocket connection manager
```

**Key Pattern**: Routers handle HTTP requests, services encapsulate business logic. All Git operations go through `git_service.py`, tmux operations through `tmux_service.py`.

**Background Tasks**: On startup, `main.py` spawns a background monitor (`TaskMonitorService`) that polls every 10 seconds to update task/code status for all active tasks.

### Frontend Structure

```
frontend/src/
├── main.ts              # Application entry point
├── router/index.ts      # Vue Router configuration with auth guards
├── views/               # Page components
│   ├── LoginView.vue
│   ├── ProjectsView.vue
│   ├── TasksView.vue
│   └── CodeReviewView.vue
├── components/          # Reusable components
│   └── DirectoryAutocomplete.vue  # Directory path browser with autocomplete
├── composables/         # Vue composition functions (useAuth, useApi)
├── api/                 # API client functions
└── store/               # Pinia state management
```

**Key Pattern**: Router guards enforce authentication via `useAuth()` composable. All API calls use the centralized API client.

### Key Features

#### Directory Browser
The Directory Browser provides a secure, interactive way to select directory paths when creating projects:

- **Endpoint**: `GET /api/filesystem/directories?path={directory_path}`
- **Component**: `DirectoryAutocomplete.vue` with keyboard navigation
- **Service**: `FilesystemService.list_directories()` with path validation
- **Security**: Prevents directory traversal (`..`), filters hidden directories
- **Features**: Real-time directory loading, breadcrumb navigation, accessible design
- **Response**: Returns sorted list of absolute directory paths as strings

#### Pull Button
The Pull button (available in CodeReviewView) allows fetching latest changes from the remote repository into a task worktree:

- **Endpoint**: `POST /api/tasks/{task_id}/pull`
- **Service Method**: `GitService.pull_worktree(worktree_path, remote_branch)`
- **State Check**: `GitService.can_pull()` determines if button is enabled
- **Response**: Returns `PullResponse` with `success`, `message`, and `commit_hash`
- **Error Handling**: Conflicts are shown in error dialog, user can resolve in terminal
- **UI**: Blue success toast ("Latest changes pulled") or error dialog with "Open Terminal" option

### Data Flow

0. **Project Creation**: When creating a project, users can either point to an existing Git repository or use the Directory Browser to select a path. If the path is not a Git repo, selecting "Initialize Git Repository" runs `git init` to create one. This enables Vibe2Crazy to manage the project with Git worktrees.

1. **Task Creation**: When a task is created, `git_service.create_worktree()` creates a Git worktree at `{PROJECTS_DIR}/{project_id}/{task_id}` and `tmux_service.create_session()` creates a tmux session named `v2d-{task_id}`.

2. **Terminal Access**: WebSocket at `/ws/terminal?token={session_token}&task_id={task_id}` connects to the tmux session. Terminal I/O is bidirectional via JSON messages with `type: "input"`, `type: "resize"`, and `type: "scroll_mode"`.

3. **Code Review**: Frontend fetches changed files via `/api/git/changes?task_id={id}`, gets diffs via `/api/git/diff`, and displays side-by-side comparison using Monaco Editor.

4. **Merge Workflow**: Auto-commit worktree changes → squash merge to main branch → delete worktree and branch.

5. **Pull Workflow**: Pull latest changes from `origin/{main_branch}` into worktree → updates commits and changed files → conflicts (if any) must be resolved manually in terminal.

### Terminal Scroll Mode

The terminal supports a scroll mode for viewing tmux history (up to 50,000 lines):

- **Trigger**: Mouse wheel scroll up at buffer top, or Page Up key
- **UI**: Header shows "Scroll Mode" in amber color during scroll mode
- **Navigation**: Mouse wheel or Page Up/Down keys scroll through tmux history
- **Exit**: Press ESC key to exit scroll mode and return to normal terminal
- **Implementation**: Frontend sends `scroll_mode` message to backend, which enters tmux copy-mode

#### Symbol Indexing

Symbol indexing provides code navigation capabilities using ctags:

- **Endpoint**: `POST /api/symbols/index` starts async indexing job
- **Service**: `ctags_service.py` manages indexing jobs with caching
- **Lookup**: `GET /api/symbols/definition?symbol_name={name}` finds symbol definitions
- **Features**: Async job status tracking, cached indexes per project, symbol definition snippets
- **Integration**: Used in CodeReviewView's SymbolOutline component

#### Command Queue

Command queue enables sending commands to terminal from outside the WebSocket:

- **Endpoints**: `GET/POST/DELETE /api/tasks/{task_id}/queue`
- **Service**: `queue_service.py` manages queue CRUD
- **Model**: `CommandQueue` with status (pending/executing/completed)
- **Use Case**: External tools can queue commands for tasks

#### Task Status Monitoring
fjkljfdasfdsafsf
Background service monitors task activity:

- **Service**: `TaskMonitorService` runs every 10 seconds
- **Task Status**: `running` (active terminal process) or `idle`
- **Code Status**: `pending_review`, `ready_to_merge`, or `no_changes`
- **Detection**: Checks tmux for running processes, git diff for code changes

## Configuration

Backend environment variables (`backend/.env`):
- `VIBE2CRAZY_PASSWORD` - Login password (default: "password")
- `PROJECTS_DIR` - Directory for Git worktrees (default: "./projects")
- `DATABASE_URL` - SQLite database path (default: "sqlite:///./data/vibe2crazy.db")
- `GIT_DEFAULT_BRANCH` - Default branch name (default: "main")
- `SESSION_EXPIRE_HOURS` - Session token expiration (default: 24)

## Important Constraints

- **Single-user only**: No multi-user collaboration or permissions
- **Git repositories**: Projects can be created from existing Git repos or initialized with `git init`
- **tmux required**: Terminal sessions require tmux to be installed
- **ctags optional**: Required for symbol indexing feature (`apt install universal-ctags`)
- **Path validation**: All file paths are validated to prevent directory traversal
- **Manual conflict resolution**: Merge conflicts must be resolved manually in the main repo

## Adding New Features

1. **Backend endpoint**: Add router in `backend/app/routers/`, include in `main.py`
2. **Frontend view**: Add component in `frontend/src/views/`, register route in `router/index.ts`
3. **API client**: Add function in `frontend/src/api/` for backend communication

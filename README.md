# Vibe2Crazy - Remote Code Editing Tool

A single-user remote code editing and collaboration tool with Git worktree isolation, persistent terminal sessions, and web-based code review.

## Features

- **Authentication**: Simple password-based login
- **Project Management**: Create and manage Git-based projects
- **Task Isolation**: Each task gets its own Git worktree and tmux session
- **Persistent Terminals**: Web-based terminals that survive page refreshes
- **Code Review**: Built-in diff viewer and editor
- **One-Click Merge**: Squash merge changes to main branch
- **Dark/Light Theme**: Toggle between themes
- **Responsive Design**: Works on desktop and mobile

## Tech Stack

- **Frontend**: Vue 3 + Vite + TypeScript
- **Backend**: Python + FastAPI + WebSocket
- **Database**: SQLite + SQLAlchemy
- **Terminal**: tmux + WebSocket (WebSSH2-style)
- **Editor**: Monaco Editor (VS Code's editor)

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Git
  git config --global user.email "you@example.com"
  git config --global user.name "Your Name"
- tmux

### Installation

1. **Clone the repository**
```bash
git clone <repo-url>
cd vibe2crazy
```

2. **Set up the backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Set up the frontend**
```bash
cd ../frontend
npm install
```

4. **Configure environment**
```bash
cd ..
cp backend/.env.example backend/.env
# Edit backend/.env and set your password
```

5. **Initialize database**
```bash
cd backend
source venv/bin/activate
python -c "from app.database import init_db; init_db()"
```

### Development

**Start backend** (from backend directory):
```bash
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8863
```

**Start frontend** (from frontend directory):
```bash
npm run dev
```

Access the application at `http://localhost:5173`

### Deployment

The project includes a deployment script that supports both development and production modes.

#### Development Mode

```bash
./deploy.sh start      # 启动开发模式 (前端 5173, 后端 8863)
./deploy.sh stop       # 停止开发模式
./deploy.sh restart    # 重启开发模式
./deploy.sh status     # 查看开发模式状态
```

#### Production Mode

```bash
./deploy.sh start-prod     # 启动生产模式 (前端 8864, 后端 8863)
./deploy.sh stop-prod      # 停止生产模式
./deploy.sh restart-prod   # 重启生产模式
./deploy.sh status-prod    # 查看生产模式状态
./deploy.sh build          # 仅构建前端
```

#### Combined Commands

```bash
./deploy.sh status-all    # 查看所有服务状态（开发+生产）
```

#### Simultaneous Operation

开发和生产模式可以同时运行在不同端口上：
- **开发模式**: 前端 5173 (Vite dev server), 后端 8863 (Uvicorn with auto-reload)
- **生产模式**: 前端 8864 (Python http.server), 后端 8863 (Uvicorn)

This allows you to run development mode for active work while keeping production mode available for testing or demonstration.

#### Logging

日志文件位置：
- 开发模式: `logs/frontend.log`, `logs/backend.log`
- 生产模式: `logs/frontend-prod.log`, `logs/backend-prod.log`

### Production (Manual)

**Build frontend**:
```bash
cd frontend
npm run build
```

**Run backend**:
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8863
```

Or use the provided systemd service (see `deploy/vibe2crazy.service`).

## Configuration

Environment variables (see `backend/.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `VIBE2CRAZY_PASSWORD` | Login password | `password` |
| `PROJECTS_DIR` | Directory for worktrees | `./projects` |
| `DATABASE_URL` | SQLite database path | `sqlite:///./data/vibe2crazy.db` |
| `GIT_DEFAULT_BRANCH` | Default Git branch | `main` |
| `SESSION_EXPIRE_HOURS` | Session expiration | `24` |

## Usage

1. **Login** with your configured password
2. **Create a Project** pointing to an existing Git repository
3. **Create a Task** - this creates a Git worktree and tmux session
4. **Open the Terminal** to run commands (e.g., `claude code cli`)
5. **Review Changes** in the code editor
6. **Merge** your changes to the main branch

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (Vue)                        │
│  Login | Projects | Tasks | Code Review + Monaco Editor     │
└─────────────────────────────────────────────────────────────┘
                              │
                    HTTP/WebSocket
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  Auth | Projects | Tasks | Files | Git | WebSocket Terminal  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      System Resources                        │
│  Git Worktree | Tmux Sessions | SQLite Database              │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
vibe2crazy/
├── backend/           # Python FastAPI backend
│   └── app/
│       ├── main.py           # FastAPI application
│       ├── models.py         # SQLAlchemy models
│       ├── schemas.py        # Pydantic schemas
│       ├── routers/          # API endpoints
│       ├── services/         # Git, Tmux, File services
│       └── websocket/        # WebSocket terminal handler
├── frontend/          # Vue 3 frontend
│   └── src/
│       ├── views/            # Page components
│       ├── components/       # Reusable components
│       ├── composables/      # Vue composition functions
│       ├── api/              # API client
│       └── router/           # Vue Router config
├── projects/           # Git worktrees storage
└── data/               # SQLite database
```

## Development

### Running Tests

Backend:
```bash
cd backend
pytest
```

Frontend:
```bash
cd frontend
npm run lint
```

### Adding New Features

1. Backend: Add router in `backend/app/routers/`
2. Frontend: Add view in `frontend/src/views/`
3. Update API client in `frontend/src/api/`

## Security

- Password stored in environment variable (not in code)
- Session tokens with expiration
- Path validation to prevent directory traversal
- WebSocket authentication required

## Limitations

- Single-user only (no multi-user support)
- Manual merge conflict resolution required
- No code review comments/annotations

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.

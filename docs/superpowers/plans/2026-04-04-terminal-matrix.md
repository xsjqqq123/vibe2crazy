# Terminal Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a multi-terminal grid view to vibe2crazy that displays multiple terminals in a configurable layout with task monitoring and independent session support.

**Architecture:** Frontend uses Vue 3 with Pinia state management, xterm.js terminals in a CSS grid layout, WebSocket connections per terminal. Backend adds REST endpoints for task listing and matrix session management, plus a WebSocket endpoint for matrix terminal sessions using tmux.

**Tech Stack:** Vue 3, Pinia, xterm.js, FastAPI, WebSocket, tmux, TypeScript, Tailwind CSS

---

## File Structure

| File | Purpose |
|------|---------|
| `frontend/src/views/MatrixView.vue` | Page container with header controls |
| `frontend/src/components/MatrixTerminal.vue` | Single terminal instance with xterm.js |
| `frontend/src/store/matrixStore.ts` | Pinia store for layout and state |
| `frontend/src/api/matrix.ts` | API client for matrix endpoints |
| `frontend/src/router/index.ts` | Add /matrix route (modify) |
| `frontend/src/views/ProjectsView.vue` | Add matrix button (modify) |
| `backend/app/routers/matrix.py` | REST endpoints for matrix |
| `backend/app/websocket/matrix_terminal.py` | WebSocket handler for matrix terminals |
| `backend/app/main.py` | Register router and WebSocket (modify) |

---

### Task 1: Backend Matrix Router - GET /api/tasks/all Endpoint

**Files:**
- Create: `backend/app/routers/matrix.py`
- Modify: `backend/app/main.py:94` (add router import and include)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_matrix.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Project, Task, TaskStatus

client = TestClient(app)

@pytest.fixture
def auth_header():
    """Get auth header for testing"""
    response = client.post("/auth/login", json={"password": "password"})
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def sample_project():
    """Create a sample project for testing"""
    db = SessionLocal()
    project = Project(
        id="test-project-1",
        name="TestProject",
        git_path="/tmp/test_repo",
        main_branch="main"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project
    db.delete(project)
    db.commit()
    db.close()

@pytest.fixture
def sample_tasks(sample_project):
    """Create sample tasks for testing"""
    db = SessionLocal()
    tasks = []
    for i in range(3):
        task = Task(
            id=f"test-task-{i}",
            project_id=sample_project.id,
            name=f"Task{i}",
            branch_name=f"task-{i}-branch",
            worktree_path=f"/tmp/test_repo/worktrees/task{i}",
            tmux_session=f"v2d-task-{i}",
            status=TaskStatus.active
        )
        db.add(task)
        tasks.append(task)
    db.commit()
    for t in tasks:
        db.refresh(t)
    yield tasks
    for t in tasks:
        db.delete(t)
    db.commit()
    db.close()

def test_get_all_tasks(auth_header, sample_tasks):
    """Test GET /api/tasks/all returns all tasks with project info"""
    response = client.get("/api/tasks/all", headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert len(data["tasks"]) >= 3
    for task in data["tasks"]:
        assert "id" in task
        assert "name" in task
        assert "project_id" in task
        assert "project_name" in task
        assert "status" in task

def test_get_all_tasks_unauthorized():
    """Test GET /api/tasks/all requires authentication"""
    response = client.get("/api/tasks/all")
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd vibe2crazy/backend && pytest tests/test_matrix.py::test_get_all_tasks -v`
Expected: FAIL with "404 Not Found" or "route not found"

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/routers/matrix.py`:

```python
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Project, Task
from app.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["matrix"])


class TaskInfoResponse:
    """Response model for task info in matrix"""
    id: str
    name: str
    project_id: str
    project_name: str
    status: str


@router.get("/tasks/all")
async def get_all_tasks(
    db: Session = Depends(get_db),
    current_user = Depends(require_auth)
):
    """Get all tasks across all projects for matrix view"""
    logger.info("Fetching all tasks for matrix view")

    tasks = db.query(Task).join(Project).order_by(
        Project.name,
        Task.created_at
    ).all()

    result = []
    for task in tasks:
        project = task.project
        result.append({
            "id": task.id,
            "name": task.name,
            "project_id": task.project_id,
            "project_name": project.name if project else "",
            "status": task.task_status.value if task.task_status else "idle"
        })

    logger.info(f"Found {len(result)} tasks")
    return {"tasks": result}
```

- [ ] **Step 4: Register router in main.py**

Modify `backend/app/main.py` line 13, add import:

```python
from app.routers import auth, projects, tasks, files, git, terminals, queues, command_presets, filesystem, symbols, global_terminal, tunnel, config, matrix
```

Modify `backend/app/main.py` after line 95 (after `app.include_router(config.router)`), add:

```python
app.include_router(matrix.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd vibe2crazy/backend && pytest tests/test_matrix.py::test_get_all_tasks -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd vibe2crazy
git add backend/app/routers/matrix.py backend/app/main.py backend/tests/test_matrix.py
git commit -m "feat: add GET /api/tasks/all endpoint for matrix view

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Backend Matrix Router - POST /api/matrix/sessions Endpoint

**Files:**
- Modify: `backend/app/routers/matrix.py:45` (add session endpoint)
- Modify: `backend/tests/test_matrix.py` (add tests)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_matrix.py`:

```python
def test_create_matrix_sessions(auth_header):
    """Test POST /api/matrix/sessions creates sessions"""
    response = client.post(
        "/api/matrix/sessions",
        json={"count": 4},
        headers=auth_header
    )
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert len(data["sessions"]) == 4
    for session in data["sessions"]:
        assert "index" in session
        assert "session_name" in session
        assert "exists" in session
        assert session["session_name"].startswith("v2d-matrix-")

def test_create_matrix_sessions_unauthorized():
    """Test POST /api/matrix/sessions requires authentication"""
    response = client.post("/api/matrix/sessions", json={"count": 4})
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd vibe2crazy/backend && pytest tests/test_matrix.py::test_create_matrix_sessions -v`
Expected: FAIL with "404 Not Found"

- [ ] **Step 3: Write minimal implementation**

Add to `backend/app/routers/matrix.py`:

```python
from app.services.tmux_service import TmuxService
from pydantic import BaseModel


class MatrixSessionsRequest(BaseModel):
    count: int


class MatrixSessionInfo(BaseModel):
    index: int
    session_name: str
    exists: bool


@router.post("/matrix/sessions")
async def create_matrix_sessions(
    request: MatrixSessionsRequest,
    current_user = Depends(require_auth)
):
    """Create or verify matrix terminal sessions"""
    logger.info(f"Creating/verifying {request.count} matrix sessions")

    sessions = []
    for i in range(1, request.count + 1):
        session_name = f"v2d-matrix-{i}"
        exists = TmuxService.session_exists(session_name)

        if not exists:
            success, msg = TmuxService.create_session(session_name, "~")
            if not success:
                logger.error(f"Failed to create matrix session {session_name}: {msg}")
                # Continue anyway, session might be created on reconnect

        sessions.append({
            "index": i,
            "session_name": session_name,
            "exists": exists or TmuxService.session_exists(session_name)
        })

    logger.info(f"Prepared {len(sessions)} matrix sessions")
    return {"sessions": sessions}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd vibe2crazy/backend && pytest tests/test_matrix.py::test_create_matrix_sessions -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd vibe2crazy
git add backend/app/routers/matrix.py backend/tests/test_matrix.py
git commit -m "feat: add POST /api/matrix/sessions endpoint for matrix terminals

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Backend WebSocket Handler for Matrix Terminals

**Files:**
- Create: `backend/app/websocket/matrix_terminal.py`
- Modify: `backend/app/main.py` (add WebSocket endpoint)

- [ ] **Step 1: Write the WebSocket handler**

Create `backend/app/websocket/matrix_terminal.py`:

```python
import asyncio
import json
import pty
import os
import select
import subprocess
import fcntl
import struct
import logging
from typing import Optional
from fastapi import WebSocket, Query
from app.auth import verify_token
from app.services.tmux_service import TmuxService

logger = logging.getLogger(__name__)

SIZE_COLS = 80
SIZE_ROWS = 24


class MatrixWebSocketTerminal:
    """WebSocket terminal handler for matrix tmux sessions"""

    def __init__(self, websocket: WebSocket, session_name: str, index: int):
        self.websocket = websocket
        self.session_name = session_name
        self.index = index
        self.fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.running = False
        self.cols = SIZE_COLS
        self.rows = SIZE_ROWS

    async def start(self):
        """Start terminal session"""
        try:
            # Ensure tmux session exists
            if not TmuxService.session_exists(self.session_name):
                logger.info(f"Creating matrix tmux session: {self.session_name}")
                success, msg = TmuxService.create_session(self.session_name, "~")
                if not success:
                    logger.error(f"Failed to create matrix tmux session: {msg}")
                    await self.send_error(f"Failed to create tmux session: {msg}")
                    await self.close()
                    return

            # Create pseudoterminal
            self.fd, slave_fd = pty.openpty()
            self._set_pty_size(self.fd, SIZE_ROWS, SIZE_COLS)
            logger.info(f"Matrix terminal {self.index} PTY created: {SIZE_COLS}x{SIZE_ROWS}")

            # Attach to tmux session
            env = os.environ.copy()
            env['TERM'] = env.get('TERM', 'xterm-256color')

            cmd = ["tmux", "attach", "-t", self.session_name]
            self.pid = subprocess.Popen(
                cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True,
                env=env
            ).pid

            os.close(slave_fd)
            self.running = True
            logger.info(f"Matrix terminal {self.index} started: fd={self.fd}, pid={self.pid}")

            asyncio.create_task(self._read_from_pty())

        except Exception as e:
            logger.error(f"Failed to start matrix terminal {self.index}: {e}")
            await self.send_error(f"Failed to start terminal: {str(e)}")
            await self.close()

    def _set_pty_size(self, fd, rows, cols):
        try:
            import termios
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        except Exception as e:
            logger.warning(f"Failed to set PTY size: {e}")

    async def _read_from_pty(self):
        loop = asyncio.get_event_loop()
        max_read_bytes = 1024 * 1024

        try:
            while self.running and self.fd is not None:
                try:
                    data = await loop.run_in_executor(
                        None,
                        lambda: os.read(self.fd, max_read_bytes) if self._select() else b""
                    )

                    if data:
                        decoded = data.decode("utf-8", errors="replace")
                        await self.send_output(decoded)
                    else:
                        await asyncio.sleep(0.05)

                except OSError:
                    logger.info(f"Matrix terminal {self.index} PTY closed (OSError)")
                    break

        except Exception as e:
            logger.error(f"Error reading from matrix PTY {self.index}: {e}")
        finally:
            self.running = False

    def _select(self) -> bool:
        try:
            return select.select([self.fd], [], [], 0.1)[0] != []
        except:
            return False

    async def handle_input(self, data: str):
        try:
            if self.fd is not None:
                os.write(self.fd, data.encode("utf-8"))
        except Exception as e:
            await self.send_error(f"Write error: {str(e)}")

    async def handle_resize(self, cols: int, rows: int):
        try:
            if not (10 <= cols <= 500 and 5 <= rows <= 200):
                return

            if self.fd is not None:
                self._set_pty_size(self.fd, rows, cols)
                self.cols = cols
                self.rows = rows

                try:
                    subprocess.run(
                        ["tmux", "resize-pane", "-t", self.session_name, "-x", str(cols), "-y", str(rows)],
                        capture_output=True,
                        timeout=1
                    )
                except:
                    pass

                if self.pid is not None:
                    try:
                        import signal
                        os.killpg(os.getpgid(self.pid), signal.SIGWINCH)
                    except:
                        pass

        except Exception as e:
            logger.warning(f"Error during matrix terminal {self.index} resize: {e}")

    async def handle_scroll_mode(self, action: str):
        try:
            if action == 'enter':
                subprocess.run(
                    ['tmux', 'copy-mode', '-e', '-t', self.session_name],
                    capture_output=True, text=True, timeout=2
                )
            elif action == 'exit':
                subprocess.run(
                    ['tmux', 'send-keys', '-t', self.session_name, 'Escape'],
                    capture_output=True, text=True, timeout=2
                )
        except Exception as e:
            logger.error(f"Error during scroll mode {action} on matrix {self.index}: {e}")

    async def handle_scroll(self, direction: str, page: bool = False):
        try:
            if page:
                cmd = 'page-up' if direction == 'up' else 'page-down'
            else:
                cmd = 'cursor-up' if direction == 'up' else 'cursor-down'

            subprocess.run(
                ['tmux', 'send-keys', '-t', self.session_name, '-X', cmd],
                capture_output=True, text=True, timeout=2
            )
        except Exception as e:
            logger.error(f"Error during scroll {direction} on matrix {self.index}: {e}")

    async def send_output(self, data: str):
        try:
            await self.websocket.send_json({"type": "output", "data": data})
        except Exception as e:
            logger.warning(f"Failed to send output on matrix {self.index}: {e}")
            self.running = False

    async def send_error(self, message: str):
        try:
            await self.websocket.send_json({"type": "error", "message": message})
        except:
            pass

    async def close(self):
        self.running = False
        if self.fd is not None:
            try:
                os.close(self.fd)
            except:
                pass
            self.fd = None
        if self.pid is not None:
            try:
                os.killpg(os.getpgid(self.pid), 9)
            except:
                pass
            self.pid = None
```

- [ ] **Step 2: Add WebSocket endpoint to main.py**

Add to `backend/app/main.py` after the global terminal WebSocket endpoint (around line 343), add:

```python
@app.websocket("/ws/matrix-terminal")
async def websocket_matrix_terminal(
    websocket: WebSocket,
    token: str = Query(...),
    index: int = Query(...)
):
    """WebSocket endpoint for matrix terminal access"""
    logger.info(f"Matrix terminal WebSocket connection request - index: {index}")
    await websocket.accept()

    # Verify token
    if not verify_token(token):
        logger.warning(f"Matrix terminal connection rejected - invalid token")
        await websocket.close(code=1008, reason="Unauthorized")
        return

    session_name = f"v2d-matrix-{index}"

    from app.websocket.matrix_terminal import MatrixWebSocketTerminal
    terminal = MatrixWebSocketTerminal(websocket, session_name, index)

    try:
        logger.info(f"Matrix terminal {index} started")
        await terminal.start()

        while True:
            try:
                data = await websocket.receive()

                if "text" in data:
                    message = data["text"]
                    try:
                        msg = json.loads(message)

                        if msg.get("type") == "input":
                            await terminal.handle_input(msg.get("data", ""))
                        elif msg.get("type") == "resize":
                            await terminal.handle_resize(
                                msg.get("cols", 80),
                                msg.get("rows", 24)
                            )
                        elif msg.get("type") == "scroll_mode":
                            action = msg.get("action")
                            if action in ("enter", "exit"):
                                await terminal.handle_scroll_mode(action)
                        elif msg.get("type") == "scroll":
                            direction = msg.get("direction")
                            page = msg.get("page", False)
                            if direction in ("up", "down"):
                                await terminal.handle_scroll(direction, page)

                    except json.JSONDecodeError:
                        pass
                elif "bytes" in data:
                    await terminal.handle_input(data["bytes"].decode("utf-8"))

            except WebSocketDisconnect as e:
                logger.info(f"Matrix terminal {index} WebSocket disconnected: {str(e)}")
                break
            except RuntimeError as e:
                if "Cannot call receive once disconnected" in str(e):
                    logger.info(f"Matrix terminal {index} WebSocket already disconnected")
                else:
                    logger.error(f"Matrix terminal {index} WebSocket error: {str(e)}")
                break
            except Exception as e:
                logger.error(f"Matrix terminal {index} WebSocket error: {str(e)}")
                break

    except Exception as e:
        logger.error(f"Matrix terminal {index} WebSocket setup failed: {str(e)}")
    finally:
        await terminal.close()
        logger.info(f"Matrix terminal {index} WebSocket connection closed")
```

- [ ] **Step 3: Commit**

```bash
cd vibe2crazy
git add backend/app/websocket/matrix_terminal.py backend/app/main.py
git commit -m "feat: add WebSocket endpoint for matrix terminals

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Frontend Matrix Store

**Files:**
- Create: `frontend/src/store/matrixStore.ts`

- [ ] **Step 1: Write the Pinia store**

Create `frontend/src/store/matrixStore.ts`:

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const STORAGE_KEY = 'vibe2crazy-matrix-settings'

export interface MatrixTask {
  id: string
  name: string
  project_id: string
  project_name: string
  status: 'running' | 'idle'
}

export type MatrixMode = 'tasks' | 'sessions'

export const useMatrixStore = defineStore('matrix', () => {
  // Grid settings
  const columns = ref(4)
  const rows = ref(4)
  const heightRatio = ref(1.0)
  const mode = ref<MatrixMode>('tasks')

  // Selection and pagination
  const selectedIndex = ref(0)
  const currentPage = ref(1)

  // Tasks data for 'tasks' mode
  const tasks = ref<MatrixTask[]>([])
  const tasksLoading = ref(false)

  // Sessions data for 'sessions' mode
  const sessions = ref<Array<{ index: number; session_name: string; exists: boolean }>>([])
  const sessionsLoading = ref(false)

  // Max rows based on columns (total cells <= 64)
  const maxRows = computed(() => Math.floor(64 / columns.value))

  // Grid capacity
  const gridCapacity = computed(() => columns.value * rows.value)

  // Total pages for tasks mode
  const totalPages = computed(() => {
    if (mode.value === 'sessions') return 1
    return Math.ceil(tasks.value.length / gridCapacity.value) || 1
  })

  // Current page tasks/sessions
  const currentItems = computed(() => {
    if (mode.value === 'sessions') {
      // Generate placeholder items for all grid positions
      return Array.from({ length: gridCapacity.value }, (_, i) => ({
        index: i + 1,
        session_name: `v2d-matrix-${i + 1}`,
        exists: sessions.value.find(s => s.index === i + 1)?.exists ?? false
      }))
    } else {
      const start = (currentPage.value - 1) * gridCapacity.value
      const end = start + gridCapacity.value
      return tasks.value.slice(start, end)
    }
  })

  // Load settings from localStorage
  const loadFromStorage = () => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (parsed.columns) columns.value = parsed.columns
        if (parsed.rows) rows.value = parsed.rows
        if (parsed.heightRatio) heightRatio.value = parsed.heightRatio
        if (parsed.mode) mode.value = parsed.mode
        if (parsed.currentPage) currentPage.value = parsed.currentPage
      }
    } catch {
      // Ignore parse errors
    }

    // Ensure rows doesn't exceed maxRows
    if (rows.value > maxRows.value) {
      rows.value = maxRows.value
    }
  }

  // Save settings to localStorage
  const saveToStorage = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        columns: columns.value,
        rows: rows.value,
        heightRatio: heightRatio.value,
        mode: mode.value,
        currentPage: currentPage.value
      }))
    } catch {
      // Ignore storage errors
    }
  }

  // Set columns and adjust rows if needed
  const setColumns = (val: number) => {
    columns.value = val
    if (rows.value > maxRows.value) {
      rows.value = maxRows.value
    }
    currentPage.value = 1
    saveToStorage()
  }

  // Set rows
  const setRows = (val: number) => {
    rows.value = Math.min(val, maxRows.value)
    currentPage.value = 1
    saveToStorage()
  }

  // Set height ratio
  const setHeightRatio = (val: number) => {
    heightRatio.value = val
    saveToStorage()
  }

  // Set mode
  const setMode = (val: MatrixMode) => {
    mode.value = val
    currentPage.value = 1
    selectedIndex.value = 0
    saveToStorage()
  }

  // Set selected index
  const setSelectedIndex = (val: number) => {
    selectedIndex.value = val
  }

  // Set current page
  const setCurrentPage = (val: number) => {
    currentPage.value = Math.max(1, Math.min(val, totalPages.value))
    selectedIndex.value = 0
    saveToStorage()
  }

  // Go to next page
  const nextPage = () => {
    if (currentPage.value < totalPages.value) {
      setCurrentPage(currentPage.value + 1)
    }
  }

  // Go to previous page
  const prevPage = () => {
    if (currentPage.value > 1) {
      setCurrentPage(currentPage.value - 1)
    }
  }

  // Set tasks
  const setTasks = (val: MatrixTask[]) => {
    tasks.value = val
  }

  // Set sessions
  const setSessions = (val: Array<{ index: number; session_name: string; exists: boolean }>) => {
    sessions.value = val
  }

  return {
    columns,
    rows,
    heightRatio,
    mode,
    selectedIndex,
    currentPage,
    tasks,
    tasksLoading,
    sessions,
    sessionsLoading,
    maxRows,
    gridCapacity,
    totalPages,
    currentItems,
    loadFromStorage,
    saveToStorage,
    setColumns,
    setRows,
    setHeightRatio,
    setMode,
    setSelectedIndex,
    setCurrentPage,
    nextPage,
    prevPage,
    setTasks,
    setSessions
  }
})
```

- [ ] **Step 2: Commit**

```bash
cd vibe2crazy
git add frontend/src/store/matrixStore.ts
git commit -m "feat: add matrix store for terminal matrix state management

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Frontend Matrix API Client

**Files:**
- Create: `frontend/src/api/matrix.ts`

- [ ] **Step 1: Write the API client**

Create `frontend/src/api/matrix.ts`:

```typescript
import { get, post } from './client'
import type { MatrixTask } from '@/store/matrixStore'

interface TasksAllResponse {
  tasks: MatrixTask[]
}

interface MatrixSessionInfo {
  index: number
  session_name: string
  exists: boolean
}

interface MatrixSessionsResponse {
  sessions: MatrixSessionInfo[]
}

interface MatrixSessionsRequest {
  count: number
}

export const matrixApi = {
  async getAllTasks(): Promise<MatrixTask[]> {
    const response = await get<TasksAllResponse>('/api/tasks/all')
    return response.tasks
  },

  async createSessions(count: number): Promise<MatrixSessionInfo[]> {
    const response = await post<MatrixSessionsResponse, MatrixSessionsRequest>(
      '/api/matrix/sessions',
      { count }
    )
    return response.sessions
  }
}

export default matrixApi
```

- [ ] **Step 2: Check API client exists, read it**

Run: `cat vibe2crazy/frontend/src/api/client.ts` or read the file to ensure `get` and `post` helpers exist.

If not, create `frontend/src/api/client.ts`:

```typescript
const BASE_URL = import.meta.env.DEV ? '' : ''

interface ApiResponse<T> {
  data?: T
  error?: string
}

async function request<T>(
  method: string,
  path: string,
  body?: any
): Promise<T> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(error || `HTTP ${response.status}`)
  }

  return response.json()
}

export async function get<T>(path: string): Promise<T> {
  return request<T>('GET', path)
}

export async function post<T, B>(path: string, body: B): Promise<T> {
  return request<T>('POST', path, body)
}

export async function patch<T, B>(path: string, body: B): Promise<T> {
  return request<T>('PATCH', path, body)
}

export async function deleteApi<T>(path: string): Promise<T> {
  return request<T>('DELETE', path)
}
```

- [ ] **Step 3: Commit**

```bash
cd vibe2crazy
git add frontend/src/api/matrix.ts frontend/src/api/client.ts
git commit -m "feat: add matrix API client for terminal matrix endpoints

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Frontend MatrixTerminal Component

**Files:**
- Create: `frontend/src/components/MatrixTerminal.vue`

- [ ] **Step 1: Write the MatrixTerminal component**

Create `frontend/src/components/MatrixTerminal.vue`:

```vue
<!-- frontend/src/components/MatrixTerminal.vue -->
<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { Terminal as XTerminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { useMainStore, type ThemeName } from '@/store'
import { useAuth } from '@/composables/useAuth'

interface Props {
  index: number
  title: string
  isSelected: boolean
  sessionName: string
  taskId?: string  // For 'tasks' mode
  mode: 'tasks' | 'sessions'
}

const props = defineProps<Props>()
const emit = defineEmits<{
  select: [index: number]
}>()

const mainStore = useMainStore()
const { token } = useAuth()

const terminalRef = ref<HTMLElement | null>(null)
const xterm = ref<XTerminal | null>(null)
const fitAddon = ref<FitAddon | null>(null)
let resizeObserver: ResizeObserver | null = null
let resizeTimeout: ReturnType<typeof setTimeout> | null = null

const ws = ref<WebSocket | null>(null)
const connected = ref(false)
const connecting = ref(false)

// Theme configurations
const DARK_THEME = {
  background: '#1e1e1e',
  foreground: '#d4d4d4',
  cursor: '#ffffff',
  selectionBackground: '#264f78',
  black: '#000000',
  red: '#cd3131',
  green: '#0dbc79',
  yellow: '#e5e510',
  blue: '#2472c8',
  magenta: '#bc3fbc',
  cyan: '#11a8cd',
  white: '#e5e5e5',
  brightBlack: '#666666',
  brightRed: '#f14c4c',
  brightGreen: '#23d18b',
  brightYellow: '#f5f543',
  brightBlue: '#3b8eea',
  brightMagenta: '#d670d6',
  brightCyan: '#29b8db',
  brightWhite: '#ffffff'
}

const LIGHT_THEME = {
  background: '#ffffff',
  foreground: '#333333',
  cursor: '#000000',
  selectionBackground: '#add6ff',
  black: '#000000',
  red: '#e14c4c',
  green: '#2da858',
  yellow: '#d4b418',
  blue: '#2c7bd6',
  magenta: '#c858c8',
  cyan: '#1fa8d4',
  white: '#333333',
  brightBlack: '#666666',
  brightRed: '#f14c4c',
  brightGreen: '#23d18b',
  brightYellow: '#e5c00e',
  brightBlue: '#3b8eea',
  brightMagenta: '#d670d6',
  brightCyan: '#29b8db',
  brightWhite: '#000000'
}

const GREEN_THEME = {
  background: '#c7edcc',
  foreground: '#2d5a3d',
  cursor: '#3b82f6',
  selectionBackground: 'rgba(59, 130, 246, 0.3)',
  black: '#2d5a3d',
  red: '#c75050',
  green: '#2d8b4e',
  yellow: '#8b6914',
  blue: '#2c7bd6',
  magenta: '#a858a8',
  cyan: '#1fa8d4',
  white: '#e8f5e9',
  brightBlack: '#4a7c5b',
  brightRed: '#e06060',
  brightGreen: '#3da85e',
  brightYellow: '#a08920',
  brightBlue: '#4a8eea',
  brightMagenta: '#b870b8',
  brightCyan: '#3ab8e4',
  brightWhite: '#ffffff'
}

const PARCHMENT_THEME = {
  background: '#f4ecd8',
  foreground: '#5c4d3a',
  cursor: '#b8860b',
  selectionBackground: 'rgba(184, 134, 11, 0.3)',
  black: '#5c4d3a',
  red: '#a04040',
  green: '#3d7a4a',
  yellow: '#7a6914',
  blue: '#2c5aa6',
  magenta: '#8a488a',
  cyan: '#1a8894',
  white: '#f4ecd8',
  brightBlack: '#7a6b55',
  brightRed: '#c05050',
  brightGreen: '#4d9a5a',
  brightYellow: '#9a8920',
  brightBlue: '#4a6ab6',
  brightMagenta: '#a858a8',
  brightCyan: '#2aa8b4',
  brightWhite: '#ffffff'
}

const getXtermTheme = (theme: ThemeName) => {
  const themes: Record<ThemeName, any> = {
    light: LIGHT_THEME,
    dark: DARK_THEME,
    green: GREEN_THEME,
    parchment: PARCHMENT_THEME
  }
  return themes[theme]
}

const getWsUrl = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname
  const port = window.location.port

  if (import.meta.env.DEV) {
    return `${protocol}//${host}:${port}`
  }

  if (port === '8864') {
    return `ws://${host}:8863`
  }

  return `${protocol}//${host}${port ? ':' + port : ''}`
}

const connect = () => {
  if (ws.value) {
    ws.value.close()
    ws.value = null
  }

  if (!token.value) return

  connecting.value = true

  let wsUrl: string
  if (props.mode === 'tasks' && props.taskId) {
    wsUrl = `${getWsUrl()}/ws/terminal?token=${token.value}&task_id=${props.taskId}`
  } else {
    wsUrl = `${getWsUrl()}/ws/matrix-terminal?token=${token.value}&index=${props.index}`
  }

  try {
    ws.value = new WebSocket(wsUrl)

    ws.value.onopen = () => {
      connected.value = true
      connecting.value = false
      if (xterm.value) {
        xterm.value.clear()
        resize(xterm.value.cols, xterm.value.rows)
      }
    }

    ws.value.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'output') {
          xterm.value?.write(msg.data)
        } else if (msg.type === 'error') {
          xterm.value?.writeln(`\x1b[31mError: ${msg.message}\x1b[0m`)
        }
      } catch {
        xterm.value?.write(event.data)
      }
    }

    ws.value.onerror = () => {
      connecting.value = false
      xterm.value?.writeln('\x1b[31mConnection error\x1b[0m')
    }

    ws.value.onclose = () => {
      connected.value = false
      connecting.value = false
      ws.value = null
    }
  } catch (err: any) {
    connecting.value = false
    xterm.value?.writeln(`\x1b[31mFailed to connect: ${err.message}\x1b[0m`)
  }
}

const disconnect = () => {
  if (ws.value) {
    ws.value.close()
    ws.value = null
  }
  connected.value = false
  connecting.value = false
}

const send = (data: string) => {
  if (ws.value && ws.value.readyState === WebSocket.OPEN && props.isSelected) {
    ws.value.send(JSON.stringify({ type: 'input', data }))
  }
}

const sendRaw = (message: object) => {
  if (ws.value && ws.value.readyState === WebSocket.OPEN && props.isSelected) {
    ws.value.send(JSON.stringify(message))
  }
}

const resize = (cols: number, rows: number) => {
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify({ type: 'resize', cols, rows }))
  }
}

const enterScrollMode = () => {
  if (!connected.value || !props.isSelected) return
  sendRaw({ type: 'scroll_mode', action: 'enter' })
}

const sendScrollCommand = (direction: 'up' | 'down', page: boolean = false) => {
  if (!connected.value || !props.isSelected) return
  sendRaw({ type: 'scroll', direction, page })
}

const handleWheel = (event: WheelEvent) => {
  if (!xterm.value || !props.isSelected) return

  const buffer = xterm.value.buffer.active

  if (event.deltaY < 0 && buffer.viewportY === 0) {
    enterScrollMode()
    event.preventDefault()
    event.stopPropagation()
    event.stopImmediatePropagation()

    const direction = event.deltaY > 0 ? 'down' : 'up'
    sendScrollCommand(direction)
    return
  }

  event.preventDefault()
  event.stopPropagation()
  event.stopImmediatePropagation()

  const scrollAmount = Math.sign(event.deltaY)
  xterm.value.scrollLines(scrollAmount)
}

const initTerminal = () => {
  if (!terminalRef.value) return

  if (xterm.value) {
    xterm.value.dispose()
    xterm.value = null
  }

  xterm.value = new XTerminal({
    cursorBlink: true,
    fontSize: 12,
    fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    scrollback: 1000,
    allowTransparency: false,
    convertEol: true,
    theme: getXtermTheme(mainStore.theme)
  })

  fitAddon.value = new FitAddon()
  xterm.value.loadAddon(fitAddon.value)
  xterm.value.open(terminalRef.value)

  const viewportElement = terminalRef.value.querySelector('.xterm-viewport') as HTMLElement
  if (viewportElement) {
    viewportElement.addEventListener('wheel', handleWheel, { passive: false, capture: true })
  }

  xterm.value.onData((data: string) => {
    if (data === '\x1b[5~' || data === '\x1b[6~' ||
        data.startsWith('\x1b[5;') || data.startsWith('\x1b[6;')) {
      return
    }
    send(data)
  })

  xterm.value.onKey(({ key, domEvent }) => {
    const isPageUp = domEvent.code === 'PageUp' || key === '\x1b[5~'
    const isPageDown = domEvent.code === 'PageDown' || key === '\x1b[6~'

    if (isPageUp && props.isSelected) {
      enterScrollMode()
      sendScrollCommand('up', true)
      domEvent.preventDefault()
    } else if (isPageDown && props.isSelected) {
      sendScrollCommand('down', true)
      domEvent.preventDefault()
    }
  })

  fitAddon.value.fit()
  if (xterm.value) {
    resize(xterm.value.cols, xterm.value.rows)
  }

  xterm.value.onResize(({ cols, rows }) => {
    resize(cols, rows)
  })

  xterm.value.clear()
  xterm.value.writeln('\x1b[33mConnecting...\x1b[0m')

  connect()
}

const handleResize = () => {
  nextTick(() => {
    if (!terminalRef.value || terminalRef.value.offsetWidth === 0 || terminalRef.value.offsetHeight === 0) return
    fitAddon.value?.fit()
    if (xterm.value) {
      resize(xterm.value.cols, xterm.value.rows)
    }
  })
}

const handleClick = () => {
  emit('select', props.index)
}

// Watch session/task changes to reconnect
watch([() => props.sessionName, () => props.taskId], () => {
  disconnect()
  nextTick(() => {
    connect()
  })
})

// Watch theme changes
watch(() => mainStore.theme, (newTheme) => {
  if (xterm.value) {
    try {
      xterm.value.options.theme = getXtermTheme(newTheme)
    } catch (error) {
      console.warn('[MatrixTerminal] Failed to update theme:', error)
    }
  }
})

onMounted(() => {
  initTerminal()

  resizeObserver = new ResizeObserver(() => {
    if (terminalRef.value && terminalRef.value.offsetParent !== null) {
      if (resizeTimeout) clearTimeout(resizeTimeout)
      resizeTimeout = setTimeout(handleResize, 10)
    }
  })

  if (terminalRef.value) {
    resizeObserver.observe(terminalRef.value)
  }
})

onUnmounted(() => {
  if (resizeTimeout) clearTimeout(resizeTimeout)

  const viewportElement = terminalRef.value?.querySelector('.xterm-viewport') as HTMLElement
  if (viewportElement) {
    viewportElement.removeEventListener('wheel', handleWheel, { capture: true } as EventListenerOptions)
  }

  disconnect()
  resizeObserver?.disconnect()

  if (xterm.value) {
    try {
      xterm.value.dispose()
    } catch (error) {
      // Ignore errors
    }
    xterm.value = null
  }
})
</script>

<template>
  <div
    class="matrix-terminal flex flex-col border border-main overflow-hidden"
    :class="{ 'selected-terminal': isSelected }"
    @click="handleClick"
  >
    <!-- Header -->
    <div
      class="flex items-center gap-2 px-2 py-1 bg-sub border-b border-main cursor-pointer"
      @click="handleClick"
    >
      <span
        :class="[
          'inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-medium',
          isSelected ? 'bg-blue-500 text-white' : 'bg-sub text-sub'
        ]"
      >
        {{ index + 1 }}
      </span>
      <span
        class="text-sm text-main truncate flex-1"
        :title="title"
      >
        {{ title }}
      </span>
      <span
        :class="[
          'w-2 h-2 rounded-full',
          connected ? 'bg-green-500' : connecting ? 'bg-yellow-500 animate-pulse' : 'bg-gray-500'
        ]"
      ></span>
    </div>

    <!-- Terminal -->
    <div ref="terminalRef" class="flex-1 overflow-hidden"></div>
  </div>
</template>

<style scoped>
.matrix-terminal {
  min-width: 100px;
  min-height: 80px;
}

.selected-terminal {
  border-color: #3b82f6;
}

:deep(.xterm) {
  height: 100%;
  padding: 0 !important;
}

:deep(.xterm-viewport) {
  overflow-y: hidden !important;
}

:deep(.xterm-scrollbar-horizontal),
:deep(.xterm-scrollbar-vertical),
:deep(.xterm .scrollbar) {
  display: none !important;
}

:deep(.xterm-screen) {
  width: 100% !important;
}

.theme-dark :deep(.xterm-viewport) {
  background-color: #1e1e1e !important;
}
.theme-light :deep(.xterm-viewport) {
  background-color: #ffffff !important;
}
.theme-green :deep(.xterm-viewport) {
  background-color: #c7edcc !important;
}
.theme-parchment :deep(.xterm-viewport) {
  background-color: #f4ecd8 !important;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
cd vibe2crazy
git add frontend/src/components/MatrixTerminal.vue
git commit -m "feat: add MatrixTerminal component for single terminal instance

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Frontend MatrixView Page

**Files:**
- Create: `frontend/src/views/MatrixView.vue`

- [ ] **Step 1: Write the MatrixView page**

Create `frontend/src/views/MatrixView.vue`:

```vue
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useMatrixStore, type MatrixTask } from '@/store/matrixStore'
import { useMainStore } from '@/store'
import matrixApi from '@/api/matrix'
import MatrixTerminal from '@/components/MatrixTerminal.vue'

const matrixStore = useMatrixStore()
const mainStore = useMainStore()

const gridRef = ref<HTMLElement | null>(null)
const terminalRefs = ref<Map<number, HTMLElement>>(new Map())

// Column options
const columnOptions = [2, 4, 6, 8, 10]

// Height ratio options
const heightRatioOptions = [
  { value: 0.8, label: '0.8x' },
  { value: 1.0, label: '1.0x' },
  { value: 1.2, label: '1.2x' },
  { value: 1.4, label: '1.4x' },
  { value: 1.6, label: '1.6x' },
  { value: 1.8, label: '1.8x' },
  { value: 2.0, label: '2.0x' },
  { value: 2.5, label: '2.5x' }
]

// Mode options
const modeOptions = [
  { value: 'tasks', label: 'All Tasks' },
  { value: 'sessions', label: 'New Sessions' }
]

// Row options based on maxRows
const rowOptions = computed(() => {
  return Array.from({ length: matrixStore.maxRows }, (_, i) => i + 1)
})

// Terminal title computation
const getTerminalTitle = (item: any, index: number): string => {
  if (matrixStore.mode === 'tasks') {
    const task = item as MatrixTask
    return `${task.project_name}/${task.name}`
  } else {
    return `Terminal ${index + 1}`
  }
}

// Get task ID for terminal (tasks mode only)
const getTaskId = (item: any): string | undefined => {
  if (matrixStore.mode === 'tasks') {
    const task = item as MatrixTask
    return task.id
  }
  return undefined
}

// Get session name for terminal
const getSessionName = (item: any, index: number): string => {
  if (matrixStore.mode === 'tasks') {
    return `v2d-${(item as MatrixTask).id}`
  } else {
    return `v2d-matrix-${index + 1}`
  }
}

// Grid style
const gridStyle = computed(() => {
  return {
    gridTemplateColumns: `repeat(${matrixStore.columns}, 1fr)`
  }
})

// Terminal height based on width and ratio
const terminalHeightStyle = computed(() => {
  // This will be calculated dynamically based on actual width
  // We use a CSS trick: aspect-ratio combined with height calculation
  return {}
})

// Load data based on mode
const loadData = async () => {
  if (matrixStore.mode === 'tasks') {
    matrixStore.tasksLoading = true
    try {
      const tasks = await matrixApi.getAllTasks()
      matrixStore.setTasks(tasks)
    } catch (err) {
      console.error('Failed to load tasks:', err)
    }
    matrixStore.tasksLoading = false
  } else {
    matrixStore.sessionsLoading = true
    try {
      const sessions = await matrixApi.createSessions(matrixStore.gridCapacity)
      matrixStore.setSessions(sessions)
    } catch (err) {
      console.error('Failed to create sessions:', err)
    }
    matrixStore.sessionsLoading = false
  }
}

// Handle terminal selection
const handleSelect = (index: number) => {
  matrixStore.setSelectedIndex(index)
}

// Handle mode change
const handleModeChange = async () => {
  await loadData()
}

// Handle settings change that requires reconnect
const handleSettingsChange = async () => {
  // Disconnect is handled by watch in MatrixTerminal
  // Just need to reload data for sessions mode
  if (matrixStore.mode === 'sessions') {
    await loadData()
  }
}

// Initialize
onMounted(async () => {
  matrixStore.loadFromStorage()
  await loadData()
})

// Watch mode changes
watch(() => matrixStore.mode, async () => {
  await handleModeChange()
})

// Watch grid size changes for sessions mode
watch([() => matrixStore.columns, () => matrixStore.rows], async () => {
  await handleSettingsChange()
})
</script>

<template>
  <div class="min-h-screen bg-main">
    <!-- Header -->
    <header class="fixed top-0 left-0 right-0 z-30 bg-main border-b border-main">
      <div class="px-4 py-2 flex items-center gap-4 flex-wrap">
        <!-- Columns -->
        <div class="flex items-center gap-2">
          <label class="text-sm text-sub">Columns:</label>
          <select
            v-model.number="matrixStore.columns"
            @change="matrixStore.setColumns(matrixStore.columns)"
            class="input text-sm py-1 px-2 w-16"
          >
            <option v-for="col in columnOptions" :key="col" :value="col">{{ col }}</option>
          </select>
        </div>

        <!-- Rows -->
        <div class="flex items-center gap-2">
          <label class="text-sm text-sub">Rows:</label>
          <select
            v-model.number="matrixStore.rows"
            @change="matrixStore.setRows(matrixStore.rows)"
            class="input text-sm py-1 px-2 w-16"
          >
            <option v-for="row in rowOptions" :key="row" :value="row">{{ row }}</option>
          </select>
        </div>

        <!-- Height Ratio -->
        <div class="flex items-center gap-2">
          <label class="text-sm text-sub">Height:</label>
          <select
            v-model.number="matrixStore.heightRatio"
            @change="matrixStore.setHeightRatio(matrixStore.heightRatio)"
            class="input text-sm py-1 px-2 w-20"
          >
            <option
              v-for="opt in heightRatioOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </div>

        <!-- Mode -->
        <div class="flex items-center gap-2">
          <label class="text-sm text-sub">Mode:</label>
          <select
            v-model="matrixStore.mode"
            @change="matrixStore.setMode(matrixStore.mode)"
            class="input text-sm py-1 px-2 w-28"
          >
            <option
              v-for="opt in modeOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </div>

        <!-- Pagination (only for tasks mode) -->
        <div v-if="matrixStore.mode === 'tasks'" class="flex items-center gap-2 ml-auto">
          <button
            @click="matrixStore.prevPage()"
            :disabled="matrixStore.currentPage === 1"
            class="btn btn-secondary text-sm py-1 px-2 disabled:opacity-50"
          >
            Prev
          </button>
          <span class="text-sm text-sub">
            第 {{ matrixStore.currentPage }}/{{ matrixStore.totalPages }} 页
          </span>
          <button
            @click="matrixStore.nextPage()"
            :disabled="matrixStore.currentPage === matrixStore.totalPages"
            class="btn btn-secondary text-sm py-1 px-2 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </header>

    <!-- Main grid -->
    <main class="pt-12 px-4 pb-4">
      <div
        v-if="matrixStore.tasksLoading || matrixStore.sessionsLoading"
        class="flex items-center justify-center py-20"
      >
        <div class="spinner"></div>
      </div>

      <div
        v-else
        ref="gridRef"
        class="grid gap-2"
        :style="gridStyle"
      >
        <MatrixTerminal
          v-for="(item, idx) in matrixStore.currentItems"
          :key="`${matrixStore.mode}-${matrixStore.currentPage}-${idx}`"
          :index="idx"
          :title="getTerminalTitle(item, idx)"
          :is-selected="matrixStore.selectedIndex === idx"
          :session-name="getSessionName(item, idx)"
          :task-id="getTaskId(item)"
          :mode="matrixStore.mode"
          @select="handleSelect"
          :style="{ height: `calc((100vw - 2rem) / ${matrixStore.columns} * ${matrixStore.heightRatio})` }"
          class="matrix-terminal-item"
        />
      </div>

      <!-- Empty state for tasks mode -->
      <div
        v-if="matrixStore.mode === 'tasks' && !matrixStore.tasksLoading && matrixStore.tasks.length === 0"
        class="text-center py-20"
      >
        <p class="text-sub">No tasks found</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.matrix-terminal-item {
  min-height: 100px;
  max-height: 600px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
cd vibe2crazy
git add frontend/src/views/MatrixView.vue
git commit -m "feat: add MatrixView page with header controls and grid layout

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 8: Add Matrix Route to Router

**Files:**
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: Add matrix route**

Modify `frontend/src/router/index.ts`, add after the `task` route (around line 34):

```typescript
{
  path: '/matrix',
  name: 'matrix',
  component: () => import('@/views/MatrixView.vue'),
  meta: { requiresAuth: true }
},
```

- [ ] **Step 2: Commit**

```bash
cd vibe2crazy
git add frontend/src/router/index.ts
git commit -m "feat: add /matrix route for terminal matrix view

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 9: Add Matrix Button to ProjectsView Header

**Files:**
- Modify: `frontend/src/views/ProjectsView.vue`

- [ ] **Step 1: Add MatrixIcon component import and button**

Modify `frontend/src/views/ProjectsView.vue`:

Add import around line 11:
```typescript
import MatrixIcon from '@/components/MatrixIcon.vue'
```

Add button after GlobalTerminalIcon (around line 232):
```vue
<MatrixIcon />
```

- [ ] **Step 2: Create MatrixIcon component**

Create `frontend/src/components/MatrixIcon.vue`:

```vue
<script setup lang="ts">
const openMatrix = () => {
  window.open('/matrix', '_blank')
}
</script>

<template>
  <button
    @click="openMatrix"
    class="p-1.5 rounded-lg hover:bg-sub hidden md:block"
    title="Terminal Matrix"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      class="h-5 w-5 text-sub"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <!-- 4x4 grid pattern -->
      <rect x="3" y="3" width="4" height="4" rx="1" stroke-width="2" />
      <rect x="10" y="3" width="4" height="4" rx="1" stroke-width="2" />
      <rect x="17" y="3" width="4" height="4" rx="1" stroke-width="2" />
      <rect x="3" y="10" width="4" height="4" rx="1" stroke-width="2" />
      <rect x="10" y="10" width="4" height="4" rx="1" stroke-width="2" />
      <rect x="17" y="10" width="4" height="4" rx="1" stroke-width="2" />
      <rect x="3" y="17" width="4" height="4" rx="1" stroke-width="2" />
      <rect x="10" y="17" width="4" height="4" rx="1" stroke-width="2" />
      <rect x="17" y="17" width="4" height="4" rx="1" stroke-width="2" />
    </svg>
  </button>
</template>
```

- [ ] **Step 3: Commit**

```bash
cd vibe2crazy
git add frontend/src/views/ProjectsView.vue frontend/src/components/MatrixIcon.vue
git commit -m "feat: add matrix button to ProjectsView header (desktop only)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 10: Integration Testing

**Files:**
- No new files (manual testing)

- [ ] **Step 1: Start the development environment**

Run: `cd vibe2crazy && ./deploy.sh start`
Expected: Backend and frontend services started

- [ ] **Step 2: Verify backend endpoints**

Run: `curl -X POST http://localhost:8863/auth/login -H "Content-Type: application/json" -d '{"password":"password"}'`
Expected: Returns token

Use the token to test:
```bash
TOKEN=$(curl -s -X POST http://localhost:8863/auth/login -H "Content-Type: application/json" -d '{"password":"password"}' | jq -r '.token')
curl -H "Authorization: Bearer $TOKEN" http://localhost:8863/api/tasks/all
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"count":4}' http://localhost:8863/api/matrix/sessions
```

- [ ] **Step 3: Open matrix view in browser**

Navigate to `http://localhost:5173/matrix` (or appropriate frontend URL)
Expected: Matrix view loads with header controls and empty grid

- [ ] **Step 4: Test grid layout controls**

1. Change columns dropdown - verify grid updates
2. Change rows dropdown - verify max rows adjusts based on columns
3. Change height ratio - verify terminal heights change
4. Switch mode - verify title format changes

- [ ] **Step 5: Test with existing tasks**

If there are existing tasks in the database:
1. Navigate to matrix view
2. Verify tasks appear in grid with correct titles
3. Click on a terminal to select it
4. Type in selected terminal - verify input is sent
5. Press PageUp - verify scroll mode

- [ ] **Step 6: Test localStorage persistence**

1. Change settings (columns, rows, ratio, mode)
2. Refresh the page
3. Verify settings are restored

- [ ] **Step 7: Test mode switching**

1. Start in "All Tasks" mode
2. Switch to "New Sessions" mode
3. Type something in a terminal
4. Switch back to "All Tasks" mode
5. Switch back to "New Sessions" mode
6. Verify previous terminal content is preserved

- [ ] **Step 8: Stop development environment**

Run: `cd vibe2crazy && ./deploy.sh stop`

---

### Task 11: Final Commit and Summary

- [ ] **Step 1: Run all tests**

Run: `cd vibe2crazy/backend && pytest --cov=app -v`
Expected: All tests pass

- [ ] **Step 2: Run frontend lint**

Run: `cd vibe2crazy/frontend && npm run lint`
Expected: No lint errors

- [ ] **Step 3: Create summary commit if there are uncommitted changes**

```bash
cd vibe2crazy
git status
# If there are uncommitted changes:
git add -A
git commit -m "feat: complete terminal matrix implementation

- Add GET /api/tasks/all endpoint for all tasks across projects
- Add POST /api/matrix/sessions endpoint for matrix terminal sessions
- Add WebSocket endpoint /ws/matrix-terminal for matrix terminals
- Add MatrixView page with configurable grid layout
- Add MatrixTerminal component with xterm.js integration
- Add matrix store for state management and localStorage persistence
- Add matrix button to ProjectsView header (desktop only)
- Support keyboard input routing to selected terminal
- Support scroll mode via PageUp/PageDown
- Preserve tmux sessions across mode switches

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pathlib import Path
from app.config import settings
from app.database import init_db, SessionLocal
import asyncio
from app.services.task_monitor_service import TaskMonitorService
from app.routers import auth, projects, tasks, files, git, terminals, queues, command_presets, filesystem, symbols, global_terminal, tunnel, config, matrix
from app.websocket.terminal import get_websocket_terminal
from app.websocket.manager import manager
from app.auth import verify_token
from app.models import Session as SessionModel, TunnelConfig
import json

# Setup logging
from app.logging_config import setup_logging, logger
setup_logging()


# Rate limiter setup using fastapi-limiter with pyrate-limiter
from pyrate_limiter import Limiter, Rate, Duration
from pyrate_limiter.clocks import MonotonicClock
from fastapi_limiter.depends import RateLimiter
from fastapi_limiter.identifier import default_identifier
from fastapi_limiter.callback import default_callback

# Create limiter with in-memory storage (default)
auth_limiter = Limiter(Rate(5, Duration.MINUTE))  # 5 requests per minute
default_limiter = Limiter(Rate(100, Duration.MINUTE))  # 100 requests per minute

# Create RateLimiter instances for dependency injection
auth_rate_limiter = RateLimiter(limiter=auth_limiter, identifier=default_identifier, callback=default_callback)
default_rate_limiter = RateLimiter(limiter=default_limiter, identifier=default_identifier, callback=default_callback)


def get_frontend_path() -> Path | None:
    """Get frontend static files path based on runtime context.

    Returns:
        Path to frontend dist directory, or None if not found.
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        base_path = Path(sys._MEIPASS)
        frontend_path = base_path / "frontend" / "dist"
        if frontend_path.exists():
            return frontend_path
    else:
        # Development mode - check relative to backend directory
        frontend_path = Path(__file__).parent.parent.parent / "frontend" / "dist"
        if frontend_path.exists():
            return frontend_path
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully")

    logger.info("Starting task monitoring service...")
    asyncio.create_task(monitor_tasks())
    logger.info("Task monitoring service started in background")

    asyncio.create_task(start_tunnel_service())

    logger.info("Vibe2Crazy is ready!")

    yield

    # Shutdown
    logger.info("Vibe2Crazy shutdown complete")


# Custom JSONResponse that uses ensure_ascii=False for Chinese character support
class CustomJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        # Use ensure_ascii=False to properly display Chinese characters
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(',', ':')
        ).encode('utf-8')


# Create FastAPI app with custom response class and lifespan
app = FastAPI(
    title="Vibe2Crazy",
    description="Remote code editing tool with Git worktree isolation",
    version="0.1.0",
    default_response_class=CustomJSONResponse,
    lifespan=lifespan
)

logger.info("Vibe2Crazy starting up...")
logger.info(f"Debug mode: {settings.debug}")
logger.info(f"Projects directory: {settings.projects_dir}")
logger.info(f"Database: {settings.database_url}")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(matrix.router)  # Matrix router before task_router for /api/tasks/all
app.include_router(tasks.task_router)
app.include_router(projects.router)
app.include_router(files.router)
app.include_router(git.router)
app.include_router(git.branch_router)
app.include_router(terminals.router)
app.include_router(queues.router, prefix="/api")
app.include_router(command_presets.router, prefix="/api/command-presets")
app.include_router(filesystem.router)
app.include_router(symbols.router)
app.include_router(global_terminal.router)
app.include_router(tunnel.router)
app.include_router(config.router)

# Serve frontend static files if bundled/available
# Mount assets directory for JS, CSS, images, etc.
frontend_path = get_frontend_path()
if frontend_path:
    logger.info(f"Serving frontend from: {frontend_path}")
    assets_path = frontend_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")
    # Serve favicon and other root-level static files
    app.mount("/static-root", StaticFiles(directory=str(frontend_path)), name="static-root")
else:
    logger.warning("Frontend static files not found - API-only mode")

# Global monitor service reference
monitor_service: TaskMonitorService = None


async def monitor_tasks():
    """Background task to monitor all task statuses"""
    global monitor_service
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        monitor_service = TaskMonitorService()
        logger.info("Task monitor service initialized")
        while True:
            try:
                monitor_service.check_all_tasks()
                logger.debug("Task status check completed")
                await asyncio.sleep(10)  # Poll every 10 seconds
            except Exception as e:
                logger.error(f"Error in task monitoring loop: {e}")
                await asyncio.sleep(10)  # Wait before retry
    finally:
        db.close()
        logger.info("Task monitor service stopped")


async def start_tunnel_service():
    """Start tunnel service if token is configured."""
    from app.services.tunnel_service import TunnelService
    from app.routers.tunnel import set_tunnel_service

    db = SessionLocal()
    try:
        config = db.query(TunnelConfig).filter(TunnelConfig.id == 1).first()
        if not config:
            config = TunnelConfig(id=1, status="disabled")
            db.add(config)
            db.commit()
            db.refresh(config)

        service = TunnelService(db, settings.port, config)
        set_tunnel_service(service)

        if config.token:
            logger.info("Starting tunnel service with configured token")
            await service.start()
        else:
            logger.info("No tunnel token configured, service not started")

    except Exception as e:
        logger.error(f"Failed to start tunnel service: {e}")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.websocket("/ws/terminal")
async def websocket_terminal(
    websocket: WebSocket,
    token: str = Query(...),
    task_id: str = Query(...)
):
    """WebSocket endpoint for terminal access"""
    logger.info(f"WebSocket connection request - task_id: {task_id}")
    await websocket.accept()

    # Verify token first (no database needed)
    if not verify_token(token):
        logger.warning(f"Terminal connection rejected - invalid token")
        await websocket.close(code=1008, reason="Unauthorized")
        return

    # Get task info with a short-lived database session
    from app.database import SessionLocal
    from app.models import Task

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.warning(f"Terminal connection rejected - task not found: {task_id}")
            await websocket.close(code=1008, reason="Task not found")
            return

        # Extract task info we need (detach from session)
        task_info = {
            'id': task.id,
            'tmux_session': task.tmux_session,
            'worktree_path': task.worktree_path
        }
    finally:
        db.close()  # Close database session immediately after use

    # Create terminal handler with detached task info
    from app.websocket.terminal import WebSocketTerminal
    from app.websocket.manager import manager

    # Create a simple object to hold task info
    class TaskInfo:
        def __init__(self, info):
            self.id = info['id']
            self.tmux_session = info['tmux_session']
            self.worktree_path = info['worktree_path']

    terminal = WebSocketTerminal(websocket, TaskInfo(task_info))

    try:
        # Register connection with manager
        await manager.connect(task_id, websocket)

        logger.info(f"Terminal started for task: {task_id}")
        await terminal.start()

        # Handle incoming messages
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
                                logger.info(f"Received scroll_mode: action={action}")
                                await terminal.handle_scroll_mode(action)
                        elif msg.get("type") == "scroll":
                            direction = msg.get("direction")
                            page = msg.get("page", False)
                            if direction in ("up", "down"):
                                logger.info(f"Received scroll: direction={direction}, page={page}")
                                await terminal.handle_scroll(direction, page)

                    except json.JSONDecodeError:
                        pass
                elif "bytes" in data:
                    # Raw bytes input
                    await terminal.handle_input(data["bytes"].decode("utf-8"))

            except (WebSocketDisconnect, RuntimeError) as e:
                # WebSocketDisconnect or "Cannot call receive once disconnected"
                logger.info(f"WebSocket disconnected - task_id: {task_id}, reason: {str(e)}")
                break
            except Exception as e:
                # Log other errors but break the loop to prevent infinite error loops
                logger.error(f"WebSocket error - task_id: {task_id}, error: {str(e)}")
                break

    except Exception as e:
        logger.error(f"WebSocket setup failed - task_id: {task_id}, error: {str(e)}")
    finally:
        # Ensure terminal is closed and resources are cleaned up
        if 'terminal' in locals():
            await terminal.close()
        # Unregister from connection manager
        manager.disconnect(task_id, websocket)
        logger.info(f"WebSocket connection closed - task_id: {task_id}")


@app.websocket("/ws/global-terminal")
async def websocket_global_terminal(
    websocket: WebSocket,
    token: str = Query(...)
):
    """WebSocket endpoint for global terminal access"""
    logger.info("Global terminal WebSocket connection request")
    await websocket.accept()

    # Verify token
    if not verify_token(token):
        logger.warning("Global terminal connection rejected - invalid token")
        await websocket.close(code=1008, reason="Unauthorized")
        return

    from app.websocket.global_terminal import GlobalWebSocketTerminal
    terminal = GlobalWebSocketTerminal(websocket)

    try:
        logger.info("Global terminal started")
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
                logger.info(f"Global terminal WebSocket disconnected: {str(e)}")
                break
            except RuntimeError as e:
                if "Cannot call receive once disconnected" in str(e):
                    logger.info("Global terminal WebSocket already disconnected")
                else:
                    logger.error(f"Global terminal WebSocket error: {str(e)}")
                break
            except Exception as e:
                logger.error(f"Global terminal WebSocket error: {str(e)}")
                break

    except Exception as e:
        logger.error(f"Global terminal WebSocket setup failed: {str(e)}")
    finally:
        await terminal.close()
        logger.info("Global terminal WebSocket connection closed")


@app.websocket("/ws/matrix-terminal")
async def websocket_matrix_terminal(
    websocket: WebSocket,
    token: str = Query(...),
    index: int = Query(...),
    session: str = Query(None)
):
    """WebSocket endpoint for matrix terminal access"""
    logger.info(f"Matrix terminal WebSocket connection request - index: {index}, session: {session}")
    await websocket.accept()

    # Verify token
    if not verify_token(token):
        logger.warning(f"Matrix terminal connection rejected - invalid token")
        await websocket.close(code=1008, reason="Unauthorized")
        return

    # Use provided session name (for tasks mode) or default to index-based name (for sessions mode)
    session_name = session if session else f"v2d-matrix-{index}"

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


# Serve favicon directly from root
@app.get("/favicon.svg")
async def serve_favicon():
    """Serve favicon from frontend dist directory."""
    frontend_path = get_frontend_path()
    if frontend_path:
        favicon_path = frontend_path / "favicon.svg"
        if favicon_path.exists():
            return FileResponse(str(favicon_path), media_type="image/svg+xml")
    return {"detail": "Favicon not found"}

# Catch-all route for SPA - must be last
# Serves index.html for any unmatched GET routes (for client-side routing)
@app.get("/{full_path:path}")
async def serve_spa(request: Request, full_path: str):
    """Serve the SPA index.html for client-side routing."""
    frontend_path = get_frontend_path()
    if frontend_path:
        index_file = frontend_path / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
    return {"detail": "Frontend not available"}

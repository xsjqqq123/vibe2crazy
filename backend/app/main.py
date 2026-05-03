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
from app.routers import auth, projects, tasks, files, git, terminals, queues, command_presets, filesystem, symbols, global_terminal, tunnel, config, matrix, search
from app.websocket.terminal import get_websocket_terminal
from app.websocket.manager import manager
from app.auth import verify_token
from app.models import Session as SessionModel, TunnelConfig
import json
import time

# Setup logging
from app.logging_config import setup_logging, logger
setup_logging()


# Rate limiter setup using fastapi-limiter with pyrate-limiter
from app.rate_limiters import auth_rate_limiter, default_rate_limiter

# Re-export for other modules
__all__ = ['auth_rate_limiter', 'default_rate_limiter']


async def _ws_heartbeat(websocket: WebSocket, last_activity: list, interval: float = 15.0):
    """Send ping only when connection is idle, to keep NAT/firewall alive."""
    while True:
        await asyncio.sleep(interval)
        if time.monotonic() - last_activity[0] >= interval:
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                break


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
app.include_router(search.router)

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
    """Background task to monitor all task statuses.

    check_all_tasks() runs in a thread pool so its synchronous
    subprocess calls (tmux capture, git commands) never block the
    asyncio event loop.
    """
    global monitor_service
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        monitor_service = TaskMonitorService()
        # Store the main event loop so the thread-pool worker can
        # schedule async callbacks (WebSocket broadcasts, delayed
        # newline sends) back onto it.
        monitor_service.set_main_loop(asyncio.get_running_loop())
        logger.info("Task monitor service initialized")
        while True:
            try:
                await asyncio.to_thread(monitor_service.check_all_tasks)
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
            config = TunnelConfig(id=1, status="disabled", use_tls=True)
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
    task_id: str = Query(...),
    cols: int = Query(80),
    rows: int = Query(24)
):
    """WebSocket endpoint for terminal access"""
    logger.info(f"WebSocket connection request - task_id: {task_id}, size: {cols}x{rows}")
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

    terminal = WebSocketTerminal(websocket, TaskInfo(task_info), initial_cols=cols, initial_rows=rows)
    last_activity = [time.monotonic()]  # Track last client activity for idle heartbeat

    try:
        # Register connection with manager
        await manager.connect(task_id, websocket)

        logger.info(f"Terminal started for task: {task_id}")
        await terminal.start()

        # Start heartbeat task (sends ping only when idle > 15s)
        heartbeat_task = asyncio.create_task(_ws_heartbeat(websocket, last_activity))

        # Handle incoming messages
        while True:
            try:
                data = await websocket.receive()

                if "text" in data:
                    message = data["text"]
                    try:
                        msg = json.loads(message)

                        if msg.get("type") == "input":
                            last_activity[0] = time.monotonic()
                            await terminal.handle_input(msg.get("data", ""))
                        elif msg.get("type") == "resize":
                            last_activity[0] = time.monotonic()
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
                            last_activity[0] = time.monotonic()
                            direction = msg.get("direction")
                            page = msg.get("page", False)
                            if direction in ("up", "down"):
                                logger.info(f"Received scroll: direction={direction}, page={page}")
                                await terminal.handle_scroll(direction, page)
                        elif msg.get("type") == "pong":
                            pass  # Heartbeat response - ignore

                    except json.JSONDecodeError:
                        pass
                elif "bytes" in data:
                    # Raw bytes input
                    last_activity[0] = time.monotonic()
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
        # Cancel heartbeat
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        # Ensure terminal is closed and resources are cleaned up
        if 'terminal' in locals():
            await terminal.close()
        # Unregister from connection manager
        manager.disconnect(task_id, websocket)
        logger.info(f"WebSocket connection closed - task_id: {task_id}")


@app.websocket("/ws/global-terminal")
async def websocket_global_terminal(
    websocket: WebSocket,
    token: str = Query(...),
    cols: int = Query(80),
    rows: int = Query(24)
):
    """WebSocket endpoint for global terminal access"""
    logger.info(f"Global terminal WebSocket connection request - size: {cols}x{rows}")
    await websocket.accept()

    # Verify token
    if not verify_token(token):
        logger.warning("Global terminal connection rejected - invalid token")
        await websocket.close(code=1008, reason="Unauthorized")
        return

    from app.websocket.global_terminal import GlobalWebSocketTerminal
    terminal = GlobalWebSocketTerminal(websocket, initial_cols=cols, initial_rows=rows)
    last_activity = [time.monotonic()]  # Track last client activity for idle heartbeat

    try:
        logger.info("Global terminal started")
        await terminal.start()

        # Start heartbeat task (sends ping only when idle > 15s)
        heartbeat_task = asyncio.create_task(_ws_heartbeat(websocket, last_activity))

        while True:
            try:
                data = await websocket.receive()

                if "text" in data:
                    message = data["text"]
                    try:
                        msg = json.loads(message)

                        if msg.get("type") == "input":
                            last_activity[0] = time.monotonic()
                            await terminal.handle_input(msg.get("data", ""))
                        elif msg.get("type") == "resize":
                            last_activity[0] = time.monotonic()
                            await terminal.handle_resize(
                                msg.get("cols", 80),
                                msg.get("rows", 24)
                            )
                        elif msg.get("type") == "scroll_mode":
                            action = msg.get("action")
                            if action in ("enter", "exit"):
                                await terminal.handle_scroll_mode(action)
                        elif msg.get("type") == "scroll":
                            last_activity[0] = time.monotonic()
                            direction = msg.get("direction")
                            page = msg.get("page", False)
                            if direction in ("up", "down"):
                                await terminal.handle_scroll(direction, page)
                        elif msg.get("type") == "pong":
                            pass  # Heartbeat response - ignore

                    except json.JSONDecodeError:
                        pass
                elif "bytes" in data:
                    last_activity[0] = time.monotonic()
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
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        await terminal.close()
        logger.info("Global terminal WebSocket connection closed")


@app.websocket("/ws/matrix-terminal")
async def websocket_matrix_terminal(
    websocket: WebSocket,
    token: str = Query(...),
    index: int = Query(...),
    session: str = Query(None),
    cols: int = Query(80),
    rows: int = Query(24)
):
    """WebSocket endpoint for matrix terminal access"""
    logger.info(f"Matrix terminal WebSocket connection request - index: {index}, session: {session}, size: {cols}x{rows}")
    await websocket.accept()

    # Verify token
    if not verify_token(token):
        logger.warning(f"Matrix terminal connection rejected - invalid token")
        await websocket.close(code=1008, reason="Unauthorized")
        return

    # Use provided session name (for tasks mode) or default to index-based name (for sessions mode)
    session_name = session if session else f"v2d-matrix-{index}"

    from app.websocket.matrix_terminal import MatrixWebSocketTerminal
    terminal = MatrixWebSocketTerminal(websocket, session_name, index, initial_cols=cols, initial_rows=rows)
    last_activity = [time.monotonic()]  # Track last client activity for idle heartbeat

    try:
        logger.info(f"Matrix terminal {index} started")
        await terminal.start()

        # Start heartbeat task (sends ping only when idle > 15s)
        heartbeat_task = asyncio.create_task(_ws_heartbeat(websocket, last_activity))

        while True:
            try:
                data = await websocket.receive()

                if "text" in data:
                    message = data["text"]
                    try:
                        msg = json.loads(message)

                        if msg.get("type") == "input":
                            last_activity[0] = time.monotonic()
                            await terminal.handle_input(msg.get("data", ""))
                        elif msg.get("type") == "resize":
                            last_activity[0] = time.monotonic()
                            await terminal.handle_resize(
                                msg.get("cols", 80),
                                msg.get("rows", 24)
                            )
                        elif msg.get("type") == "scroll_mode":
                            action = msg.get("action")
                            if action in ("enter", "exit"):
                                await terminal.handle_scroll_mode(action)
                        elif msg.get("type") == "scroll":
                            last_activity[0] = time.monotonic()
                            direction = msg.get("direction")
                            page = msg.get("page", False)
                            if direction in ("up", "down"):
                                await terminal.handle_scroll(direction, page)
                        elif msg.get("type") == "pong":
                            pass  # Heartbeat response - ignore

                    except json.JSONDecodeError:
                        pass
                elif "bytes" in data:
                    last_activity[0] = time.monotonic()
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
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
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


def run_dual_stack(host: str = "0.0.0.0", port: int = 8863):
    """Run the backend with dual-stack HTTP/HTTPS support.

    Starts an internal uvicorn on a high port, then runs a dual-stack
    TCP proxy on the external port that auto-detects TLS connections.
    """
    from app.tls_utils import ensure_self_signed_cert, DualStackProxy, create_ssl_context, INTERNAL_PORT
    import uvicorn

    # Generate self-signed cert if needed
    data_dir = Path(settings.database_url.replace("sqlite:///", "")).parent
    cert_path, key_path = ensure_self_signed_cert(data_dir)
    ssl_ctx = create_ssl_context(cert_path, key_path)

    # Start dual-stack proxy on external port -> internal port
    proxy = DualStackProxy(
        external_port=port,
        internal_host="127.0.0.1",
        internal_port=INTERNAL_PORT,
        ssl_ctx=ssl_ctx,
    )
    proxy.start()

    logger.info("Dual-stack server: external :%d (HTTP+HTTPS) -> internal :%d (HTTP)", port, INTERNAL_PORT)

    try:
        uvicorn.run(
            "app:app",
            host="127.0.0.1",
            port=INTERNAL_PORT,
            log_level="info",
        )
    finally:
        proxy.stop()


if __name__ == "__main__":
    run_dual_stack()

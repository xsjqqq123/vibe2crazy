# PyInstaller + Pyarmor Release Script Design

Date: 2026-03-27
Status: Approved

## Overview

Create `release.sh` script that packages Vibe2Crazy backend and frontend into a single executable using PyInstaller, with pyarmor obfuscation for code protection. Frontend static files are embedded in the executable and served by the backend.

## Target Platforms

- Linux
- Windows (requires building on Windows)
- macOS (requires building on macOS)

Each platform must build its own executable - no cross-compilation.

## Release Package Structure

```
release/
├── vibe2crazy          # Linux executable
├── vibe2crazy.exe      # Windows executable (built on Windows)
├── vibe2crazy-macos    # macOS executable (built on macOS)
├── .env.example        # Configuration template
└── README.txt          # Quick start instructions
```

User copies `.env.example` to `.env` and edits settings.

## Components

### 1. release.sh Script

**Functions:**

- `detect_platform()` - Identify current OS and set executable name
- `check_prerequisites()` - Verify pyarmor, pyinstaller, node, npm installed
- `install_dependencies()` - Install missing build tools if needed
- `build_frontend()` - Run `npm run build` in frontend directory
- `obfuscate_backend()` - Run pyarmor on backend/app directory
- `package_executable()` - Run PyInstaller on obfuscated code with embedded frontend
- `create_config_template()` - Generate `.env.example`
- `create_readme()` - Generate `README.txt` with usage instructions
- `cleanup()` - Remove temporary obfuscated files

**Build Flow:**

```
frontend/dist/           ← npm run build
    ↓
build/obfuscated/       ← pyarmor gen backend/app
    ↓
release/vibe2crazy      ← pyinstaller packages obfuscated + frontend
```

**Pyarmor Command:**

```bash
pyarmor gen --enable-rft --enable-bcc --enable-jac \
    --output build/obfuscated \
    backend/app
```

Options:
- `--enable-rft`: Restrict function types
- `--enable-bcc`: Bytecode compilation
- `--enable-jac`: Jump after call

**PyInstaller Command:**

```bash
pyinstaller --onefile \
    --name vibe2crazy \
    --add-data "frontend/dist:frontend/dist" \
    --add-data "build/obfuscated/app:app" \
    --hidden-import pyarmor_runtime_000000 \
    --hidden-import uvicorn \
    --hidden-import uvicorn.logging \
    --hidden-import uvicorn.loops \
    --hidden-import uvicorn.loops.auto \
    --hidden-import uvicorn.protocols \
    --hidden-import uvicorn.protocols.http \
    --hidden-import uvicorn.protocols.http.auto \
    --hidden-import uvicorn.protocols.websockets \
    --hidden-import uvicorn.protocols.websockets.auto \
    --hidden-import uvicorn.protocols.websockets.websockets_impl \
    --hidden-import sqlalchemy.dialects.sqlite \
    --hidden-import fastapi \
    --hidden-import pydantic \
    --hidden-import pydantic_settings \
    --hidden-import python_multipart \
    --hidden-import git \
    --hidden-import ptyprocess \
    --hidden-import jose \
    --collect-all pyarmor_runtime_000000 \
    build/obfuscated/app/main.py
```

### 2. Backend Entry Point Modifications

Modify `backend/app/main.py` to:

1. Detect if running as bundled executable
2. Serve frontend static files from bundled location when executable
3. Fall back to development paths when not bundled

**Code pattern:**

```python
import sys
from pathlib import Path

def get_frontend_path() -> Path:
    """Get frontend static files path based on runtime context."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        base_path = Path(sys._MEIPASS)
        return base_path / "frontend" / "dist"
    else:
        # Development mode
        return Path(__file__).parent.parent.parent / "frontend" / "dist"

# Mount frontend static files if directory exists
frontend_path = get_frontend_path()
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
```

### 3. Configuration Template

`release/.env.example`:

```env
# ===========================================
# Vibe2Crazy Configuration
# ===========================================

# Required Settings (MUST CHANGE before deployment)
# -------------------------------------------------
VIBE2CRAZY_PASSWORD=your-secure-password-here
SECRET_KEY=your-random-secret-key-here

# Server Settings
# ---------------
HOST=0.0.0.0
PORT=8863

# Storage Settings
# ----------------
PROJECTS_DIR=./projects
DATABASE_URL=sqlite:///./data/vibe2crazy.db

# Git Settings
# ------------
GIT_DEFAULT_BRANCH=main

# Session Settings
# ----------------
SESSION_EXPIRE_HOURS=24

# Tmux Settings
# -------------
TMUX_SESSION_PREFIX=vibe2crazy-
```

### 4. README.txt

`release/README.txt`:

```
Vibe2Crazy - Single Executable Release
======================================

Quick Start:
1. Copy .env.example to .env
2. Edit .env - change VIBE2CRAZY_PASSWORD and SECRET_KEY
3. Run: ./vibe2crazy
4. Open http://localhost:8863 in browser

Requirements:
- tmux must be installed on the system
- git must be installed for project management

Configuration:
- Edit .env file to customize settings
- Default port: 8863
- Data stored in ./data/ and ./projects/

Notes:
- First run creates database automatically
- Projects directory created automatically
- Logs output to stdout

Platform Builds:
- Linux: vibe2crazy
- Windows: vibe2crazy.exe
- macOS: vibe2crazy-macos

Each platform requires building on that platform.
```

## Prerequisites

Build machine requires:
- Python 3.10+ with pip
- Node.js 18+ with npm
- pyarmor (`pip install pyarmor`)
- pyinstaller (`pip install pyinstaller`)

Runtime machine requires:
- tmux (for terminal sessions)
- git (for project management)

## Error Handling

- Script checks for pyarmor/pyinstaller before starting
- Frontend build failure stops process with error message
- Pyarmor obfuscation failure stops process
- PyInstaller failure shows detailed error output
- Cleanup on failure removes partial build artifacts

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `release.sh` | Create | Build script |
| `backend/app/main.py` | Modify | Add bundled frontend detection |
| `release/.env.example` | Create | Configuration template |
| `release/README.txt` | Create | Usage instructions |

## Testing Plan

1. Run `./release.sh` on Linux
2. Verify `release/vibe2crazy` created
3. Copy `.env.example` to `.env`, edit password
4. Run executable, verify frontend loads
5. Test login, project creation, terminal access
6. Repeat on Windows and macOS if available
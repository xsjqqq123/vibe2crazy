# PyInstaller + Pyarmor Release Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create release.sh script that packages Vibe2Crazy into a single executable with pyarmor obfuscation and embedded frontend.

**Architecture:** Script builds frontend with npm, obfuscates backend with pyarmor, packages both with PyInstaller into single executable. Backend modified to detect bundled frontend and serve static files.

**Tech Stack:** Bash, PyInstaller, Pyarmor, npm/Vite, Python/FastAPI

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `release.sh` | Create | Build script for packaging |
| `backend/app/main.py` | Modify | Add bundled frontend detection and static file serving |
| `release/.env.example` | Create | Configuration template for users |
| `release/README.txt` | Create | Usage instructions |

---

### Task 1: Modify Backend Entry Point for Bundled Frontend

**Files:**
- Modify: `backend/app/main.py`
- Test: Manual test by running executable

This task modifies the FastAPI app to serve frontend static files when running as a bundled executable.

- [ ] **Step 1: Read current main.py to understand structure**

Run: Read `backend/app/main.py`
Purpose: Identify where to add frontend serving logic

- [ ] **Step 2: Add frontend path detection function**

Add this function after imports and before app creation (around line 45):

```python
import sys
from pathlib import Path

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
```

- [ ] **Step 3: Mount frontend static files after app creation**

Add this code after `app.include_router(global_terminal.router)` (around line 72), before the monitor service definition:

```python
# Mount frontend static files if bundled/available
frontend_path = get_frontend_path()
if frontend_path:
    logger.info(f"Serving frontend from: {frontend_path}")
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
else:
    logger.warning("Frontend static files not found - API-only mode")
```

- [ ] **Step 4: Verify imports are present**

Ensure these imports exist at top of file (they should already be there):
- `from fastapi.staticfiles import StaticFiles` (line 5)
- `from pathlib import Path` (line 7)

If `StaticFiles` import missing, add it.

- [ ] **Step 5: Commit backend changes**

```bash
git add backend/app/main.py
git commit -m "feat(backend): add bundled frontend detection for executable mode

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Create Configuration Template

**Files:**
- Create: `release/.env.example`

- [ ] **Step 1: Create release directory**

```bash
mkdir -p release
```

- [ ] **Step 2: Write configuration template**

```bash
cat > release/.env.example << 'EOF'
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

# CORS origins - comma separated
CORS_ORIGINS=http://localhost:8863

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
EOF
```

- [ ] **Step 3: Commit configuration template**

```bash
git add release/.env.example
git commit -m "feat(release): add configuration template for packaged executable

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Create README for Release Package

**Files:**
- Create: `release/README.txt`

- [ ] **Step 1: Write README file**

```bash
cat > release/README.txt << 'EOF'
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
Run ./release.sh on target platform to create executable.
EOF
```

- [ ] **Step 2: Commit README**

```bash
git add release/README.txt
git commit -m "feat(release): add README for packaged executable

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Create Release Script

**Files:**
- Create: `release.sh`

This is the main build script. It's a comprehensive script with multiple functions.

- [ ] **Step 1: Write the release.sh script**

```bash
cat > release.sh << 'SCRIPT_EOF'
#!/bin/bash
# Vibe2Crazy Release Script - Package with PyInstaller + Pyarmor
#
# Usage: ./release.sh
# Output: release/vibe2crazy (Linux) or vibe2crazy.exe (Windows) or vibe2crazy-macos

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_DIR="$SCRIPT_DIR/backend"
BUILD_DIR="$SCRIPT_DIR/build"
RELEASE_DIR="$SCRIPT_DIR/release"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Detect platform
detect_platform() {
    case "$(uname -s)" in
        Linux*)     PLATFORM="linux"; EXEC_NAME="vibe2crazy" ;;
        Darwin*)    PLATFORM="macos"; EXEC_NAME="vibe2crazy-macos" ;;
        CYGWIN*|MINGW*|MSYS*)    PLATFORM="windows"; EXEC_NAME="vibe2crazy.exe" ;;
        *)          echo -e "${RED}Unknown platform: $(uname -s)${NC}"; exit 1 ;;
    esac
    echo -e "${BLUE}Platform: $PLATFORM${NC}"
    echo -e "${BLUE}Executable name: $EXEC_NAME${NC}"
}

# Check prerequisites
check_prerequisites() {
    echo ""
    echo -e "${YELLOW}=== Checking Prerequisites ===${NC}"

    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python 3 is required but not installed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Python 3: $(python3 --version)${NC}"

    # Check pip
    if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
        echo -e "${RED}pip is required but not installed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ pip available${NC}"

    # Check Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${RED}Node.js is required but not installed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Node.js: $(node --version)${NC}"

    # Check npm
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}npm is required but not installed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ npm: $(npm --version)${NC}"

    echo -e "${GREEN}=== Prerequisites Check Complete ===${NC}"
}

# Install build tools
install_build_tools() {
    echo ""
    echo -e "${YELLOW}=== Installing Build Tools ===${NC}"

    # Check/install pyarmor
    if ! python3 -c "import pyarmor" 2>/dev/null; then
        echo -e "${YELLOW}Installing pyarmor...${NC}"
        pip3 install pyarmor --quiet
    fi
    echo -e "${GREEN}✓ pyarmor installed${NC}"

    # Check/install pyinstaller
    if ! python3 -c "import PyInstaller" 2>/dev/null; then
        echo -e "${YELLOW}Installing pyinstaller...${NC}"
        pip3 install pyinstaller --quiet
    fi
    echo -e "${GREEN}✓ pyinstaller installed${NC}"

    echo -e "${GREEN}=== Build Tools Installation Complete ===${NC}"
}

# Build frontend
build_frontend() {
    echo ""
    echo -e "${YELLOW}=== Building Frontend ===${NC}"

    cd "$FRONTEND_DIR"

    # Check node_modules
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing frontend dependencies...${NC}"
        npm install
    fi

    # Build frontend
    echo "Running npm build..."
    npm run build

    if [ ! -d "dist" ]; then
        echo -e "${RED}✗ Frontend build failed - dist directory not created${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ Frontend built successfully${NC}"
    echo -e "${GREEN}  Output: $FRONTEND_DIR/dist${NC}"

    cd "$SCRIPT_DIR"
}

# Obfuscate backend with pyarmor
obfuscate_backend() {
    echo ""
    echo -e "${YELLOW}=== Obfuscating Backend ===${NC}"

    # Create build directory
    mkdir -p "$BUILD_DIR"

    # Clean previous obfuscated output
    rm -rf "$BUILD_DIR/obfuscated"

    cd "$BACKEND_DIR"

    # Obfuscate with pyarmor
    # --enable-rft: Restrict function types
    # --enable-bcc: Bytecode compilation
    # --enable-jac: Jump after call
    echo "Running pyarmor obfuscation..."
    python3 -m pyarmor gen \
        --enable-rft \
        --enable-bcc \
        --enable-jac \
        --output "$BUILD_DIR/obfuscated" \
        --platform "$PLATFORM" \
        app

    if [ ! -d "$BUILD_DIR/obfuscated/app" ]; then
        echo -e "${RED}✗ Pyarmor obfuscation failed${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ Backend obfuscated successfully${NC}"
    echo -e "${GREEN}  Output: $BUILD_DIR/obfuscated/app${NC}"

    cd "$SCRIPT_DIR"
}

# Package with PyInstaller
package_executable() {
    echo ""
    echo -e "${YELLOW}=== Packaging Executable ===${NC}"

    cd "$SCRIPT_DIR"

    # Create release directory
    mkdir -p "$RELEASE_DIR"

    # Clean previous build artifacts
    rm -f "$BUILD_DIR/vibe2crazy.spec"
    rm -rf "$BUILD_DIR/build"

    # Build PyInstaller command
    # We need to create a temporary entry point that imports from obfuscated app
    cat > "$BUILD_DIR/entry.py" << 'ENTRY_EOF'
import sys
from pathlib import Path

# Add obfuscated app to path
sys.path.insert(0, str(Path(__file__).parent / "obfuscated"))

# Import and run the app
from app.main import app

# For PyInstaller, we need a console script entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8863)
ENTRY_EOF

    # Run PyInstaller
    echo "Running PyInstaller..."
    pyinstaller \
        --onefile \
        --name "$EXEC_NAME" \
        --distpath "$RELEASE_DIR" \
        --workpath "$BUILD_DIR/build" \
        --specpath "$BUILD_DIR" \
        --add-data "$FRONTEND_DIR/dist:frontend/dist" \
        --add-data "$BUILD_DIR/obfuscated/app:app" \
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
        --hidden-import uvicorn.lifespan \
        --hidden-import uvicorn.lifespan.on \
        --hidden-import sqlalchemy.dialects.sqlite \
        --hidden-import sqlalchemy.pool \
        --hidden-import sqlalchemy.engine \
        --hidden-import fastapi \
        --hidden-import fastapi.routing \
        --hidden-import pydantic \
        --hidden-import pydantic_settings \
        --hidden-import python_multipart \
        --hidden-import git \
        --hidden-import git.exc \
        --hidden-import git.repo \
        --hidden-import git.cmd \
        --hidden-import ptyprocess \
        --hidden-import jose \
        --hidden-import jose.jws \
        --hidden-import jose.jwt \
        --hidden-import dotenv \
        --hidden-import pyarmor_runtime \
        --collect-all pyarmor_runtime \
        --console \
        --clean \
        "$BUILD_DIR/entry.py"

    if [ ! -f "$RELEASE_DIR/$EXEC_NAME" ]; then
        echo -e "${RED}✗ PyInstaller packaging failed${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ Executable packaged successfully${NC}"
    echo -e "${GREEN}  Output: $RELEASE_DIR/$EXEC_NAME${NC}"
}

# Cleanup temporary files
cleanup() {
    echo ""
    echo -e "${YELLOW}=== Cleaning Up ===${NC}"

    rm -rf "$BUILD_DIR"
    echo -e "${GREEN}✓ Build directory cleaned${NC}"

    rm -f "$SCRIPT_DIR/$EXEC_NAME.spec"
    echo -e "${GREEN}✓ Spec files cleaned${NC}"
}

# Print success message
print_success() {
    echo ""
    echo -e "${GREEN}=== Release Build Complete ===${NC}"
    echo ""
    echo -e "${GREEN}Executable: $RELEASE_DIR/$EXEC_NAME${NC}"
    echo ""
    echo "Release package contents:"
    ls -la "$RELEASE_DIR"
    echo ""
    echo "To deploy:"
    echo "  1. Copy release/ directory to target machine"
    echo "  2. Copy .env.example to .env and edit settings"
    echo "  3. Run: ./$EXEC_NAME"
    echo ""
}

# Main
main() {
    echo ""
    echo -e "${BLUE}=== Vibe2Crazy Release Build ===${NC}"
    echo ""

    detect_platform
    check_prerequisites
    install_build_tools
    build_frontend
    obfuscate_backend
    package_executable
    cleanup
    print_success
}

main
SCRIPT_EOF
```

- [ ] **Step 2: Make script executable**

```bash
chmod +x release.sh
```

- [ ] **Step 3: Add release directory to .gitignore**

Add `build/` to gitignore to exclude temporary build files:

```bash
echo "build/" >> .gitignore
```

- [ ] **Step 4: Commit release script**

```bash
git add release.sh .gitignore
git commit -m "feat: add release.sh script for PyInstaller + Pyarmor packaging

- Builds frontend with npm
- Obfuscates backend with pyarmor (rft, bcc, jac)
- Packages into single executable with PyInstaller
- Supports Linux, Windows, macOS (build on target platform)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Test Release Build

**Files:**
- None (testing task)

- [ ] **Step 1: Run the release script**

```bash
./release.sh
```

Expected output:
- Frontend builds successfully
- Backend obfuscated
- Executable created in `release/vibe2crazy`

- [ ] **Step 2: Verify executable exists**

```bash
ls -la release/
```

Expected: `vibe2crazy` file present with reasonable size (~50-100MB)

- [ ] **Step 3: Test executable startup**

```bash
cd release
cp .env.example .env
# Edit password in .env for security
./vibe2crazy &
sleep 5
curl http://localhost:8863/health
```

Expected: `{"status": "healthy"}`

- [ ] **Step 4: Test frontend access**

```bash
curl http://localhost:8863/
```

Expected: HTML content from frontend

- [ ] **Step 5: Stop test executable**

```bash
pkill -f vibe2crazy
```

- [ ] **Step 6: Final commit if any fixes needed**

If testing revealed issues, fix them and commit.

---

## Self-Review Checklist

### Spec Coverage

| Spec Requirement | Task |
|------------------|------|
| release.sh script with detect_platform() | Task 4 |
| release.sh script with check_prerequisites() | Task 4 |
| release.sh script with install_dependencies() | Task 4 |
| release.sh script with build_frontend() | Task 4 |
| release.sh script with obfuscate_backend() | Task 4 |
| release.sh script with package_executable() | Task 4 |
| release.sh script with cleanup() | Task 4 |
| Backend entry point modifications | Task 1 |
| Configuration template | Task 2 |
| README.txt | Task 3 |
| Cross-platform support | Task 4 (detect_platform) |
| Pyarmor obfuscation with rft/bcc/jac | Task 4 |

### Placeholder Scan

✓ No TBD, TODO, or placeholder text
✓ All steps contain actual code or commands
✓ No vague descriptions without implementation

### Type Consistency

✓ All file paths are consistent across tasks
✓ Function names match between definition and usage
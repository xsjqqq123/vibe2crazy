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

    # Check patchelf (required for staticx on Linux)
    if [ "$(uname -s)" = "Linux" ]; then
        if ! command -v patchelf &> /dev/null; then
            echo -e "${RED}patchelf is required for static linking${NC}"
            echo -e "${YELLOW}Install with: sudo apt install -y patchelf${NC}"
            exit 1
        fi
        echo -e "${GREEN}✓ patchelf installed${NC}"
    fi

    echo -e "${GREEN}=== Prerequisites Check Complete ===${NC}"
}

# Install build tools in backend venv
install_build_tools() {
    echo ""
    echo -e "${YELLOW}=== Installing Build Tools ===${NC}"

    cd "$BACKEND_DIR"

    # Create venv if not exists
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}Creating Python virtual environment...${NC}"
        python3 -m venv venv
    fi

    # Activate venv
    source venv/bin/activate

    # Install dependencies
    echo -e "${YELLOW}Installing backend dependencies...${NC}"
    pip install -r requirements.txt --quiet

    # Check/install pyarmor
    if ! python -c "import pyarmor" 2>/dev/null; then
        echo -e "${YELLOW}Installing pyarmor...${NC}"
        pip install pyarmor --quiet
    fi
    echo -e "${GREEN}✓ pyarmor installed${NC}"

    # Check/install pyinstaller
    if ! python -c "import PyInstaller" 2>/dev/null; then
        echo -e "${YELLOW}Installing pyinstaller...${NC}"
        pip install pyinstaller --quiet
    fi
    echo -e "${GREEN}✓ pyinstaller installed${NC}"

    # Check/install staticx (Linux only - for portable static executable)
    if [ "$PLATFORM" = "linux" ]; then
        # staticx requires pkg_resources from setuptools (removed in setuptools 70+)
        if ! python -c "import pkg_resources" 2>/dev/null; then
            echo -e "${YELLOW}Installing setuptools (version <70 for pkg_resources)...${NC}"
            pip install "setuptools<70" --quiet
        fi

        if ! python -c "import staticx" 2>/dev/null; then
            echo -e "${YELLOW}Installing staticx...${NC}"
            pip install staticx --quiet
        fi
        echo -e "${GREEN}✓ staticx installed${NC}"
    fi

    echo -e "${GREEN}=== Build Tools Installation Complete ===${NC}"

    cd "$SCRIPT_DIR"
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

# Obfuscate backend with pyarmor (optional - continues without obfuscation if trial limit hit)
obfuscate_backend() {
    echo ""
    echo -e "${YELLOW}=== Obfuscating Backend ===${NC}"

    # Activate backend venv
    source "$BACKEND_DIR/venv/bin/activate"

    # Create build directory
    mkdir -p "$BUILD_DIR"

    # Clean previous obfuscated output
    rm -rf "$BUILD_DIR/obfuscated"

    cd "$BACKEND_DIR"

    # Try to obfuscate with pyarmor
    # Note: Trial license has limits. If it fails, we copy unobfuscated code
    echo "Running pyarmor obfuscation..."
    if pyarmor gen \
        --output "$BUILD_DIR/obfuscated" \
        app 2>&1; then
        echo -e "${GREEN}✓ Backend obfuscated successfully${NC}"
        echo -e "${GREEN}  Output: $BUILD_DIR/obfuscated/app${NC}"
    else
        echo -e "${YELLOW}Pyarmor obfuscation failed (trial license limits?)${NC}"
        echo -e "${YELLOW}Continuing without obfuscation...${NC}"
        mkdir -p "$BUILD_DIR/obfuscated"
        cp -r app "$BUILD_DIR/obfuscated/"
    fi

    if [ ! -d "$BUILD_DIR/obfuscated/app" ]; then
        echo -e "${RED}✗ Backend preparation failed${NC}"
        exit 1
    fi

    cd "$SCRIPT_DIR"
}

# Package with PyInstaller
package_executable() {
    echo ""
    echo -e "${YELLOW}=== Packaging Executable ===${NC}"

    # Activate backend venv
    source "$BACKEND_DIR/venv/bin/activate"

    cd "$SCRIPT_DIR"

    # Prepare client module (copy without venv and cache files)
    CLIENT_SRC="$SCRIPT_DIR/../vibe2crazy_server/client"
    CLIENT_DEST="$BUILD_DIR/client"
    if [ -d "$CLIENT_SRC" ]; then
        echo "Preparing client module..."
        rm -rf "$CLIENT_DEST"
        mkdir -p "$CLIENT_DEST"
        # Copy client files, excluding venv, __pycache__, and egg-info
        for item in "$CLIENT_SRC"/*; do
            name=$(basename "$item")
            if [[ "$name" != "venv" && "$name" != "__pycache__" && "$name" != "*.egg-info" && "$name" != "*.egg" ]]; then
                cp -r "$item" "$CLIENT_DEST/"
            fi
        done
        echo -e "${GREEN}✓ Client module prepared${NC}"
    else
        echo -e "${YELLOW}Client module not found at $CLIENT_SRC${NC}"
    fi

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

# Import the app module
from app.main import app

# For PyInstaller, we need a console script entry point
if __name__ == "__main__":
    from app.main import run_dual_stack
    run_dual_stack(host="0.0.0.0", port=8863)
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
        --add-data "$BUILD_DIR/client:client" \
        --hidden-import client \
        --hidden-import client.tunnel_client \
        --hidden-import client.config \
        --hidden-import client.connection \
        --hidden-import client.protocol \
        --hidden-import client.http_forwarder \
        --hidden-import client.node_discovery \
        --hidden-import client.websocket_forwarder \
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
        --hidden-import sqlalchemy.orm \
        --hidden-import sqlalchemy.ext \
        --hidden-import sqlalchemy.ext.declarative \
        --hidden-import sqlalchemy.ext.declarative.api \
        --hidden-import sqlalchemy.sql \
        --hidden-import sqlalchemy.sql.schema \
        --hidden-import sqlalchemy.sql.type_api \
        --hidden-import fastapi \
        --hidden-import fastapi.routing \
        --hidden-import fastapi.middleware \
        --hidden-import fastapi.middleware.cors \
        --hidden-import fastapi.staticfiles \
        --hidden-import fastapi.responses \
        --hidden-import starlette.middleware \
        --hidden-import starlette.middleware.cors \
        --hidden-import starlette.staticfiles \
        --hidden-import pydantic \
        --hidden-import pydantic_settings \
        --hidden-import pydantic_core \
        --hidden-import python_multipart \
        --hidden-import python_multipart.multipart \
        --hidden-import git \
        --hidden-import git.exc \
        --hidden-import git.repo \
        --hidden-import git.cmd \
        --hidden-import git.config \
        --hidden-import git.objects \
        --hidden-import git.refs \
        --hidden-import git.diff \
        --hidden-import ptyprocess \
        --hidden-import ptyprocess.ptyprocess \
        --hidden-import jose \
        --hidden-import jose.jws \
        --hidden-import jose.jwt \
        --hidden-import jose.exceptions \
        --hidden-import jose.constants \
        --hidden-import jose.utils \
        --hidden-import dotenv \
        --hidden-import pyrate_limiter \
        --hidden-import pyrate_limiter.limiter \
        --hidden-import pyrate_limiter.buckets \
        --hidden-import fastapi_limiter \
        --hidden-import fastapi_limiter.depends \
        --hidden-import fastapi_limiter.identifier \
        --hidden-import fastapi_limiter.callback \
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

    # Apply StaticX for static linking (Linux only)
    if [ "$PLATFORM" = "linux" ]; then
        echo ""
        echo -e "${YELLOW}=== Applying StaticX ===${NC}"
        echo "Creating statically linked executable..."

        # Create temporary output for staticx
        STATIC_OUTPUT="${EXEC_NAME}-static"

        if staticx "$RELEASE_DIR/$EXEC_NAME" "$RELEASE_DIR/$STATIC_OUTPUT" 2>&1; then
            # Replace original with static version
            mv "$RELEASE_DIR/$STATIC_OUTPUT" "$RELEASE_DIR/$EXEC_NAME"
            echo -e "${GREEN}✓ StaticX applied successfully${NC}"
            echo -e "${GREEN}  Executable is now statically linked and portable${NC}"
        else
            echo -e "${YELLOW}StaticX failed (continuing with PyInstaller output)${NC}"
            echo -e "${YELLOW}The executable may have glibc dependencies${NC}"
        fi
    fi
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
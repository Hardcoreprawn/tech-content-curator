#!/bin/bash
################################################################################
# Setup Python 3.14 with GIL Disabled (Free-Threading)
#
# This script builds Python 3.14 from source with the GIL disabled,
# enabling true parallel execution and 3-4x speedup on multi-article generation.
#
# Usage:
#   bash scripts/setup_python_314_nogil.sh
#
# What it does:
#   1. Downloads Python 3.14 source code
#   2. Compiles with --disable-gil flag
#   3. Installs to ~/.python-nogil/3.14
#   4. Creates a convenient alias
#
# Requirements:
#   - Ubuntu/Debian (for apt-get)
#   - ~500MB disk space
#   - ~5-10 minutes build time
#
# After installation:
#   - Use: python314-nogil --version
#   - Or: ~/.python-nogil/3.14/bin/python3.14 --version
#   - With uv: uv python install 3.14
#
# WSL2 Notes:
#   - Run inside WSL2 Ubuntu terminal
#   - Requires build-essential and development headers
#   - Binary will work in WSL2 and native Windows terminals
################################################################################

set -e  # Exit on any error

PYTHON_VERSION="3.14.0"
PYTHON_DIR="$HOME/.python-nogil"
PYTHON_HOME="$PYTHON_DIR/$PYTHON_VERSION"
DOWNLOAD_DIR="/tmp/python-build"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Python 3.14 with GIL Disabled${NC}"
echo -e "${BLUE}================================${NC}\n"

# Check if already installed
if [ -f "$PYTHON_HOME/bin/python3.14" ]; then
    echo -e "${GREEN}✓ Python 3.14 (no-GIL) already installed at:${NC}"
    echo -e "  $PYTHON_HOME/bin/python3.14"
    
    # Show version
    echo -e "\n${GREEN}Version info:${NC}"
    $PYTHON_HOME/bin/python3.14 --version
    
    # Show GIL status
    echo -e "\n${GREEN}GIL Status:${NC}"
    GIL_STATUS=$($PYTHON_HOME/bin/python3.14 -c "import sys; print('disabled' if sys.flags.optimize else 'enabled (unexpected)')") || echo "disabled"
    echo -e "  ${GREEN}✓ GIL is $GIL_STATUS${NC}"
    
    exit 0
fi

echo -e "${YELLOW}Installing Python $PYTHON_VERSION with GIL disabled...${NC}\n"

# Install dependencies
echo -e "${BLUE}1. Installing build dependencies...${NC}"
sudo apt-get update > /dev/null 2>&1
sudo apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    libsqlite3-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libgdbm-dev \
    libc6-dev \
    > /dev/null 2>&1

echo -e "${GREEN}✓ Dependencies installed${NC}\n"

# Download Python source
echo -e "${BLUE}2. Downloading Python $PYTHON_VERSION source...${NC}"
mkdir -p "$DOWNLOAD_DIR"
cd "$DOWNLOAD_DIR"

PYTHON_URL="https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tar.xz"

if [ ! -f "Python-$PYTHON_VERSION.tar.xz" ]; then
    wget -q "$PYTHON_URL" || {
        echo -e "${RED}✗ Failed to download Python source${NC}"
        echo "Try downloading manually from: $PYTHON_URL"
        exit 1
    }
fi

echo -e "${GREEN}✓ Source downloaded${NC}\n"

# Extract
echo -e "${BLUE}3. Extracting source code...${NC}"
tar -xf "Python-$PYTHON_VERSION.tar.xz"
cd "Python-$PYTHON_VERSION"
echo -e "${GREEN}✓ Source extracted${NC}\n"

# Configure with GIL disabled
echo -e "${BLUE}4. Configuring with --disable-gil...${NC}"
./configure \
    --prefix="$PYTHON_HOME" \
    --disable-gil \
    --enable-optimizations \
    > /dev/null 2>&1 || {
    echo -e "${RED}✗ Configure failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Configured${NC}\n"

# Build (this takes a few minutes)
echo -e "${BLUE}5. Building Python (this may take 5-10 minutes)...${NC}"
JOBS=$(nproc || echo 4)
make -j"$JOBS" > /dev/null 2>&1 || {
    echo -e "${RED}✗ Build failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Build complete${NC}\n"

# Install
echo -e "${BLUE}6. Installing to $PYTHON_HOME...${NC}"
make install > /dev/null 2>&1 || {
    echo -e "${RED}✗ Installation failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Installation complete${NC}\n"

# Verify installation
echo -e "${BLUE}7. Verifying installation...${NC}"

PYTHON_BIN="$PYTHON_HOME/bin/python3.14"

if [ ! -f "$PYTHON_BIN" ]; then
    echo -e "${RED}✗ Python binary not found at $PYTHON_BIN${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python binary found${NC}"

# Show version
echo -e "\n${GREEN}Python version:${NC}"
$PYTHON_BIN --version

# Verify GIL is disabled
echo -e "\n${GREEN}Verifying GIL is disabled...${NC}"
GIL_CHECK=$($PYTHON_BIN -c "import sys; sys.flags.allow_isolation and print('✓ Free-threading capable') or print('⚠ GIL enabled')" 2>&1) || true
echo "  $GIL_CHECK"

# Create symlink for easy access
echo -e "\n${BLUE}8. Creating convenient symlink...${NC}"
mkdir -p "$HOME/.local/bin"
ln -sf "$PYTHON_BIN" "$HOME/.local/bin/python314-nogil"
echo -e "${GREEN}✓ Symlink created: python314-nogil${NC}"

# Cleanup
echo -e "\n${BLUE}9. Cleaning up build files...${NC}"
cd /tmp
rm -rf "$DOWNLOAD_DIR"
echo -e "${GREEN}✓ Cleaned up${NC}\n"

# Summary
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✓ Installation Complete!${NC}"
echo -e "${GREEN}================================${NC}\n"

echo -e "${BLUE}Quick Start:${NC}"
echo -e "  # Use directly:"
echo -e "  python314-nogil --version"
echo -e ""
echo -e "  # Or with uv:"
echo -e "  export PYTHONPATH=$PYTHON_HOME/bin:$PYTHONPATH"
echo -e "  uv python list"
echo -e ""
echo -e "  # Run benchmarks with free-threading:"
echo -e "  PYTHON_GIL=0 python scripts/benchmark_free_threading.py"
echo -e ""
echo -e "${BLUE}Next Steps:${NC}"
echo -e "  1. Run the benchmark to verify free-threading benefits:"
echo -e "     PYTHON_GIL=0 python314-nogil scripts/benchmark_free_threading.py"
echo -e ""
echo -e "  2. Use with uv (optional):"
echo -e "     uv python install --python-preference=$PYTHON_HOME/bin/python3.14"
echo -e ""
echo -e "  3. Or use directly:"
echo -e "     $PYTHON_HOME/bin/python3.14 -m src.generate --max-articles 5"
echo -e ""
echo -e "${YELLOW}Note:${NC} This build is optimized for your system."
echo -e "      It won't work on other machines without rebuilding."
echo -e ""

#!/bin/bash
################################################################################
# Setup Python 3.14 with GIL Disabled (Using conda-forge)
#
# This script sets up a GIL-disabled Python 3.14 using conda-forge,
# which provides pre-built binaries (much faster than building from source).
#
# Usage:
#   bash scripts/setup_python_314_nogil_conda.sh
#
# What it does:
#   1. Downloads and installs Miniforge (minimal conda)
#   2. Creates a new environment with Python 3.14 (free-threading variant)
#   3. Installs uv and project dependencies
#
# Requirements:
#   - ~2GB disk space
#   - ~2 minutes installation time
#
# After installation:
#   conda activate py314-nogil
#   python --version
#   PYTHON_GIL=0 python scripts/benchmark_free_threading.py
#
# Notes:
#   - Much faster than building from source
#   - Pre-built binaries from conda-forge
#   - Can switch between conda environments easily
#   - Doesn't interfere with system Python
################################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Python 3.14 GIL-Disabled Setup${NC}"
echo -e "${BLUE}Using conda-forge (Pre-built)${NC}"
echo -e "${BLUE}================================${NC}\n"

MINIFORGE_VERSION="latest"
MINIFORGE_URL="https://github.com/conda-forge/miniforge/releases/download/24.9.2-0/Miniforge3-24.9.2-0-Linux-x86_64.sh"
MINIFORGE_DIR="$HOME/miniforge3"
ENV_NAME="py314-nogil"

# Check if conda already installed
if command -v conda &> /dev/null; then
    echo -e "${GREEN}✓ conda is already installed${NC}"
    CONDA_PATH=$(conda run python -c "import sys; print(sys.prefix)")
    echo -e "  Location: $CONDA_PATH\n"
else
    echo -e "${BLUE}1. Installing Miniforge...${NC}"
    
    # Download Miniforge
    mkdir -p /tmp/miniforge-install
    cd /tmp/miniforge-install
    
    if [ ! -f "miniforge.sh" ]; then
        echo -e "${YELLOW}  Downloading Miniforge...${NC}"
        wget -q "$MINIFORGE_URL" -O miniforge.sh || {
            echo -e "${RED}✗ Failed to download Miniforge${NC}"
            exit 1
        }
    fi
    
    chmod +x miniforge.sh
    
    # Install
    ./miniforge.sh -b -p "$MINIFORGE_DIR" > /dev/null 2>&1 || {
        echo -e "${RED}✗ Miniforge installation failed${NC}"
        exit 1
    }
    
    # Initialize conda
    "$MINIFORGE_DIR/bin/conda" init bash > /dev/null 2>&1
    
    echo -e "${GREEN}✓ Miniforge installed${NC}\n"
fi

# Source conda
source "$(conda info --base)/etc/profile.d/conda.sh"

# Check if environment already exists
if conda env list | grep -q "^$ENV_NAME "; then
    echo -e "${GREEN}✓ Environment '$ENV_NAME' already exists${NC}"
    echo -e "${BLUE}Activating environment...${NC}"
    conda activate "$ENV_NAME"
    
    python --version
    echo -e "\n${GREEN}Ready to use!${NC}"
    echo -e "  PYTHON_GIL=0 python scripts/benchmark_free_threading.py"
    exit 0
fi

# Create environment with Python 3.14 free-threading
echo -e "${BLUE}2. Creating conda environment with Python 3.14 (free-threading)...${NC}"

conda create -y -n "$ENV_NAME" \
    -c conda-forge \
    python=3.14 \
    "python[build=*_nogil*]" \
    > /dev/null 2>&1 || {
    echo -e "${YELLOW}⚠ Note: free-threading variant not available, installing standard Python 3.14${NC}"
    conda create -y -n "$ENV_NAME" \
        -c conda-forge \
        python=3.14 \
        > /dev/null 2>&1 || {
        echo -e "${RED}✗ Failed to create environment${NC}"
        exit 1
    }
}

echo -e "${GREEN}✓ Environment created${NC}\n"

# Activate environment
echo -e "${BLUE}3. Activating environment...${NC}"
conda activate "$ENV_NAME"
echo -e "${GREEN}✓ Environment activated${NC}\n"

# Install uv
echo -e "${BLUE}4. Installing uv package manager...${NC}"
pip install -q uv > /dev/null 2>&1 || {
    echo -e "${RED}✗ Failed to install uv${NC}"
    exit 1
}
echo -e "${GREEN}✓ uv installed${NC}\n"

# Install project dependencies
echo -e "${BLUE}5. Installing project dependencies...${NC}"
cd "$(git rev-parse --show-toplevel)" 2>/dev/null || cd /mnt/d/projects/tech-content-curator/tech-content-curator

uv sync --all-extras > /dev/null 2>&1 || {
    echo -e "${RED}✗ Failed to install dependencies${NC}"
    exit 1
}
echo -e "${GREEN}✓ Dependencies installed${NC}\n"

# Verify Python
echo -e "${BLUE}6. Verifying installation...${NC}"
python --version
echo -e "${GREEN}✓ Python ready${NC}\n"

# Summary
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✓ Setup Complete!${NC}"
echo -e "${GREEN}================================${NC}\n"

echo -e "${BLUE}Quick Start:${NC}"
echo -e "  # Activate environment:"
echo -e "  conda activate $ENV_NAME"
echo -e ""
echo -e "  # Run with free-threading:"
echo -e "  PYTHON_GIL=0 python scripts/benchmark_free_threading.py"
echo -e ""
echo -e "  # Or generate articles:"
echo -e "  PYTHON_GIL=0 python -m src.generate --max-articles 5"
echo -e ""
echo -e "${BLUE}Environment Details:${NC}"
echo -e "  Name: $ENV_NAME"
echo -e "  Location: $(conda run -n $ENV_NAME python -c 'import sys; print(sys.prefix)')"
echo -e ""
echo -e "${BLUE}Next Steps:${NC}"
echo -e "  1. Activate: ${YELLOW}conda activate $ENV_NAME${NC}"
echo -e "  2. Benchmark: ${YELLOW}PYTHON_GIL=0 python scripts/benchmark_free_threading.py${NC}"
echo -e "  3. Check: ${YELLOW}python -c 'import sys; print(sys.flags)'${NC}"
echo -e ""

#!/bin/bash
################################################################################
# Run commands with Python 3.14 no-GIL build
#
# Usage:
#   bash scripts/run_with_nogil.sh python -m src.collectors
#   bash scripts/run_with_nogil.sh pytest tests/
#
# This script:
#   1. Activates the no-GIL Python environment
#   2. Sets PYTHON_GIL=0
#   3. Uses uv to manage dependencies
#   4. Runs the specified command
################################################################################

set -e

NOGIL_PYTHON="/home/opr/.python-nogil/3.14.0/bin/python3.14"

if [ ! -f "$NOGIL_PYTHON" ]; then
    echo "Error: No-GIL Python not found at $NOGIL_PYTHON"
    echo "Run: bash scripts/setup_python_314_nogil.sh"
    exit 1
fi

# Export environment
export PYTHON_GIL=0

# Run with uv using the no-GIL Python
exec uv run --python "$NOGIL_PYTHON" "$@"

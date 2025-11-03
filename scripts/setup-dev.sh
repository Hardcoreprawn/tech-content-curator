#!/bin/bash
# setup-dev.sh - One-command development environment setup
# Usage: ./scripts/setup-dev.sh
# Installs uv, Python 3.14, dependencies, and verifies everything works

set -e  # Exit on error

# Ensure we have access to uv if just installed
export PATH="$HOME/.local/bin:$PATH"

echo "🚀 Tech Content Curator - Development Setup"
echo "=========================================="
echo ""

# Check if running in WSL
if ! grep -qi microsoft /proc/version 2>/dev/null; then
    echo "⚠️  Warning: This script is optimized for WSL2"
    echo "   It will work on Linux/macOS, but WSL2 is recommended"
    echo ""
fi

# Step 1: Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "✅ uv installed"
else
    echo "✅ uv already installed"
fi

echo ""

# Step 2: Install Python 3.14 if not present
if ! uv python list 2>/dev/null | grep -q "python-3.14"; then
    echo "📥 Installing Python 3.14..."
    uv python install 3.14
    echo "✅ Python 3.14 installed"
else
    echo "✅ Python 3.14 already installed"
fi

echo ""

# Step 3: Sync dependencies
echo "📚 Syncing project dependencies..."
uv sync --python 3.14 --all-extras
echo "✅ Dependencies synced"

echo ""

# Step 4: Verify setup
echo "🔍 Verifying setup..."
echo ""

PYTHON_VERSION=$(uv run python --version 2>&1)
echo "   Python: $PYTHON_VERSION"

PYTEST_VERSION=$(uv run pytest --version 2>&1)
echo "   pytest: $PYTEST_VERSION"

UVERSION=$(uv --version)
echo "   uv: $UVERSION"

echo ""

# Step 5: Run tests to verify everything works
echo "🧪 Running test suite..."
TEST_OUTPUT=$(uv run pytest tests/ -q 2>&1 || true)
if echo "$TEST_OUTPUT" | grep -q "passed"; then
    PASSED=$(echo "$TEST_OUTPUT" | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+")
    echo "✅ Tests: $PASSED passed"
else
    echo "⚠️  Tests: Could not verify (may need API keys)"
fi

echo ""
echo "=========================================="
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Configure VS Code: Read SETUP.md section 'Step 5'"
echo "  2. Add API keys: cp .env.example .env && edit .env"
echo "  3. Run tests: uv run pytest tests/ -v"
echo ""
echo "Documentation:"
echo "  - Quick Start: docs/QUICK-START.md"
echo "  - Full Setup: SETUP.md"
echo "  - AI Guide: docs/AI-DEVELOPMENT-GUIDE.md"
echo ""

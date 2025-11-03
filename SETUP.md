# Tech Content Curator - Setup Guide

Complete setup instructions for the Tech Content Curator project.

## System Requirements

### Minimum Requirements

- **Python**: 3.14+ (officially supported for free-threading)
- **Package Manager**: `uv` (astral.sh/uv)
- **OS**: Windows 10/11 with WSL2 or native Linux/macOS

### Recommended Setup

- **OS**: Ubuntu 24.04 LTS (via WSL2 on Windows)
- **Python**: 3.14+ (managed by uv)
- **Terminal**: WSL bash in VS Code

## Quick Start (Recommended: WSL2 on Windows)

### 1. Prepare WSL Environment

```bash
# Update WSL to Ubuntu 24.04 LTS
wsl --list --verbose           # Check current version
# If on Ubuntu 22.04, upgrade: sudo do-release-upgrade -d

# Inside WSL, verify Python and install build tools
lsb_release -a                 # Check Ubuntu version (should be 24.04)
python3 --version              # Check Python (should be 3.12+)
sudo apt-get update && sudo apt-get upgrade -y
```

### 2. Install uv Package Manager

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH (add this to ~/.bashrc or ~/.zshrc)
export PATH=/home/$USER/.local/bin:$PATH

# Verify installation
uv --version                   # Should show version 0.9.7+
```

### 3. Install Python 3.14

```bash
uv python install 3.14         # Download and install Python 3.14

# Verify
uv python list                 # Should show python-3.14.x
```

### 4. Set Up Project

```bash
# Clone and navigate to project
cd /path/to/tech-content-curator

# Sync dependencies with Python 3.14 and all extras (includes dev/pytest)
uv sync --python 3.14 --all-extras

# Verify setup
uv run python --version        # Should show 3.14.x
uv run pytest --version        # Should show pytest installed
```

### 5. Configure VS Code

VS Code will automatically detect the WSL environment. Settings are in `.vscode/settings.json`:

```json
{
  "terminal.integrated.defaultProfile.windows": "WSL",
  "terminal.integrated.profiles.windows": {
    "WSL": {
      "path": "wsl.exe",
      "args": ["-d", "Ubuntu", "-e", "bash", "-li"],
      "icon": "terminal-linux"
    }
  }
}
```

When you open a terminal in VS Code, it will automatically use WSL.

## Running Tests

### In WSL Terminal

```bash
# Navigate to project (VS Code does this automatically)
cd /mnt/d/projects/tech-content-curator

# Run all tests
uv run python -m pytest tests/ -v

# Run specific test file
uv run python -m pytest tests/test_illustrations.py -v

# Run with coverage
uv run python -m pytest tests/ --cov=src --cov-report=html
```

### Running Single Test

```bash
uv run python -m pytest tests/test_illustrations.py::TestListSectionDetection -v
```

## Environment Variables

Create a `.env` file in the project root:

```bash
# API Keys
OPENAI_API_KEY=your_openai_key_here

# Optional: Social Media API Keys
BLUESKY_USERNAME=your_handle
BLUESKY_PASSWORD=your_password
MASTODON_INSTANCE=mastodon.social
MASTODON_TOKEN=your_token

# Optional: Redis (for caching)
REDIS_URL=redis://localhost:6379/0
```

Never commit `.env` file to version control!

## Project Structure

```
.
├── src/                          # Main source code
│   ├── illustrations/            # Feature 3: AI-Powered Illustrations
│   │   ├── ai_mermaid_generator.py
│   │   ├── ai_ascii_generator.py
│   │   ├── ai_svg_generator.py
│   │   ├── placement.py
│   │   ├── detector.py
│   │   └── accessibility.py
│   ├── pipeline/                 # Core orchestrator
│   │   └── orchestrator.py
│   ├── models/                   # Data models
│   ├── collectors/               # Social media collectors
│   └── generators/               # Content generators
├── tests/                        # Test suite (331 tests)
├── docs/                         # Documentation
├── pyproject.toml                # Project configuration
├── .vscode/
│   ├── settings.json             # VS Code settings (WSL default)
│   └── launch.json               # Debug configurations
└── .env.example                  # Environment variables template
```

## Development Workflow

### 1. Create Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 2. Run Tests Before Committing
```bash
# Run all tests
uv run pytest tests/ -v

# Run linting
uv run ruff check src/
uv run ruff format src/

# Run type checking
uv run mypy src/
```

### 3. Commit and Push
```bash
git add .
git commit -m "Brief description of changes"
git push origin feature/your-feature-name
```

## Troubleshooting

### pytest not found

```bash
# Make sure all dependencies are synced, including dev extras
uv sync --python 3.14 --all-extras

# Run tests using python -m pytest
uv run python -m pytest tests/
```

### Wrong Python version

```bash
# Check active Python
uv run python --version

# Force Python 3.14
uv run --python 3.14 python --version

# Resync with correct version
uv sync --python 3.14 --all-extras --no-cache
```

### WSL Terminal Not Opening

1. Make sure `.vscode/settings.json` exists with correct WSL configuration
2. Restart VS Code
3. Open new terminal: Ctrl+`

### API Rate Limiting

The project includes rate limiting and caching. Check `src/rate_limit.py` for configuration.

## Testing Feature 3: Illustration System

The illustration system (Feature 3) uses AI to generate context-aware diagrams:

```bash
# Test illustration generation
uv run python -m pytest tests/test_illustrations.py -v

# Test format selection (Mermaid, ASCII, SVG)
uv run python -m pytest tests/test_illustrations_phase2.py -v

# Test orchestrator with illustrations
uv run python -m pytest tests/test_generate.py::test_generate_single_article_success -v
```

### Test Coverage

Current test coverage:

- Phase 1 (Foundation): 50 tests ✅
- Phase 2 (Intelligence): 38 tests ✅
- Phase 3 (Integration): 11 tests ✅
- Phase 4 (Multi-Format AI): Integrated into above ✅
- **Total: 331 tests passing**

## Performance Notes

### WSL vs Native
- **WSL2**: ~5-10% slower I/O than native, negligible for development
- **Full Fiber**: WSL network performance is excellent
- **Recommendation**: Use WSL for consistency with production Linux environment

### Test Execution Time
- Full test suite: ~5-10 seconds
- Single test: <1 second typically
- Integration tests with API mocks: 2-5 seconds

## Advanced Configuration

### Custom Python Version
```bash
# Use specific Python version
uv sync --python 3.13.9

# Switch between versions
uv run --python 3.12 python script.py
```

### Development Dependencies Only
```bash
# Install only dev dependencies (no main project)
uv venv venv --python 3.13
source venv/bin/activate
pip install -e ".[dev]"
```

### Local Testing with Real API Keys
```bash
# Create .env.local (not committed)
cp .env.example .env.local
# Edit .env.local with real API keys

# Run tests with real keys
export ENV_FILE=.env.local
uv run pytest tests/ -v
```

## Next Steps

1. ✅ WSL2 Setup Complete
2. ✅ Python 3.13 Installed
3. ✅ Dependencies Synced
4. ⏳ [Feature 3 Testing](#testing-feature-3-illustration-system) - Generate test articles with AI illustrations
5. ⏳ Real content collection and generation validation

## Support & Documentation

- **Feature 3 Design**: `docs/FEATURE-3-DESIGN.md`
- **Phase 4 Architecture**: `docs/PHASE-4-MULTIFORMAT-DESIGN.md`
- **Implementation Status**: `docs/IMPLEMENTATION-CHECKLIST.md`
- **Project README**: `README.md`

---

**Last Updated**: November 3, 2025
**Python Version**: 3.14+
**uv Version**: 0.9.7+
**OS**: Ubuntu 24.04 LTS (recommended)

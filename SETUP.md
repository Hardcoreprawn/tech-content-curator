# Tech Content Curator - Development Setup

Complete setup instructions for Windows developers using WSL2, optimized for VS Code and AI integration.

## Architecture Decision

This project is configured to run on **WSL2 (Linux)** for maximum consistency:
- ✅ Matches GitHub Actions CI/CD environment exactly
- ✅ Better performance via native WSL2 filesystem access
- ✅ Eliminates shell compatibility issues (bash vs PowerShell)
- ✅ Easier for AI to work with (single clear path)
- ✅ Consistent with Linux production deployments

**Why WSL2 instead of native Windows?**
- Python 3.14 free-threading works best on POSIX systems
- No PATH/shell escaping issues for AI to navigate
- GitHub Actions uses Ubuntu, so WSL ensures parity
- Modern WSL2 I/O performance is excellent

## System Requirements

- **Windows 10/11** with WSL2 enabled
- **Ubuntu 24.04 LTS** in WSL2 (or upgrade via `sudo do-release-upgrade -d`)
- **VS Code** with Python extension
- **~2GB** disk space for Python 3.14 + dependencies

## One-Command Setup (Recommended)

After cloning the repository, run this in WSL bash terminal:

```bash
cd /mnt/d/projects/tech-content-curator
./scripts/setup-dev.sh
```

This script handles:
- Installs `uv` package manager
- Downloads Python 3.14
- Syncs all dependencies (including dev/test)
- Configures VS Code environment
- Verifies everything works

**If the script is missing**, see [Manual Setup](#manual-setup-step-by-step) below.

## Manual Setup (Step-by-Step)

### Step 1: Prepare WSL Environment

```bash
# Inside WSL bash terminal
wsl --list --verbose                    # Check from Windows PowerShell
lsb_release -a                          # Should show Ubuntu 24.04 LTS
sudo apt-get update && sudo apt-get upgrade -y
```

### Step 2: Install `uv` Package Manager

`uv` manages Python versions and dependencies cleanly:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.bashrc                    # Reload PATH
uv --version                            # Verify (should be 0.9.7+)
```

### Step 3: Install Python 3.14

```bash
uv python install 3.14                  # Downloads and installs
uv python list                          # Verify python-3.14.x installed
```

### Step 4: Clone and Setup Project

```bash
cd /mnt/d/projects/tech-content-curator
uv sync --python 3.14 --all-extras      # Install dependencies
uv run pytest --version                 # Verify pytest works
```

### Step 5: Configure VS Code

VS Code needs to know about the WSL Python environment.

**Update `.vscode/settings.json`:**

```json
{
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": "explicit"
    }
  },
  "python.defaultInterpreterPath": "/usr/local/bin/python3.14",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"],
  "python.analysis.typeCheckingMode": "basic",
  "python.analysis.extraPaths": ["./src"],
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

This ensures:
- Integrated terminal opens in WSL bash
- Python extension finds the WSL Python
- pytest discovers tests correctly
- Formatting/linting uses ruff (consistent with CI)

## Verifying Your Setup

Run these commands in WSL bash terminal inside VS Code:

```bash
# Verify Python version
uv run python --version            # Should show 3.14.x

# Verify dependencies installed
uv run pytest --version            # Should work

# Run test suite
uv run pytest tests/ -v            # Should show passing tests

# Verify ruff (linter)
uv run ruff --version              # Should work
```

If all show correct versions/output, **setup is complete!**

## Daily Development Workflow

### Running Code

Always use `uv run` to ensure the right Python is used:

```bash
uv run python script.py             # Run a script
uv run pytest tests/                # Run tests
uv run mypy src/                    # Type checking
uv run ruff check src/              # Linting
uv run ruff format src/             # Auto-format
```

**Important for AI agents:** Always prefix Python commands with `uv run` to guarantee the correct environment.

### Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Specific test file
uv run pytest tests/test_illustrations.py -v

# Specific test class
uv run pytest tests/test_illustrations.py::TestListSectionDetection -v

# With coverage
uv run pytest tests/ --cov=src --cov-report=html
```

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature

# Make changes and run tests
uv run pytest tests/ -v

# Commit with descriptive message
git commit -m "Add feature: description"

# Push to GitHub
git push origin feature/your-feature
```

## Environment Variables

Create `.env` file in project root (never commit):

```bash
# Required for AI features
OPENAI_API_KEY=sk-...

# Optional social media APIs
BLUESKY_USERNAME=your.handle
BLUESKY_PASSWORD=your_app_password
MASTODON_INSTANCE=mastodon.social
MASTODON_TOKEN=your_token
```

Copy from `.env.example` to get started:

```bash
cp .env.example .env
# Edit .env with your keys
```

## Troubleshooting

### Terminal Issues (Multiple Spawning, "Terminal Broken")

**Symptom**: VS Code opens 15-20 new terminal tabs instead of one, terminals won't respond, or "terminal broken" errors

**Root Cause**: Usually triggered by WSL Ubuntu upgrade (e.g., 22.04 → 24.04), terminal profile misconfiguration, or bash initialization loops

**⚡ Quick Fix**:

1. **Close VS Code completely** (not just minimize)
2. **In PowerShell**: `wsl --shutdown` (terminates WSL)
3. **Reopen VS Code** - should have clean terminal
4. **Open new terminal** (Ctrl+` or View → Terminal)

**If issue persists**:

```bash
# Run this ONCE in WSL to clean bash initialization
bash scripts/wsl-reset-terminals.sh
```

Then:
1. Close all terminal tabs
2. Restart VS Code
3. Open new terminal

**If still broken** (nuclear option - clears everything):

```powershell
# In PowerShell as admin
wsl --terminate Ubuntu
wsl --unregister Ubuntu
# Then reinstall Ubuntu from Microsoft Store or Windows Terminal
```

**Ubuntu 24.04 Specific Issues**:

After upgrading from 22.04 to 24.04:
- systemd may be enabled (can interfere with terminals)
- bash initialization may have changed

Check:
```bash
cat /etc/wsl.conf | grep -i systemd
```

If it shows `systemd=true` and you have terminal issues, try disabling it (requires modifying `/etc/wsl.conf` - you may need `sudo` access).

**VS Code Profile Issue**:

The terminal profile in `.vscode/settings.json` should be simple:

```json
"terminal.integrated.defaultProfile.windows": "WSL",
"terminal.integrated.profiles.windows": {
  "WSL": {
    "path": "wsl.exe",
    "args": ["-d", "Ubuntu"],
    "icon": "terminal-linux"
  }
}
```

Don't use `-e bash -li` (can cause re-initialization loops).

### "Python not found" in VS Code

1. Check terminal is using WSL (should show `user@computer:/mnt/d/projects/...`)
2. Verify in WSL: `which python3.14` (should show a path)
3. Restart VS Code
4. In VS Code: Ctrl+Shift+P → "Python: Select Interpreter" → Choose WSL Python

### "uv command not found"

The `uv` installation added to `~/.bashrc`. Make sure you're using bash, not sh:

```bash
bash --version                  # Should be version 4.x or 5.x
source $HOME/.bashrc
uv --version                    # Should now work
```

### Wrong Python version when running tests

```bash
# Check which Python pytest is using
uv run which python

# If wrong, resync with explicit version
uv sync --python 3.14 --all-extras --no-cache
```

### VS Code shows wrong test count or can't find tests

1. Run in WSL terminal: `uv run pytest tests/ --collect-only`
2. If it fails, dependencies may not be installed: `uv sync --python 3.14 --all-extras`
3. Reload VS Code window: Ctrl+Shift+P → "Developer: Reload Window"

### Running on older Python version

If you need to test with Python 3.13 or 3.12:

```bash
uv python install 3.13           # Install if needed
uv sync --python 3.13            # Use specific version
uv run pytest tests/ -v          # Tests will use 3.13
uv sync --python 3.14            # Switch back to 3.14
```

## For AI Agents / Automation

If you're an AI helping with this project, **use these commands**:

```bash
# Always start with
cd /mnt/d/projects/tech-content-curator

# Run Python code - always prefix with uv
uv run python -c "import sys; print(sys.version)"

# Run tests - always use uv run
uv run pytest tests/test_file.py -v --tb=short

# Install dependencies
uv sync --python 3.14 --all-extras

# Verify environment
uv run python --version
uv run pytest --version
```

**Golden Rule:** If it's a Python command and you're in WSL, prefix it with `uv run`.

## Project Structure

```
tech-content-curator/
├── src/                          # Main source code
│   ├── illustrations/            # AI diagram generation
│   ├── pipeline/                 # Core orchestrator
│   ├── models/                   # Data models
│   └── ...
├── tests/                        # Test suite (~100 tests)
├── docs/                         # Documentation
├── .vscode/
│   ├── settings.json            # VS Code configuration
│   └── launch.json              # Debug configuration
├── pyproject.toml               # Project metadata & dependencies
├── uv.lock                      # Locked dependency versions
├── .env.example                 # Environment template
└── SETUP.md                     # This file
```

## Storage & Performance Optimization

### WSL2 File Location

Store the project on **Windows NTFS** (`/mnt/d/...`) for best performance:
- ✅ Direct access to Windows filesystem
- ✅ Fast I/O for tests and development
- ✅ No serialization overhead

```bash
# GOOD - Native Windows filesystem
/mnt/d/projects/tech-content-curator

# AVOID - WSL home directory (slower)
~/projects/tech-content-curator
```

### Disk Space Required

- Python 3.14 + dependencies: ~1GB
- Git repository: ~300MB
- Virtual environments: ~500MB (included in above)
- Test artifacts/cache: ~100MB

**Total: ~2GB available recommended**

## Next Steps

1. ✅ Complete setup per steps above
2. ✅ Verify with troubleshooting section if needed
3. ⏳ Read `docs/QUICK-START.md` for project overview
4. ⏳ Run sample: `uv run python demo/demo_single_article.py`
5. ⏳ Run full test suite: `uv run pytest tests/ -v`

## Additional Resources

- **Quick Start**: `docs/QUICK-START.md`
- **Architecture**: `docs/FEATURE-3-DESIGN.md`
- **Implementation Plan**: `docs/ILLUSTRATION-QUALITY-IMPLEMENTATION.md`
- **Python Project**: `pyproject.toml`

---

**Last Updated:** November 3, 2025  
**Tested On:** Windows 11 + WSL2 Ubuntu 24.04 LTS + Python 3.14 + uv 0.9.7+  
**For:** VS Code + Windows Developers with WSL2  
**Also Works:** Linux/macOS (adapt WSL-specific sections)

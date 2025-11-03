# AI Development Cheatsheet

Quick reference for AI agents working on this project. **Always follow these patterns.**

## Environment

- **Location**: `/mnt/d/projects/tech-content-curator` (always use WSL)
- **Python**: 3.14 (managed by `uv`)
- **Package Manager**: `uv` (not pip)
- **Shell**: bash (not PowerShell)

**Golden Rule:** When in doubt about environment, use `uv run <command>`

## Standard Commands

```bash
# Navigate to project
cd /mnt/d/projects/tech-content-curator

# Check Python version (do this first)
uv run python --version

# Run Python script
uv run python script.py

# Run code snippet
uv run python -c "import src.models; print(src.models)"

# Run tests
uv run pytest tests/ -v
uv run pytest tests/test_file.py -v
uv run pytest tests/test_file.py::TestClass::test_method -v

# Check code quality
uv run ruff check src/
uv run ruff format src/

# Type checking
uv run mypy src/

# Install new dependency
uv add package_name
uv add package_name --optional dev  # dev dependency
```

## Common Patterns

### Reading/Writing Files

```python
# Always include proper type hints
from pathlib import Path

# Read
content = Path("file.py").read_text()

# Write
Path("file.py").write_text(content)

# Append
with open("file.py", "a") as f:
    f.write("new content\n")
```

### Testing Your Changes

```bash
# After editing source code, ALWAYS run relevant tests
uv run pytest tests/test_file_you_changed.py -v

# Before committing, run full suite
uv run pytest tests/ -v

# If tests fail, check what changed
git diff
```

### Creating New Files

```bash
# Create with proper content (always include docstring)
cat > src/new_module.py << 'EOF'
"""Module description."""

from typing import Optional

def my_function(arg: str) -> Optional[str]:
    """Function description."""
    return arg.upper()
EOF

# Then run tests to verify imports work
uv run pytest tests/ -v
```

## Project Structure (for Reference)

```
src/
├── illustrations/          # Diagram/illustration generation
│   ├── ai_mermaid_generator.py
│   ├── ai_ascii_generator.py
│   ├── diagram_validator.py
│   ├── mermaid_quality_selector.py
│   ├── placement.py
│   └── detector.py
├── pipeline/              # Core orchestration
│   ├── orchestrator.py
│   ├── illustration_service.py
│   └── generator.py
├── models.py              # Data models (Pydantic)
├── config.py              # Configuration loading
└── ...

tests/
├── test_illustrations.py
├── test_mermaid_quality_selector.py
├── test_multi_candidate_selection.py
├── test_diagram_validator.py
└── ...
```

## Key Classes to Know

### Configuration
```python
from src.models import PipelineConfig
config = PipelineConfig(
    openai_api_key="...",
    mermaid_candidates=3,
    diagram_validation_threshold=0.7,
)
```

### Illustration Service
```python
from src.pipeline.illustration_service import IllustrationService
service = IllustrationService(client, config)
result = service.generate_illustrations(generator_name, content)
```

### Mermaid Quality Selector
```python
from src.illustrations.mermaid_quality_selector import MermaidQualitySelector
selector = MermaidQualitySelector(client, n_candidates=3)
result = selector.generate_best(section_title, section_content, concept_type)
```

## Error Handling

**When you encounter an error:**

1. Check Python version: `uv run python --version`
2. Check dependencies: `uv run pytest --version`
3. Check test with simpler case: `uv run pytest tests/test_illustrations.py::TestListSectionDetection::test_detect_list_section -v`
4. Look at error message - it usually tells you what's wrong
5. Check if you need to install a dependency: `uv add package_name`

## Git Workflow

```bash
# Check status
git status

# See what you changed
git diff

# Make sure tests pass
uv run pytest tests/ -v

# Stage changes
git add src/file.py tests/test_file.py

# Commit with descriptive message
git commit -m "Add feature: description of changes"

# Push to branch
git push origin feature-branch

# Check if remote is ahead
git fetch origin
git log --oneline -5
```

## Testing Guidelines

### Write Tests Like This

```python
"""Tests for my_module."""

from unittest.mock import Mock

def test_function_returns_uppercase():
    """Function converts string to uppercase."""
    from src.my_module import my_function
    
    result = my_function("hello")
    assert result == "HELLO"

def test_function_with_mock():
    """Function calls dependency correctly."""
    mock_dep = Mock()
    
    from src.my_module import MyClass
    obj = MyClass(dep=mock_dep)
    obj.do_something()
    
    mock_dep.assert_called_once()
```

### Run Specific Tests

```bash
# Single test
uv run pytest tests/test_file.py::test_function -v

# Multiple tests in class
uv run pytest tests/test_file.py::TestClass -v

# All tests matching pattern
uv run pytest tests/ -k "list_section" -v

# With output showing print statements
uv run pytest tests/ -v -s
```

## Documentation References

- **Setup**: SETUP.md (full instructions)
- **Quick Start**: docs/QUICK-START.md
- **Architecture**: docs/FEATURE-3-DESIGN.md
- **Implementation Plan**: docs/ILLUSTRATION-QUALITY-IMPLEMENTATION.md

## Debugging Tips

### Check imports work
```bash
uv run python -c "from src.illustrations.mermaid_quality_selector import MermaidQualitySelector; print('OK')"
```

### List what was imported
```bash
uv run python -c "import src; print(dir(src))"
```

### Check which version of package is installed
```bash
uv run python -c "import openai; print(openai.__version__)"
```

### Run test with full traceback
```bash
uv run pytest tests/test_file.py -v --tb=long
```

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| "pytest not found" | `uv sync --python 3.14 --all-extras` |
| "wrong Python version" | `uv run python --version` to verify, then `uv sync --python 3.14` to reset |
| "import error" | Check file exists, package is in pyproject.toml, run `uv sync` |
| "test fails" | Run with `-v -s` to see output, check test expectations |
| "file not found" | Use absolute paths or Path() object, check working directory |

---

**Last Updated:** November 3, 2025  
**For:** AI Agents and Developers  
**Python:** 3.14+ via uv  
**Platform:** WSL2 (Windows) or Linux

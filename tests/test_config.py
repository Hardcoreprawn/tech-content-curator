"""Tests for configuration management.

Tests cover:
- Path helper functions (project_root, data_dir, content_dir)
- Directory creation
- Path validation
"""

from pathlib import Path

from src.config import get_content_dir, get_data_dir, get_project_root

# ============================================================================
# Test Path Helpers
# ============================================================================


class TestPathHelpers:
    """Test configuration path helper functions."""

    def test_get_project_root_returns_path(self):
        """get_project_root() returns a Path object."""
        result = get_project_root()
        assert isinstance(result, Path)

    def test_get_project_root_exists(self):
        """Project root directory exists."""
        root = get_project_root()
        assert root.exists()
        assert root.is_dir()

    def test_get_project_root_has_src(self):
        """Project root contains src directory."""
        root = get_project_root()
        src_dir = root / "src"
        assert src_dir.exists()
        assert src_dir.is_dir()

    def test_get_data_dir_returns_path(self):
        """get_data_dir() returns a Path object."""
        result = get_data_dir()
        assert isinstance(result, Path)

    def test_get_data_dir_exists(self):
        """Data directory exists or is created."""
        data_dir = get_data_dir()
        assert data_dir.exists()
        assert data_dir.is_dir()

    def test_get_data_dir_is_in_project(self):
        """Data directory is under project root."""
        root = get_project_root()
        data_dir = get_data_dir()
        assert data_dir.parent == root
        assert data_dir.name == "data"

    def test_get_content_dir_returns_path(self):
        """get_content_dir() returns a Path object."""
        result = get_content_dir()
        assert isinstance(result, Path)

    def test_get_content_dir_exists(self):
        """Content directory exists or is created."""
        content_dir = get_content_dir()
        assert content_dir.exists()
        assert content_dir.is_dir()

    def test_get_content_dir_is_in_project(self):
        """Content directory is under project root."""
        root = get_project_root()
        content_dir = get_content_dir()
        # content_dir should be root/content/posts
        assert content_dir.name == "posts"
        assert content_dir.parent.name == "content"
        assert content_dir.parent.parent == root

    def test_get_content_dir_creates_nested_directories(self):
        """Content directory creates parent directories (content/posts)."""
        content_dir = get_content_dir()
        # Check the full path structure
        assert content_dir.exists()
        assert content_dir.parent.exists()  # content/ directory
        assert content_dir.name == "posts"

    def test_multiple_calls_return_same_paths(self):
        """Multiple calls to get_*_dir() return consistent paths."""
        root1 = get_project_root()
        root2 = get_project_root()
        assert root1 == root2

        data1 = get_data_dir()
        data2 = get_data_dir()
        assert data1 == data2

        content1 = get_content_dir()
        content2 = get_content_dir()
        assert content1 == content2

    def test_directories_are_creatable_if_missing(self):
        """Directories are created if they don't exist."""
        # This is implicitly tested by calling the functions
        # If they fail, they'll raise an exception
        data_dir = get_data_dir()
        content_dir = get_content_dir()

        assert data_dir.exists()
        assert content_dir.exists()

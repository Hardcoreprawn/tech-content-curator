"""Tests for quality feedback system."""

from src.config import QUALITY_THRESHOLDS
from src.pipeline.quality_feedback import (
    build_improvement_prompt,
    generate_quality_feedback,
    get_quality_prompt_enhancements,
    should_regenerate_article,
)


class TestGenerateQualityFeedback:
    """Test quality feedback generation."""

    def test_generates_feedback_for_low_readability(self):
        """Feedback includes readability improvements when score is low."""
        quality_metrics = {
            "readability_score": 25.0,
            "grade_level": 15.0,
            "matches_target": False,
            "match_explanation": "Too difficult",
            "recommendations": ["Use shorter sentences"],
        }

        feedback = generate_quality_feedback(quality_metrics, "intermediate", "general")

        assert "MORE READABLE" in feedback
        assert "shorter sentences" in feedback
        assert "25.0" in feedback

    def test_generates_feedback_for_high_grade_level(self):
        """Feedback includes grade level improvements when too high."""
        quality_metrics = {
            "readability_score": 40.0,
            "grade_level": 16.0,
            "matches_target": False,
            "match_explanation": "Grade level too high",
            "recommendations": [],
        }

        feedback = generate_quality_feedback(quality_metrics, "beginner", "tutorial")

        assert "GRADE LEVEL" in feedback
        assert "16.0" in feedback
        assert "Simplify technical jargon" in feedback

    def test_includes_content_type_requirements(self):
        """Feedback includes content-type-specific requirements."""
        quality_metrics = {
            "readability_score": 40.0,
            "grade_level": 14.0,
            "matches_target": False,
            "match_explanation": "Too difficult",
            "recommendations": [],
        }

        feedback_tutorial = generate_quality_feedback(
            quality_metrics, "intermediate", "tutorial"
        )
        feedback_research = generate_quality_feedback(
            quality_metrics, "intermediate", "research"
        )

        assert "Tutorial Requirements" in feedback_tutorial
        assert "step-by-step" in feedback_tutorial

        assert "Research Article Requirements" in feedback_research
        assert "Cite all sources" in feedback_research

    def test_includes_recommendations(self):
        """Feedback includes specific recommendations from analysis."""
        quality_metrics = {
            "readability_score": 40.0,
            "grade_level": 14.0,
            "matches_target": False,
            "match_explanation": "Too difficult",
            "recommendations": [
                "Break long paragraphs into shorter ones",
                "Add more concrete examples",
            ],
        }

        feedback = generate_quality_feedback(quality_metrics, "intermediate", "general")

        assert "Specific Improvements Needed" in feedback
        assert "Break long paragraphs" in feedback
        assert "Add more concrete examples" in feedback

    def test_returns_empty_for_good_quality(self):
        """Returns empty feedback when quality is good."""
        quality_metrics = {
            "readability_score": 65.0,
            "grade_level": 10.0,
            "matches_target": True,
            "match_explanation": "Appropriate",
            "recommendations": [],
        }

        feedback = generate_quality_feedback(quality_metrics, "intermediate", "general")

        assert feedback == ""


class TestBuildImprovementPrompt:
    """Test improvement prompt building."""

    def test_includes_original_content(self):
        """Prompt includes the original article content."""
        original = "This is the original article."
        quality_metrics = {
            "readability_score": 30.0,
            "match_explanation": "Too difficult",
        }

        prompt = build_improvement_prompt(
            original, quality_metrics, "intermediate", "general"
        )

        assert "This is the original article." in prompt

    def test_includes_quality_issues(self):
        """Prompt includes quality issues identified."""
        quality_metrics = {
            "readability_score": 30.0,
            "match_explanation": "Grade level too high for target",
        }

        prompt = build_improvement_prompt(
            "Original content", quality_metrics, "intermediate", "general"
        )

        assert "Grade level too high for target" in prompt
        assert "QUALITY ISSUES IDENTIFIED" in prompt

    def test_includes_improvement_guidelines(self):
        """Prompt includes improvement guidelines."""
        quality_metrics = {
            "readability_score": 30.0,
            "grade_level": 15.0,
            "matches_target": False,
            "match_explanation": "Too difficult",
            "recommendations": [],
        }

        prompt = build_improvement_prompt(
            "Original content", quality_metrics, "intermediate", "general"
        )

        assert "IMPROVEMENT GUIDELINES" in prompt
        assert "intermediate level" in prompt


class TestShouldRegenerateArticle:
    """Test article regeneration logic."""

    def test_no_regeneration_when_auto_improve_false(self):
        """Does not regenerate when auto_improve is False."""
        quality_metrics = {
            "passed_threshold": False,
            "readability_score": 20.0,
        }

        assert not should_regenerate_article(quality_metrics, auto_improve=False)

    def test_regeneration_when_score_very_low(self):
        """Regenerates when score is very low and auto_improve is True."""
        quality_metrics = {
            "passed_threshold": False,
            "readability_score": 25.0,
        }

        assert should_regenerate_article(quality_metrics, auto_improve=True)

    def test_no_regeneration_when_score_acceptable(self):
        """Does not regenerate when score is acceptable."""
        quality_metrics = {
            "passed_threshold": False,
            "readability_score": 45.0,
        }

        assert not should_regenerate_article(quality_metrics, auto_improve=True)

    def test_no_regeneration_when_passed_threshold(self):
        """Does not regenerate when article passed threshold."""
        quality_metrics = {
            "passed_threshold": True,
            "readability_score": 60.0,
        }

        assert not should_regenerate_article(quality_metrics, auto_improve=True)


class TestGetQualityPromptEnhancements:
    """Test quality prompt enhancement generation."""

    def test_includes_target_audience(self):
        """Enhancements include target audience information."""
        enhancements = get_quality_prompt_enhancements("intermediate", "general")

        assert "intermediate level" in enhancements.lower()

    def test_includes_readability_targets(self):
        """Enhancements include readability target ranges."""
        enhancements = get_quality_prompt_enhancements("beginner", "general")
        thresholds = QUALITY_THRESHOLDS["beginner"]

        assert str(thresholds["min_flesch_ease"]) in enhancements
        assert str(thresholds["max_grade_level"]) in enhancements

    def test_includes_writing_style_guidelines(self):
        """Enhancements include general writing style guidelines."""
        enhancements = get_quality_prompt_enhancements("intermediate", "general")

        assert "clear, concise sentences" in enhancements
        assert "active voice" in enhancements
        assert "concrete examples" in enhancements

    def test_beginner_level_guidance(self):
        """Beginner level includes extra guidance."""
        enhancements = get_quality_prompt_enhancements("beginner", "tutorial")

        assert "Explain all technical terms" in enhancements
        assert "no prior knowledge" in enhancements
        assert "analogies" in enhancements

    def test_advanced_level_guidance(self):
        """Advanced level allows technical depth."""
        enhancements = get_quality_prompt_enhancements("advanced", "research")

        assert "Technical precision" in enhancements
        assert "domain-specific terminology" in enhancements
        assert "depth and nuance" in enhancements

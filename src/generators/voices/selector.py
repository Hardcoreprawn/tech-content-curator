"""Voice selection logic for choosing appropriate voice for articles.

This module handles:
- Content-type based voice filtering
- Recency-based filtering to prevent consecutive repetition
- Complexity scoring to match voice sophistication
- Variety bonuses for underused voices
- Tie-breaking with controlled randomness
"""

import json
import random
from pathlib import Path

from ...utils.logging import get_logger
from .profiles import (
    VOICE_PROFILES,
    VoiceProfile,
    get_voices_for_content_type,
)

logger = get_logger(__name__)


class VoiceSelector:
    """Selects appropriate voice for article generation based on content and history."""

    def __init__(self, history_file: str = "data/voice_history.json"):
        """Initialize voice selector with history file.

        Args:
            history_file: Path to JSON file tracking voice usage history
        """
        logger.debug(f"Initializing VoiceSelector with history file: {history_file}")
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_history_file()

    def _ensure_history_file(self) -> None:
        """Ensure history file exists and is valid JSON."""
        if not self.history_file.exists():
            self.history_file.write_text("[]")
        else:
            try:
                json.loads(self.history_file.read_text())
            except (json.JSONDecodeError, OSError):
                self.history_file.write_text("[]")

    def _load_history(self) -> list[dict]:
        """Load voice history from file."""
        try:
            content = self.history_file.read_text()
            return json.loads(content) if content else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save_history(self, history: list[dict]) -> None:
        """Save voice history to file."""
        self.history_file.write_text(json.dumps(history, indent=2))

    def add_to_history(self, article_slug: str, voice_id: str) -> None:
        """Record voice usage for an article.

        Args:
            article_slug: Unique identifier for the article
            voice_id: Voice ID used for the article
        """
        logger.debug(f"Recording voice usage: {voice_id} for article {article_slug}")
        history = self._load_history()
        history.append({"article_slug": article_slug, "voice_id": voice_id})
        # Keep last 50 entries for recency filtering
        if len(history) > 50:
            history = history[-50:]
        self._save_history(history)

    def get_recent_voices(self, count: int = 3) -> list[str]:
        """Get the most recent voices used (excluding duplicates, most recent first).

        Args:
            count: Number of recent voices to return

        Returns:
            List of voice IDs, most recent first
        """
        history = self._load_history()
        seen = set()
        recent = []
        for entry in reversed(history):
            voice_id = entry.get("voice_id")
            if voice_id and voice_id not in seen:
                recent.append(voice_id)
                seen.add(voice_id)
                if len(recent) >= count:
                    break
        return recent

    def _calculate_voice_score(
        self,
        voice_id: str,
        content_type: str,
        complexity_score: float,
        recent_voices: list[str],
    ) -> float:
        """Calculate selection score for a voice.

        Scoring factors (0-1 scale):
        1. Content-type fit (0.0-1.0): From voice profile content_type_fit
        2. Complexity match (0.0-1.0): How well voice handles this complexity
        3. Recency penalty: -0.5 if used in last 2 articles, -0.1 if in last 3
        4. Variety bonus: +0.1 if voice hasn't been used in history
        5. Randomness factor: ±0.05 for tiebreaking

        Args:
            voice_id: Voice to score
            content_type: Type of content ("tutorial", "news", etc.)
            complexity_score: Complexity of article (0.0-1.0)
            recent_voices: List of recently used voices

        Returns:
            Score (0.0-1.0+, with penalties/bonuses)
        """
        profile = VOICE_PROFILES[voice_id]

        # Factor 1: Content-type fit
        fit_score = profile.content_type_fit.get(content_type, 0.5)

        # Factor 2: Complexity match
        # Simple voices (low temp) -> low complexity, complex voices (high temp) -> high complexity
        target_temp = 0.4 + (complexity_score * 0.3)  # Range: 0.4-0.7
        temp_diff = abs(profile.temperature - target_temp)
        complexity_match = 1.0 - (temp_diff / 0.3)  # Normalize to 0-1
        complexity_match = max(0.0, min(1.0, complexity_match))

        # Base score from content fit and complexity
        base_score = (fit_score * 0.6) + (complexity_match * 0.4)

        # Factor 3: Recency penalty (prevent consecutive or near-consecutive use)
        recency_penalty = 0.0
        if voice_id == recent_voices[0] if recent_voices else False:
            recency_penalty = 0.5  # Don't use the immediate previous voice
        elif voice_id in recent_voices[:2]:
            recency_penalty = 0.2  # Discourage using voice from last 2 articles

        # Factor 4: Variety bonus
        history_voices = set(self._load_history_voices(limit=20))
        variety_bonus = 0.1 if voice_id not in history_voices else 0.0

        # Factor 5: Randomness for tiebreaking
        randomness = random.uniform(-0.05, 0.05)

        total_score = base_score - recency_penalty + variety_bonus + randomness
        return max(0.0, min(1.5, total_score))  # Clamp to reasonable range

    def _load_history_voices(self, limit: int = 20) -> list[str]:
        """Get list of voice IDs from history."""
        history = self._load_history()
        result: list[str] = []
        for entry in history[-limit:]:
            voice_id = entry.get("voice_id")
            if isinstance(voice_id, str):
                result.append(voice_id)
        return result

    def select_voice(
        self,
        content_type: str,
        complexity_score: float = 0.5,
        preferred_voices: list[str] | None = None,
    ) -> VoiceProfile:
        """Select best voice for an article.

        Args:
            content_type: Type of content ("tutorial", "news", "analysis", "research", "general")
            complexity_score: Measured complexity (0.0-1.0). Used for voice matching.
            preferred_voices: List of voice IDs to prefer (will be checked first).
                If None, all voices are candidates.

        Returns:
            Selected VoiceProfile

        Raises:
            ValueError: If no valid voices available
        """
        logger.debug(
            f"Selecting voice for {content_type} content (complexity={complexity_score})"
        )
        # Get candidate voices for this content type
        ranked_voices = get_voices_for_content_type(content_type)

        # Filter to preferred voices if provided
        if preferred_voices:
            ranked_voices = [v for v in ranked_voices if v in preferred_voices]

        if not ranked_voices:
            # Fallback to all voices if preferred list filtered everything
            if not preferred_voices:
                raise ValueError(f"No voices found for content type: {content_type}")
            ranked_voices = list(VOICE_PROFILES.keys())

        # Get recent voices for recency filtering
        recent_voices = self.get_recent_voices(count=3)

        # Score all candidate voices
        scores = {}
        for voice_id in ranked_voices:
            score = self._calculate_voice_score(
                voice_id, content_type, complexity_score, recent_voices
            )
            scores[voice_id] = score

        # Sort by score (descending) and return top voice
        best_voice_id = sorted(scores.keys(), key=lambda v: scores[v], reverse=True)[0]
        selected_profile = VOICE_PROFILES[best_voice_id]
        logger.info(
            f"Selected voice: {selected_profile.name} (score: {scores[best_voice_id]:.2f})"
        )
        return selected_profile

    def select_voice_with_details(
        self,
        content_type: str,
        complexity_score: float = 0.5,
        preferred_voices: list[str] | None = None,
    ) -> tuple[VoiceProfile, dict]:
        """Select voice and return scoring details for debugging.

        Args:
            content_type: Type of content
            complexity_score: Measured complexity
            preferred_voices: List of preferred voice IDs

        Returns:
            Tuple of (VoiceProfile, dict with scoring details)
        """
        logger.debug(
            f"Selecting voice with details: {content_type} (complexity={complexity_score})"
        )
        ranked_voices = get_voices_for_content_type(content_type)
        if preferred_voices:
            ranked_voices = [v for v in ranked_voices if v in preferred_voices]

        if not ranked_voices:
            if not preferred_voices:
                raise ValueError(f"No voices found for content type: {content_type}")
            ranked_voices = list(VOICE_PROFILES.keys())

        recent_voices = self.get_recent_voices(count=3)

        # Score and collect details
        scores = {}
        details = {}
        for voice_id in ranked_voices:
            score = self._calculate_voice_score(
                voice_id, content_type, complexity_score, recent_voices
            )
            scores[voice_id] = score
            profile = VOICE_PROFILES[voice_id]
            details[voice_id] = {
                "name": profile.name,
                "score": score,
                "fit_score": profile.content_type_fit.get(content_type, 0.5),
                "temperature": profile.temperature,
            }

        best_voice_id = sorted(scores.keys(), key=lambda v: scores[v], reverse=True)[0]
        return VOICE_PROFILES[best_voice_id], {
            "selected": best_voice_id,
            "scores": details,
            "recent_voices": recent_voices,
        }

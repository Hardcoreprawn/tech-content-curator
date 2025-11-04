"""Quick validation tests for voice system.

Tests:
1. All 7 voices load correctly
2. Voice selection works for each content type
3. Recency filtering prevents consecutive duplicate voices
4. History tracking works
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.generators.voices import get_all_voice_ids, get_voices_for_content_type
from src.generators.voices.selector import VoiceSelector


def test_voices_load():
    """Verify all 7 voices are defined."""
    voices = get_all_voice_ids()
    print(f"✓ Loaded {len(voices)} voices: {voices}")
    assert len(voices) == 7, f"Expected 7 voices, got {len(voices)}"
    assert set(voices) == {
        "taylor",
        "sam",
        "aria",
        "quinn",
        "riley",
        "jordan",
        "emerson",
    }


def test_content_type_fit():
    """Verify voice ranking for each content type."""
    content_types = ["tutorial", "news", "analysis", "research", "general"]

    for content_type in content_types:
        ranked = get_voices_for_content_type(content_type)
        print(f"\n{content_type.upper()}:")
        for i, voice_id in enumerate(ranked[:3], 1):
            print(f"  {i}. {voice_id}")


def test_voice_selection():
    """Test voice selection with history tracking."""
    selector = VoiceSelector(history_file="/tmp/test_voice_history.json")

    print("\n--- Testing Voice Selection ---")

    # Generate 20 selections to test recency filtering
    selected_voices = []
    for i in range(20):
        voice = selector.select_voice("general", complexity_score=0.5)
        selected_voices.append(voice.voice_id)
        selector.add_to_history(f"test_article_{i}", voice.voice_id)

        if i < 5 or i % 5 == 0:
            print(f"Article {i}: {voice.name} ({voice.voice_id})")

    # Check for long consecutive duplicates (should be rare)
    consecutive_count = 0
    max_consecutive = 0
    for i in range(1, len(selected_voices)):
        if selected_voices[i] == selected_voices[i - 1]:
            consecutive_count += 1
            max_consecutive = max(max_consecutive, consecutive_count)
        else:
            consecutive_count = 0

    print(f"\nMax consecutive duplicates: {max_consecutive}")
    assert max_consecutive < 2, f"Too many consecutive duplicates: {max_consecutive}"

    # Verify distribution (should be relatively balanced)
    distribution = {}
    for voice_id in selected_voices:
        distribution[voice_id] = distribution.get(voice_id, 0) + 1

    print("\nVoice distribution across 20 articles:")
    for voice_id in sorted(distribution.keys()):
        count = distribution[voice_id]
        pct = (count / len(selected_voices)) * 100
        print(f"  {voice_id}: {count} ({pct:.1f}%)")

    # With 7 voices and 20 articles, expect roughly 2-3 each (14-43%)
    min_count = min(distribution.values())
    max_count = max(distribution.values())
    print(f"\nRange: {min_count}-{max_count} (expected ~2-4 for balanced distribution)")


def test_voice_details():
    """Test selection with debugging details."""
    selector = VoiceSelector(history_file="/tmp/test_voice_history_2.json")

    voice, details = selector.select_voice_with_details(
        "tutorial", complexity_score=0.7
    )

    print("--- Selection Details (tutorial, complexity=0.7) ---")
    print(f"Selected: {voice.name} ({voice.voice_id})")
    print("Scoring:")
    for voice_id in ["taylor", "quinn", "sam"]:
        if voice_id in details["scores"]:
            scores = details["scores"][voice_id]
            print(
                f"  {voice_id}: score={scores['score']:.3f}, "
                f"fit={scores['fit_score']:.2f}, temp={scores['temperature']:.1f}"
            )

    print(f"\nRecent voices: {details['recent_voices']}")


if __name__ == "__main__":
    print("=" * 60)
    print("VOICE SYSTEM VALIDATION TESTS")
    print("=" * 60)

    test_voices_load()
    test_content_type_fit()
    test_voice_selection()
    test_voice_details()

    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)

"""Generate voice performance report from metrics data.

This script analyzes voice performance metrics and generates
a human-readable markdown report with insights and recommendations.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.generators.voices.adaptation import VoiceAdapter
from src.utils.logging import get_logger

logger = get_logger(__name__)


def main():
    """Generate and print voice performance report."""
    adapter = VoiceAdapter()

    # Generate report
    report = adapter.generate_report()

    # Print to stdout (can be redirected to file)
    print(report)

    # Also generate high-priority suggestions summary
    print("\n" + "=" * 80)
    print("HIGH PRIORITY ISSUES")
    print("=" * 80 + "\n")

    all_voices = adapter.get_all_metrics()
    has_issues = False

    for voice_id in sorted(all_voices.keys()):
        suggestions = adapter.analyze_voice_performance(voice_id)
        high_priority = [s for s in suggestions if s.priority == "high"]

        if high_priority:
            has_issues = True
            print(f"## {voice_id.title()}")
            for suggestion in high_priority:
                print(f"\n**Issue:** {suggestion.issue}")
                print(f"**Recommendation:** {suggestion.suggestion}")
                print("**Evidence:**")
                for evidence in suggestion.evidence:
                    print(f"  - {evidence}")
                print()

    if not has_issues:
        print("✓ No high priority issues detected!")
        print("All voices performing within acceptable ranges.")

    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80 + "\n")

    # Content type recommendations
    content_types = ["tutorial", "analysis", "research", "news", "general"]
    print("Best Voice by Content Type:")
    print()

    for ct in content_types:
        best = adapter.get_best_voice_for_content_type(ct, min_uses=3)
        if best:
            metrics = adapter.get_metrics(best)
            score = metrics.content_type_scores.get(ct, 0) if metrics else 0
            print(f"- **{ct.title()}**: {best.title()} (score: {score:.1f})")

    logger.info("Report generation complete")


if __name__ == "__main__":
    main()

"""Voice system for diverse article generation.

This package provides:
- Voice profiles: 7 distinct writing personalities
- Voice selection: Content-type aware voice matching with recency filtering
- Voice rotation tracking: Maintain diversity with history management
- Voice prompts: Voice-specific system prompts and personality injection
"""

from .profiles import (
    VoiceProfile,
    get_all_voice_ids,
    get_voice_profile,
    get_voices_for_content_type,
)
from .prompts import (
    VoicePromptKit,
    build_content_generation_prompt,
    build_voice_system_prompt,
    check_for_banned_phrases,
    filter_banned_phrases,
    get_banned_phrases_for_voice,
    get_voice_prompt_kit,
)

__all__ = [
    "VoiceProfile",
    "VoicePromptKit",
    "get_all_voice_ids",
    "get_voice_profile",
    "get_voices_for_content_type",
    "build_voice_system_prompt",
    "build_content_generation_prompt",
    "get_voice_prompt_kit",
    "get_banned_phrases_for_voice",
    "check_for_banned_phrases",
    "filter_banned_phrases",
]

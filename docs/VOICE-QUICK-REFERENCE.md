# Voice System Quick Reference

**Phase 1 Complete**: Voice-aware article generation ready for production  
**Last Updated**: November 4, 2025

## Quick Start

### Using the Voice System

```python
from src.generators.voices import (
    build_voice_system_prompt,
    get_voice_prompt_kit,
    check_for_banned_phrases,
    filter_banned_phrases,
)

# 1. Build a system prompt for a voice
system_prompt = build_voice_system_prompt("taylor", content_type="tutorial")

# 2. Use in API call
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Write about X..."}
    ],
)

# 3. Validate output
issues = check_for_banned_phrases(response.choices[0].message.content, "taylor")
if issues:
    cleaned, replacements = filter_banned_phrases(content, "taylor")
    print(f"Cleaned {len(replacements)} banned phrases")
```

## The 7 Voices

### Quick Personality Chart

```
TAYLOR (Technical Explainer)
├─ Opening: Bold statement or scenario
├─ Style: Step-by-step, concrete examples
├─ Structure: Procedures with explanations
└─ Use: Tutorials, technical guides

SAM (Storyteller)
├─ Opening: Scene or personal anecdote
├─ Style: Narrative arcs, vivid descriptions
├─ Structure: Setup → Complication → Resolution
└─ Use: Case studies, human impact stories

ARIA (Analyst)
├─ Opening: Bold claim with backing
├─ Style: Evidence-driven, questioning
├─ Structure: Thesis → Evidence → Implications
└─ Use: Analysis, critique, deep dives

QUINN (Pragmatist)
├─ Opening: Problem statement
├─ Style: Direct, action-oriented
├─ Structure: Problem → Steps → Validation
└─ Use: How-tos, quick fixes, practical guides

RILEY (Researcher)
├─ Opening: Statement with citation
├─ Style: Academic rigor, formal
├─ Structure: Background → Methods → Findings → Limitations
└─ Use: Research summaries, literature reviews

JORDAN (Journalist)
├─ Opening: News lede
├─ Style: Urgent, clear, scannable
├─ Structure: Inverted pyramid
└─ Use: News, announcements, breaking updates

EMERSON (Enthusiast)
├─ Opening: What's exciting
├─ Style: Passionate, celebratory
├─ Structure: Problem → Solution → Opportunities
└─ Use: Launches, innovations, positive framing
```

## Common Tasks

### Get Voice Characteristics

```python
from src.generators.voices import get_voice_prompt_kit

kit = get_voice_prompt_kit("samantha")
print(kit.system_message)           # Core voice identity
print(kit.style_guidance)           # Writing style rules
print(kit.banned_phrases_warning)   # Phrases to avoid
print(kit.content_type_tweaks)      # Content-specific adjustments
```

### Check for Banned Phrases

```python
from src.generators.voices import check_for_banned_phrases, get_banned_phrases_for_voice

# See what phrases are banned for a voice
banned = get_banned_phrases_for_voice("taylor")
print(banned)  # ["Simply put", "Interestingly", ...]

# Check article for violations
issues = check_for_banned_phrases(article_text, "taylor")
for phrase, count in issues:
    print(f"Found '{phrase}' {count} time(s)")
```

### Auto-Clean Banned Phrases

```python
from src.generators.voices import filter_banned_phrases

cleaned, replacements = filter_banned_phrases(article_text, "taylor")
if replacements:
    print(f"Replaced: {replacements}")
    # Uses simple regex: "Simply put" → "In short", etc.
```

### Get Content-Type Tweaks

```python
from src.generators.voices import get_voice_prompt_kit

kit = get_voice_prompt_kit("taylor")
tutorial_guidance = kit.content_type_tweaks["tutorial"]
print(tutorial_guidance)
# Output: "For tutorials, Taylor should: - Be extremely explicit..."
```

## Integration Points

### Orchestrator Flow

```python
# 1. Select voice
from src.generators.voices.selector import VoiceSelector
voice_selector = VoiceSelector()
voice_profile = voice_selector.select_voice(
    content_type="tutorial",
    complexity_score=0.65
)

# 2. Set on item
item.voice_profile = voice_profile.voice_id

# 3. Generator automatically uses it
# (see GeneralArticleGenerator.generate_content)
```

### Generator Integration

```python
# In GeneralArticleGenerator.generate_content():

voice_id = getattr(item, "voice_profile", None)
if voice_id and voice_id != "default":
    from src.generators.voices.prompts import build_voice_system_prompt
    system_message = build_voice_system_prompt(voice_id, content_type)
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]
else:
    messages = [{"role": "user", "content": prompt}]

# Send to OpenAI
response = self.client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
    temperature=0.6,
    max_tokens=2000,
)
```

## Content Types

### Five Supported Types

```
"tutorial"   → Step-by-step guides, how-tos
"analysis"   → Deep analysis, critique, investigation  
"research"   → Research summaries, academic content
"news"       → News, announcements, breaking updates
"general"    → Everything else (default)
```

### Voice Adjustments Per Type

Each voice tweaks its approach for the content type. Examples:

**Taylor (Tutorial):** "Be extremely explicit about prerequisites, number every step clearly"

**Sam (Tutorial):** "Frame as a journey, celebrate milestones, tell mini-stories"

**Aria (Analysis):** "Lead with clear thesis, present balanced evidence, address counterarguments"

**Quinn (News):** "Lead with what changed, give action items, focus on immediate impact"

## File Locations

```
src/generators/voices/
├── __init__.py              # Public API exports
├── profiles.py              # Voice profile definitions
├── selector.py              # VoiceSelector class
├── prompt_kits_1.py         # Taylor, Sam prompt kits
├── prompt_kits_2.py         # Aria, Quinn, Riley prompt kits
├── prompt_kits_3.py         # Jordan, Emerson prompt kits
└── prompts.py               # Unified prompt system

docs/
├── PHASE-1.4-VOICE-PROMPTS.md      # Full documentation
└── VOICE-SYSTEM-IMPLEMENTATION.md  # Implementation details
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Voice not influencing article | Check item.voice_profile is set, verify system message in API call |
| Banned phrases in output | Use filter_banned_phrases() for post-generation cleanup |
| Wrong content-type tweaks | Verify detect_content_type() returns valid type |
| Import errors | Ensure voice_profile attribute exists on item |
| Performance impact | Voice system adds ~50-100 tokens to system prompt (minimal) |

## Testing Voice Output

### Blind Voice Identification Test

Generate articles on same topic with all 7 voices, then:

```python
articles = {
    "taylor.md": "You are reading...",    # Can you identify Taylor?
    "sam.md": "In 2004, a developer...",  # Can you identify Sam?
    "aria.md": "X is fundamentally...",   # Can you identify Aria?
    # etc.
}
```

Success metric: Human can correctly identify 5+ voices from writing style alone.

## Version Info

- **Phase:** 1.4 (Voice-Aware Prompts)
- **Status:** ✅ Complete and integrated
- **Python:** 3.9+ (tested and type-hinted for 3.14)
- **PEP Compliance:** 100% (PEP 8, 257, 484)
- **Type Annotations:** 100% coverage

## Related Docs

- Full implementation: [PHASE-1.4-VOICE-PROMPTS.md](PHASE-1.4-VOICE-PROMPTS.md)
- Voice system overview: [VOICE-SYSTEM-IMPLEMENTATION.md](VOICE-SYSTEM-IMPLEMENTATION.md)
- Code quality audit: [PYTHON-PEP-COMPLIANCE-AUDIT.md](PYTHON-PEP-COMPLIANCE-AUDIT.md)

---

**Need Help?**

1. Check the 7 voice personalities above
2. Review Integration Points section
3. Look at Common Tasks examples
4. Check Troubleshooting for your issue
5. Read full docs for detailed explanation

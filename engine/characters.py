"""Character voice detection and multi-voice segment parsing."""
from __future__ import annotations

import re


def detect_characters(text: str) -> list[str]:
    """Find CHARACTER: patterns in text and return sorted unique character names."""
    return sorted(set(
        m.group(1).strip()
        for m in re.finditer(r'^([A-Z][A-Z\s]{1,24}):', text, re.MULTILINE)
        if len(m.group(1).strip()) >= 2
    ))


def parse_segments(
    text: str,
    assignments: dict[str, str],
    default_voice: str,
) -> list[tuple[str, str]]:
    """Split text into (voice_name, text) segments based on character assignments."""
    segments = []
    for line in text.splitlines():
        m = re.match(r'^([A-Z][A-Z\s]{1,24}):\s*(.*)', line)
        if m and m.group(1).strip() in assignments:
            char = m.group(1).strip()
            segments.append((assignments[char], m.group(2).strip()))
        elif line.strip():
            segments.append((default_voice, line.strip()))
    return [(voice, seg_text) for voice, seg_text in segments if seg_text]

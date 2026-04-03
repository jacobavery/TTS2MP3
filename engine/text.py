"""Text processing: chunking, normalization, cleanup, and pronunciation."""

import re
from .formats import CHUNK_SIZE


def chunk_text(text: str, max_chars: int = CHUNK_SIZE) -> list[str]:
    """Split *text* into chunks <= max_chars at paragraph then sentence boundaries."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = ""

    for para in re.split(r'\n\s*\n', text):
        para = para.strip()
        if not para:
            continue
        candidate = (current + "\n\n" + para).strip() if current else para
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(para) <= max_chars:
            current = para
        else:
            for sent in re.split(r'(?<=[.!?])\s+', para):
                candidate = (current + " " + sent).strip() if current else sent
                if len(candidate) <= max_chars:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    while len(sent) > max_chars:
                        chunks.append(sent[:max_chars])
                        sent = sent[max_chars:]
                    current = sent

    if current:
        chunks.append(current)

    return chunks or [text]


def normalize_text(text: str) -> str:
    """Expand common number/date/currency patterns to spoken form before TTS."""
    # Currency: $4.99 -> "4 dollars and 99 cents"
    text = re.sub(
        r'\$(\d{1,3}(?:,\d{3})*|\d+)\.(\d{2})\b',
        lambda m: f"{m.group(1).replace(',', '')} dollars and {m.group(2)} cents",
        text,
    )
    # Currency (whole): $5 -> "5 dollars"
    text = re.sub(
        r'\$(\d{1,3}(?:,\d{3})*|\d+)\b',
        lambda m: f"{m.group(1).replace(',', '')} dollars",
        text,
    )
    # Percentages: 42% -> "42 percent"
    text = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'\1 percent', text)
    # Date ranges: 2019-2023 -> "2019 to 2023"
    text = re.sub(r'\b((?:19|20)\d{2})[–\-]((?:19|20)\d{2})\b', r'\1 to \2', text)
    # ISO dates: 2024-01-15 -> "January 15, 2024"
    _months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]

    def _iso_date(m):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12:
            return f"{_months[mo - 1]} {d}, {y}"
        return m.group(0)

    text = re.sub(
        r'\b((?:19|20)\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b',
        _iso_date, text,
    )
    # Large numbers with commas: 1,234,567 -> "1234567"
    text = re.sub(
        r'(\d{1,3}),(\d{3})',
        lambda m: m.group(0).replace(',', ''),
        text,
    )
    return text


def clean_pdf_text(text: str) -> str:
    """Remove common PDF extraction artifacts: page numbers, headers, soft hyphens."""
    from collections import Counter

    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    text = re.sub(r'^\s*\d{1,4}\s*$', '', text, flags=re.MULTILINE)
    lines = text.splitlines()
    line_counts = Counter(ln.strip() for ln in lines if 2 <= len(ln.strip()) <= 60)
    repeated = {ln for ln, cnt in line_counts.items() if cnt >= 3}
    lines = [ln for ln in lines if ln.strip() not in repeated]
    text = "\n".join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def strip_markdown(text: str) -> str:
    """Strip Markdown syntax to plain prose suitable for TTS."""
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`\n]+`', '', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,3}([^*\n]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}([^_\n]+)_{1,3}', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'^[-*_]{3,}\s*$', '\n', text, flags=re.MULTILINE)
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)
    text = re.sub(r'~~([^~]+)~~', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def clean_rtf_artifacts(text: str) -> str:
    """Remove RTF control words and markup that leaked through the parser."""
    text = re.sub(r'\{\\rtf\d[^{}]{0,200}', '', text)
    text = re.sub(
        r'\{\\(?:fonttbl|colortbl|expandedcolortbl|info|stylesheet)[^{}]*\}',
        '', text, flags=re.DOTALL,
    )
    text = re.sub(r'\{[^{}a-zA-Z0-9]*\}', '', text)
    text = re.sub(r'\\[a-zA-Z]+\d*\*? ?', '', text)
    text = re.sub(r'[\\{}]', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def apply_pronunciations(text: str, pronunciations: list[dict]) -> str:
    """Apply all pronunciation substitutions to *text* before TTS."""
    for entry in pronunciations:
        find = entry.get("find", "")
        replace = entry.get("replace", "")
        if not find:
            continue
        if entry.get("whole_word", False):
            text = re.sub(r'\b' + re.escape(find) + r'\b', replace, text)
        else:
            text = text.replace(find, replace)
    return text

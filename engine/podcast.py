"""Podcast RSS 2.0 / iTunes feed generation."""

import os


MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".m4b": "audio/mp4",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
}

AUDIO_EXTS = set(MIME_TYPES.keys())


def generate_rss(
    audio_dir: str,
    base_url: str,
    title: str = "Podcast",
    author: str = "",
    description: str = "",
) -> str:
    """Generate an RSS 2.0 / iTunes-compatible feed XML string."""
    base_url = base_url.rstrip("/") + "/"

    items = sorted(
        f for f in os.listdir(audio_dir)
        if os.path.splitext(f)[1].lower() in AUDIO_EXTS
    )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">',
        "  <channel>",
        f"    <title>{title}</title>",
        f"    <itunes:author>{author}</itunes:author>",
        f"    <description>{description}</description>",
        f"    <link>{base_url}</link>",
    ]
    for fname in items:
        stem = os.path.splitext(fname)[0]
        fpath = os.path.join(audio_dir, fname)
        size = os.path.getsize(fpath)
        url = base_url + fname
        ext = os.path.splitext(fname)[1].lower()
        mime = MIME_TYPES.get(ext, "audio/mpeg")
        lines += [
            "    <item>",
            f"      <title>{stem}</title>",
            f'      <enclosure url="{url}" length="{size}" type="{mime}"/>',
            f"      <guid>{url}</guid>",
            "    </item>",
        ]
    lines += ["  </channel>", "</rss>"]
    return "\n".join(lines)

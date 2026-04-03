"""Audiobook builder: EPUB chapter extraction and M4B assembly."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from .audio import get_audio_duration


def epub_chapters(path: str) -> list[tuple[str, str]]:
    """Return list of (title, text) for each non-empty EPUB chapter."""
    import ebooklib
    from ebooklib import epub as _epub
    from bs4 import BeautifulSoup

    book = _epub.read_epub(path, options={"ignore_ncx": True})
    chapters = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        heading = soup.find(["h1", "h2", "h3"])
        title = heading.get_text().strip() if heading else item.get_name()
        text = soup.get_text(separator="\n")
        text = "\n".join(ln for ln in text.splitlines() if ln.strip())
        if text.strip():
            chapters.append((title, text))
    return chapters


def extract_epub_cover(epub_path: str, cache_dir: str) -> str | None:
    """Return a temp file path containing the EPUB cover image, or None."""
    import ebooklib
    from ebooklib import epub as _epub

    conv_dir = os.path.join(cache_dir, "conversions")
    os.makedirs(conv_dir, exist_ok=True)

    try:
        book = _epub.read_epub(epub_path)
        for item in book.get_items():
            if (item.get_type() == ebooklib.ITEM_COVER or
                    "cover" in (item.get_name() or "").lower()):
                if item.media_type and item.media_type.startswith("image/"):
                    suffix = ".jpg" if "jpeg" in item.media_type else ".png"
                    fd, tmp = tempfile.mkstemp(suffix=suffix, dir=conv_dir)
                    with os.fdopen(fd, "wb") as f:
                        f.write(item.get_content())
                    return tmp
    except Exception:
        pass
    return None


def assemble_m4b(
    chapter_mp3s: list[str],
    chapter_titles: list[str],
    out_path: str,
):
    """Concatenate MP3 chapter files into a chapter-marked M4B."""
    tmp_dir = tempfile.mkdtemp()
    try:
        durations = [get_audio_duration(p) for p in chapter_mp3s]

        concat_file = os.path.join(tmp_dir, "concat.txt")
        with open(concat_file, "w") as f:
            for mp3 in chapter_mp3s:
                f.write(f"file '{mp3}'\n")

        meta_file = os.path.join(tmp_dir, "meta.txt")
        with open(meta_file, "w", encoding="utf-8") as f:
            f.write(";FFMETADATA1\n")
            pos = 0.0
            for title, dur in zip(chapter_titles, durations):
                start_ms = int(pos * 1000)
                end_ms = int((pos + dur) * 1000)
                f.write(
                    f"\n[CHAPTER]\nTIMEBASE=1/1000\n"
                    f"START={start_ms}\nEND={end_ms}\n"
                    f"title={title}\n"
                )
                pos += dur

        concat_mp3 = os.path.join(tmp_dir, "full.mp3")
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", concat_file, "-acodec", "copy", concat_mp3],
            capture_output=True,
        )
        if r.returncode != 0:
            raise RuntimeError(
                "MP3 concat failed: " + r.stderr.decode(errors="replace")[:300])

        r = subprocess.run(
            ["ffmpeg", "-y", "-i", concat_mp3, "-i", meta_file,
             "-map_metadata", "1", "-acodec", "aac", "-b:a", "128k",
             out_path],
            capture_output=True,
        )
        if r.returncode != 0:
            raise RuntimeError(
                "M4B assembly failed: " + r.stderr.decode(errors="replace")[:300])

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

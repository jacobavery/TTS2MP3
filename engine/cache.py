"""SHA-256 content-addressed cache for TTS synthesis results."""

import hashlib
import os


def cache_key(voice: str, text: str, rate: str, pitch: str, volume: str) -> str:
    """Generate a 24-char hex cache key from synthesis parameters."""
    blob = f"{voice}|{text}|{rate}|{pitch}|{volume}"
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


def preview_cache_path(name: str, cache_dir: str) -> str:
    return os.path.join(cache_dir, "previews", f"{name}.mp3")


def conv_cache_path(key: str, cache_dir: str) -> str:
    return os.path.join(cache_dir, "conversions", f"{key}.mp3")


def ensure_cache_dirs(cache_dir: str):
    """Create cache directory structure if it doesn't exist."""
    os.makedirs(os.path.join(cache_dir, "previews"), exist_ok=True)
    os.makedirs(os.path.join(cache_dir, "conversions"), exist_ok=True)
    os.makedirs(os.path.join(cache_dir, "jobs"), exist_ok=True)


def cache_size(cache_dir: str) -> dict:
    """Return cache statistics: {total_bytes, preview_count, conversion_count}."""
    total = 0
    preview_count = 0
    conversion_count = 0
    preview_dir = os.path.join(cache_dir, "previews")
    conv_dir = os.path.join(cache_dir, "conversions")
    for dp, _, fns in os.walk(cache_dir):
        for fn in fns:
            fp = os.path.join(dp, fn)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
            if dp == preview_dir:
                preview_count += 1
            elif dp == conv_dir:
                conversion_count += 1
    return {
        "total_bytes": total,
        "preview_count": preview_count,
        "conversion_count": conversion_count,
    }

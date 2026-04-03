"""Audio processing: ffmpeg conversion, concatenation, normalization, metadata."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from .formats import EXPORT_FORMATS


def check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def check_tesseract() -> bool:
    try:
        subprocess.run(["tesseract", "--version"], capture_output=True, timeout=3)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def get_audio_duration(path: str) -> float:
    """Return duration in seconds via ffprobe."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, timeout=10,
        )
        if r.returncode == 0:
            return float(r.stdout.decode().strip())
    except Exception:
        pass
    return 0.0


def make_silence_clip(duration_secs: float, out_path: str):
    """Generate a silent MP3 clip of *duration_secs* seconds via ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
         "-t", str(duration_secs),
         "-acodec", "libmp3lame", "-b:a", "128k",
         out_path],
        capture_output=True, check=True,
    )


def concat_audio(file_list: list[str], out_path: str, tmp_dir: str):
    """Concatenate audio files using ffmpeg concat demuxer."""
    concat_file = os.path.join(tmp_dir, "concat.txt")
    with open(concat_file, "w") as f:
        for fp in file_list:
            f.write(f"file '{fp}'\n")
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", concat_file, "-acodec", "copy", out_path],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "ffmpeg concat failed: " + result.stderr.decode(errors="replace")[:300])


def convert_format(
    in_path: str,
    out_path: str,
    fmt: str,
    quality_extra: list[str] | None = None,
    ffmpeg_available: bool = True,
):
    """Convert audio file to the target format with optional quality override."""
    native_args = EXPORT_FORMATS[fmt][1]
    base_ffmpeg_args = list(native_args or [])

    if quality_extra and base_ffmpeg_args:
        if quality_extra[0] in ("-b:a", "-q:a"):
            for flag in ("-b:a", "-q:a"):
                try:
                    idx = base_ffmpeg_args.index(flag)
                    base_ffmpeg_args.pop(idx)
                    base_ffmpeg_args.pop(idx)
                except ValueError:
                    pass
        base_ffmpeg_args = base_ffmpeg_args + quality_extra

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    needs_ffmpeg = bool(base_ffmpeg_args)

    # No conversion needed, or no ffmpeg for native MP3 with quality preset
    if not needs_ffmpeg or not ffmpeg_available:
        if os.path.abspath(in_path) != os.path.abspath(out_path):
            shutil.copy2(in_path, out_path)
    else:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", in_path] + base_ffmpeg_args + [out_path],
            capture_output=True,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, "ffmpeg", result.stderr)


def normalize_loudness(path: str, cache_dir: str) -> bool:
    """Apply loudnorm filter in-place. Returns True on success."""
    nfd, norm_tmp = tempfile.mkstemp(
        suffix=os.path.splitext(path)[1], dir=cache_dir)
    os.close(nfd)
    try:
        res = subprocess.run(
            ["ffmpeg", "-y", "-i", path,
             "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
             "-ar", "44100", norm_tmp],
            capture_output=True,
        )
        if res.returncode == 0 and os.path.getsize(norm_tmp) > 0:
            shutil.move(norm_tmp, path)
            return True
        return False
    finally:
        if os.path.isfile(norm_tmp):
            try:
                os.unlink(norm_tmp)
            except OSError:
                pass


def embed_metadata(
    out_path: str,
    title: str = "",
    author: str = "",
    cover_path: str | None = None,
):
    """Embed ID3/MP4 metadata (and optional cover art) into *out_path* in-place."""
    ext = os.path.splitext(out_path)[1].lower()
    fd, tmp = tempfile.mkstemp(suffix=ext, dir=os.path.dirname(out_path))
    os.close(fd)
    try:
        cmd = ["ffmpeg", "-y", "-i", out_path]
        if cover_path and os.path.isfile(cover_path):
            cmd += ["-i", cover_path,
                    "-map", "0:a", "-map", "1:v",
                    "-c:a", "copy", "-c:v", "mjpeg",
                    "-disposition:v", "attached_pic"]
        else:
            cmd += ["-c:a", "copy"]
        if title:
            cmd += ["-metadata", f"title={title}"]
        if author:
            cmd += ["-metadata", f"artist={author}",
                    "-metadata", f"album_artist={author}"]
        cmd.append(tmp)
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode == 0 and os.path.getsize(tmp) > 0:
            shutil.move(tmp, out_path)
    finally:
        if os.path.isfile(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass

"""Constants for audio formats, quality presets, and synthesis parameters."""

CHUNK_SIZE = 4800  # chars (~60 s of speech at 150 WPM)

WPM_ESTIMATE = 150  # approximate TTS words-per-minute at normal speed

QUALITY_PRESETS = {
    "MP3":  [("Standard (128k)", ["-b:a", "128k"]),
             ("High (192k)",     ["-b:a", "192k"]),
             ("Maximum (320k)",  ["-b:a", "320k"])],
    "WAV":  [],
    "FLAC": [],
    "AAC":  [("Standard (128k)", ["-b:a", "128k"]),
             ("High (192k)",     ["-b:a", "192k"])],
    "M4B":  [("Standard (96k)",  ["-b:a", "96k"]),
             ("High (128k)",     ["-b:a", "128k"])],
    "OGG":  [("Standard (q4)",   ["-q:a", "4"]),
             ("High (q7)",       ["-q:a", "7"])],
    "OPUS": [("Standard (96k)",  ["-b:a", "96k"]),
             ("High (128k)",     ["-b:a", "128k"]),
             ("Maximum (192k)",  ["-b:a", "192k"])],
}

PARA_PAUSE_OPTIONS = [
    ("None", 0.0),
    ("Short (0.5s)", 0.5),
    ("Medium (1s)", 1.0),
    ("Long (2s)", 2.0),
]

# (extension, ffmpeg_args) — None args means native MP3, no conversion needed
EXPORT_FORMATS = {
    "MP3":  (".mp3",  None),
    "WAV":  (".wav",  ["-acodec", "pcm_s16le"]),
    "FLAC": (".flac", ["-acodec", "flac"]),
    "AAC":  (".m4a",  ["-acodec", "aac",       "-b:a", "192k"]),
    "M4B":  (".m4b",  ["-acodec", "aac",       "-b:a", "128k"]),
    "OGG":  (".ogg",  ["-acodec", "libvorbis", "-q:a", "5"]),
    "OPUS": (".opus", ["-acodec", "libopus",   "-b:a", "128k"]),
}

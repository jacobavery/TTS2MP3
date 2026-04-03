"""Server configuration."""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CACHE_DIR = os.path.join(BASE_DIR, ".tts_cache")
JOBS_DIR = os.path.join(CACHE_DIR, "jobs")
FAVORITES_FILE = os.path.join(BASE_DIR, ".tts_favorites.json")
SETTINGS_FILE = os.path.join(BASE_DIR, ".tts_settings.json")
PRONUNCIATION_FILE = os.path.join(BASE_DIR, ".tts_pronunciations.json")
HISTORY_FILE = os.path.join(BASE_DIR, ".tts_history.json")

MAX_TEXT_LENGTH = 500_000
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_CONCURRENT_JOBS = 3
JOB_TTL_SECONDS = 3600  # 1 hour

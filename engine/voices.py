"""Voice listing, filtering, display names, and curated picks."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess

import edge_tts

STAFF_PICKS = {
    "Professional Male":   "en-US-AndrewNeural",
    "Professional Female": "en-US-AvaNeural",
    "Friendly Male":       "en-US-BrianNeural",
    "Friendly Female":     "en-US-EmmaNeural",
    "Authoritative":       "en-US-ChristopherNeural",
    "Warm & Caring":       "en-US-JennyNeural",
    "Energetic":           "en-US-RogerNeural",
    "Kid Voice":           "en-US-AnaNeural",
    "British Male":        "en-GB-RyanNeural",
    "British Female":      "en-GB-SoniaNeural",
    "Australian Male":     "en-AU-WilliamMultilingualNeural",
    "Australian Female":   "en-AU-NatashaNeural",
    "Indian Female":       "en-IN-NeerjaExpressiveNeural",
}

LANG_NAMES = {
    "af": "Afrikaans", "am": "Amharic", "ar": "Arabic", "az": "Azerbaijani",
    "bg": "Bulgarian", "bn": "Bengali", "bs": "Bosnian", "ca": "Catalan",
    "cs": "Czech", "cy": "Welsh", "da": "Danish", "de": "German",
    "el": "Greek", "en": "English", "es": "Spanish", "et": "Estonian",
    "eu": "Basque", "fa": "Persian", "fi": "Finnish", "fil": "Filipino",
    "fr": "French", "ga": "Irish", "gl": "Galician", "gu": "Gujarati",
    "he": "Hebrew", "hi": "Hindi", "hr": "Croatian", "hu": "Hungarian",
    "hy": "Armenian", "id": "Indonesian", "is": "Icelandic", "it": "Italian",
    "ja": "Japanese", "jv": "Javanese", "ka": "Georgian", "kk": "Kazakh",
    "km": "Khmer", "kn": "Kannada", "ko": "Korean", "lo": "Lao",
    "lt": "Lithuanian", "lv": "Latvian", "mk": "Macedonian", "ml": "Malayalam",
    "mn": "Mongolian", "mr": "Marathi", "ms": "Malay", "mt": "Maltese",
    "my": "Burmese", "nb": "Norwegian", "ne": "Nepali", "nl": "Dutch",
    "or": "Odia", "pa": "Punjabi", "pl": "Polish", "ps": "Pashto",
    "pt": "Portuguese", "ro": "Romanian", "ru": "Russian", "si": "Sinhala",
    "sk": "Slovak", "sl": "Slovenian", "so": "Somali", "sq": "Albanian",
    "sr": "Serbian", "su": "Sundanese", "sv": "Swedish", "sw": "Swahili",
    "ta": "Tamil", "te": "Telugu", "th": "Thai", "tr": "Turkish",
    "uk": "Ukrainian", "ur": "Urdu", "uz": "Uzbek", "vi": "Vietnamese",
    "wuu": "Wu Chinese", "yue": "Cantonese", "zh": "Chinese", "zu": "Zulu",
}


def voice_display_name(short_name: str) -> str:
    """'en-US-AndrewNeural' → 'Andrew'"""
    parts = short_name.split("-")
    if len(parts) >= 3:
        return parts[2].replace("Neural", "").replace("Multilingual", "")
    return short_name


def list_macos_voices() -> list[dict]:
    """Return list of macOS system voice dicts (Backend='macos')."""
    try:
        r = subprocess.run(["say", "-v", "?"], capture_output=True, timeout=10)
        if r.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []

    _female_hints = {
        "samantha", "victoria", "karen", "moira", "tessa", "fiona", "veena",
        "ava", "allison", "susan", "zoe", "kate", "serena", "alice", "amelie",
        "anna", "joana", "laura", "lekha", "luciana", "mariska", "mei-jia",
        "melina", "milena", "monica", "nora", "paulina", "satu", "sin-ji",
        "솔아", "kyoko", "meijia", "kanya",
    }
    voices = []
    for line in r.stdout.decode(errors="replace").splitlines():
        parts = line.split("#", 1)
        if len(parts) < 2:
            continue
        desc = parts[1].strip()
        tokens = parts[0].split()
        if len(tokens) < 2:
            continue
        locale_raw = tokens[-1]
        name = " ".join(tokens[:-1])
        locale = locale_raw.replace("_", "-")
        gender = "Female" if name.lower() in _female_hints else "Male"
        voices.append({
            "ShortName": name,
            "Locale": locale,
            "Gender": gender,
            "VoiceTag": {"VoicePersonalities": []},
            "Description": desc,
            "Backend": "macos",
        })
    return voices


async def list_edge_voices() -> list[dict]:
    """Fetch cloud voices from edge_tts and tag them with Backend='edge_tts'."""
    voices = await edge_tts.list_voices()
    for v in voices:
        v.setdefault("Backend", "edge_tts")
    return voices


async def list_all_voices(cache_dir: str | None = None) -> list[dict]:
    """Return combined list of edge_tts + macOS voices, with optional JSON caching."""
    cache_path = os.path.join(cache_dir, "_voice_list.json") if cache_dir else None

    # Try edge_tts first
    try:
        cloud = await list_edge_voices()
    except Exception:
        cloud = []
        # Fallback to cache
        if cache_path and os.path.isfile(cache_path):
            with open(cache_path) as f:
                cloud = json.load(f)

    # Save cache
    if cloud and cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(cloud, f)

    # Merge macOS voices
    macos = list_macos_voices()

    return cloud + macos


def filter_voices(
    voices: list[dict],
    search: str = "",
    language: str = "All",
    gender: str = "All",
    favorites: set[str] | None = None,
    favorites_only: bool = False,
) -> list[dict]:
    """Filter a voice list by search, language, gender, and favorites."""
    out = []
    search_lower = search.lower()
    for v in voices:
        if language != "All" and v.get("Locale") != language:
            continue
        if gender != "All" and v.get("Gender") != gender:
            continue
        if favorites_only and favorites and v["ShortName"] not in favorites:
            continue
        if search_lower:
            dname = voice_display_name(v["ShortName"]).lower()
            haystack = f"{v['ShortName']} {dname} {v.get('Gender', '')} {v.get('Locale', '')}"
            personalities = v.get("VoiceTag", {}).get("VoicePersonalities", [])
            haystack += " " + " ".join(personalities)
            if search_lower not in haystack.lower():
                continue
        out.append(v)
    return out

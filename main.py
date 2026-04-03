import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import edge_tts
import asyncio
import threading
import subprocess
import hashlib
import os
import re
import json
import shutil
import tempfile
import signal
import time
from striprtf.striprtf import rtf_to_text
import ebooklib
from ebooklib import epub as _epub
from bs4 import BeautifulSoup
try:
    import fitz  # PyMuPDF
    _HAS_FITZ = True
except (ImportError, OSError):
    _HAS_FITZ = False

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _HAS_DND = True
except ImportError:
    _HAS_DND = False

FAVORITES_FILE       = os.path.join(os.path.dirname(__file__), ".tts_favorites.json")
SETTINGS_FILE        = os.path.join(os.path.dirname(__file__), ".tts_settings.json")
PRONUNCIATION_FILE   = os.path.join(os.path.dirname(__file__), ".tts_pronunciations.json")
HISTORY_FILE         = os.path.join(os.path.dirname(__file__), ".tts_history.json")
PROJECT_EXT          = ".tts2mp3"
CACHE_DIR            = os.path.join(os.path.dirname(__file__), ".tts_cache")
VOICE_LIST_CACHE     = os.path.join(CACHE_DIR, "_voice_list.json")
MACOS_VOICE_CACHE    = os.path.join(CACHE_DIR, "_macos_voices.json")
PREVIEW_CACHE_DIR    = os.path.join(CACHE_DIR, "previews")
CONVERSION_CACHE_DIR = os.path.join(CACHE_DIR, "conversions")

CHUNK_SIZE = 4800  # chars (~60 s of speech at 150 WPM) — split long texts here

# Per-format quality presets: label → extra ffmpeg bitrate args that override defaults
QUALITY_PRESETS = {
    "MP3":  [("Standard (128k)", ["-b:a","128k"]),
             ("High (192k)",     ["-b:a","192k"]),
             ("Maximum (320k)", ["-b:a","320k"])],
    "WAV":  [],
    "FLAC": [],
    "AAC":  [("Standard (128k)", ["-b:a","128k"]),
             ("High (192k)",     ["-b:a","192k"])],
    "M4B":  [("Standard (96k)",  ["-b:a","96k"]),
             ("High (128k)",     ["-b:a","128k"])],
    "OGG":  [("Standard (q4)",   ["-q:a","4"]),
             ("High (q7)",       ["-q:a","7"])],
    "OPUS": [("Standard (96k)",  ["-b:a","96k"]),
             ("High (128k)",     ["-b:a","128k"]),
             ("Maximum (192k)", ["-b:a","192k"])],
}

PARA_PAUSE_OPTIONS = [("None", 0.0), ("Short (0.5s)", 0.5),
                      ("Medium (1s)", 1.0), ("Long (2s)", 2.0)]

os.makedirs(PREVIEW_CACHE_DIR, exist_ok=True)
os.makedirs(CONVERSION_CACHE_DIR, exist_ok=True)

# (ext, ffmpeg_args)  — None args means native MP3, no conversion
EXPORT_FORMATS = {
    "MP3":  (".mp3",  None),
    "WAV":  (".wav",  ["-acodec", "pcm_s16le"]),
    "FLAC": (".flac", ["-acodec", "flac"]),
    "AAC":  (".m4a",  ["-acodec", "aac",        "-b:a", "192k"]),
    "M4B":  (".m4b",  ["-acodec", "aac",        "-b:a", "128k"]),
    "OGG":  (".ogg",  ["-acodec", "libvorbis",  "-q:a", "5"]),
    "OPUS": (".opus", ["-acodec", "libopus",    "-b:a", "128k"]),
}

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

FONT_HEADER    = ("SF Pro Display", 20, "bold")
FONT_SUBHEADER = ("SF Pro Display", 13, "bold")
FONT_BODY      = ("SF Pro Text", 12)
FONT_SMALL     = ("SF Pro Text", 11)
FONT_MONO      = ("SF Mono", 11)
FONT_CAPTION   = ("SF Pro Text", 10)

MAX_RECENT    = 8
WPM_ESTIMATE  = 150   # approximate TTS words-per-minute at normal speed


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def voice_display_name(short_name):
    """'en-US-AndrewNeural' → 'Andrew'"""
    parts = short_name.split("-")
    if len(parts) >= 3:
        return parts[2].replace("Neural", "").replace("Multilingual", "")
    return short_name


def _set_text(widget, text):
    """Replace all content in a tk.Text widget."""
    widget.config(state="normal")
    widget.delete("1.0", "end")
    if text:
        widget.insert("1.0", text)


def _clean_rtf_artifacts(text):
    """Remove RTF control words and markup that leaked through the parser."""
    # Drop full RTF header groups: {\rtf1 ... }
    text = re.sub(r'\{\\rtf\d[^{}]{0,200}', '', text)
    # Drop font/colour/info tables and similar brace groups with control words
    text = re.sub(r'\{\\(?:fonttbl|colortbl|expandedcolortbl|info|stylesheet)[^{}]*\}', '', text, flags=re.DOTALL)
    # Drop remaining brace groups that are purely markup (no plain words inside)
    text = re.sub(r'\{[^{}a-zA-Z0-9]*\}', '', text)
    # Drop control words: \word  or  \word123
    text = re.sub(r'\\[a-zA-Z]+\d*\*? ?', '', text)
    # Drop lone backslashes and stray braces left over
    text = re.sub(r'[\\{}]', '', text)
    # Collapse excessive blank lines and trailing spaces
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _chunk_text(text, max_chars=CHUNK_SIZE):
    """Split *text* into chunks ≤ max_chars at paragraph then sentence boundaries."""
    if len(text) <= max_chars:
        return [text]

    chunks  = []
    current = ""

    for para in re.split(r'\n\s*\n', text):
        para = para.strip()
        if not para:
            continue
        candidate = (current + "\n\n" + para).strip() if current else para
        if len(candidate) <= max_chars:
            current = candidate
            continue

        # Current chunk is full — flush it
        if current:
            chunks.append(current)
            current = ""

        if len(para) <= max_chars:
            current = para
        else:
            # Para itself is oversized — split on sentence boundaries
            for sent in re.split(r'(?<=[.!?])\s+', para):
                candidate = (current + " " + sent).strip() if current else sent
                if len(candidate) <= max_chars:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    # Hard-split if a single sentence exceeds limit
                    while len(sent) > max_chars:
                        chunks.append(sent[:max_chars])
                        sent = sent[max_chars:]
                    current = sent

    if current:
        chunks.append(current)

    return chunks or [text]


def _normalize_text(text):
    """Expand common number/date/currency patterns to spoken form before TTS."""
    # Currency: $4.99 → "4 dollars and 99 cents"
    text = re.sub(
        r'\$(\d{1,3}(?:,\d{3})*|\d+)\.(\d{2})\b',
        lambda m: f"{m.group(1).replace(',','')} dollars and {m.group(2)} cents", text)
    # Currency (whole): $5 → "5 dollars"
    text = re.sub(
        r'\$(\d{1,3}(?:,\d{3})*|\d+)\b',
        lambda m: f"{m.group(1).replace(',','')} dollars", text)
    # Percentages: 42% → "42 percent"
    text = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'\1 percent', text)
    # Date ranges: 2019–2023 or 2019-2023 → "2019 to 2023"
    text = re.sub(r'\b((?:19|20)\d{2})[–\-]((?:19|20)\d{2})\b', r'\1 to \2', text)
    # ISO dates: 2024-01-15 → "January 15, 2024"
    _months = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]
    def _iso_date(m):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12:
            return f"{_months[mo-1]} {d}, {y}"
        return m.group(0)
    text = re.sub(r'\b((?:19|20)\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b',
                  _iso_date, text)
    # Large numbers with commas: 1,234,567 → "1234567" (let TTS speak it naturally)
    text = re.sub(r'(\d{1,3}),(\d{3})', lambda m: m.group(0).replace(',',''), text)
    return text


def _clean_pdf_text(text):
    """Remove common PDF extraction artifacts: page numbers, running headers, soft hyphens."""
    # Rejoin soft-hyphenated line breaks: "infor-\nmation" → "information"
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    # Strip lines that are purely a page number (optional whitespace + digits)
    text = re.sub(r'^\s*\d{1,4}\s*$', '', text, flags=re.MULTILINE)
    # Strip very short repeated lines (likely running headers/footers)
    lines = text.splitlines()
    from collections import Counter
    line_counts = Counter(ln.strip() for ln in lines if 2 <= len(ln.strip()) <= 60)
    repeated = {ln for ln, cnt in line_counts.items() if cnt >= 3}
    lines = [ln for ln in lines if ln.strip() not in repeated]
    text = "\n".join(lines)
    # Collapse runs of blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _strip_markdown(text):
    """Strip Markdown syntax to plain prose suitable for TTS."""
    # Remove fenced code blocks entirely
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`\n]+`', '', text)       # inline code
    # ATX headers: ## Title → Title
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Bold/italic
    text = re.sub(r'\*{1,3}([^*\n]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}([^_\n]+)_{1,3}', r'\1', text)
    # Links: [text](url) → text
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    # Images: ![alt](url) → alt text
    text = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', text)
    # Horizontal rules → paragraph break
    text = re.sub(r'^[-*_]{3,}\s*$', '\n', text, flags=re.MULTILINE)
    # Blockquotes
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)
    # Strikethrough
    text = re.sub(r'~~([^~]+)~~', r'\1', text)
    # Clean up excess whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _list_macos_voices():
    """Return list of macOS system voice dicts (Backend='macos')."""
    try:
        r = subprocess.run(["say", "-v", "?"], capture_output=True, timeout=10)
        if r.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []

    # Gender hints from common macOS voice names
    _female_hints = {"samantha","victoria","karen","moira","tessa","fiona","veena",
                     "ava","allison","susan","zoe","kate","serena","alice","amelie",
                     "anna","joana","laura","lekha","luciana","mariska","mei-jia",
                     "melina","milena","monica","nora","paulina","satu","sin-ji",
                     "솔아","kyoko","meijia","kanya"}
    voices = []
    for line in r.stdout.decode(errors="replace").splitlines():
        parts = line.split("#", 1)
        if len(parts) < 2:
            continue
        desc = parts[1].strip()
        tokens = parts[0].split()
        if len(tokens) < 2:
            continue
        locale_raw = tokens[-1]                       # e.g. en_US
        name       = " ".join(tokens[:-1])            # e.g. Samantha
        locale     = locale_raw.replace("_", "-")     # en-US
        gender     = "Female" if name.lower() in _female_hints else "Male"
        voices.append({
            "ShortName":    name,
            "Locale":       locale,
            "Gender":       gender,
            "VoiceTag":     {"VoicePersonalities": []},
            "Description":  desc,
            "Backend":      "macos",
        })
    return voices


def check_tesseract():
    """Return True if the tesseract CLI is available."""
    try:
        subprocess.run(["tesseract", "--version"], capture_output=True, timeout=3)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


class TTS2MP3App:
    def __init__(self, root):
        self.root = root
        self.root.title("TTS2MP3 Studio")
        self.root.geometry("1060x760")
        self.root.minsize(900, 640)

        self.all_voices      = []
        self.filtered_voices = []
        self.favorites       = self._load_favorites()
        self.settings        = self._load_settings()
        self.pronunciations  = self._load_pronunciations()
        self.output_file     = None
        self.converting      = False
        self.preview_process = None
        self.chosen_voice    = None
        self.previewing      = False
        self._preview_gen    = 0   # incremented on each new preview; threads use it to self-cancel
        self.ffmpeg          = check_ffmpeg()
        self.tesseract       = check_tesseract()
        self.fav_menu        = None   # built after voices load

        # Inline playback state
        self._player_proc   = None
        self._player_paused = False
        self._player_pos    = 0.0
        self._player_dur    = 0.0
        self._player_file   = None
        self._player_start  = 0.0
        self._player_timer  = None

        # Project / history
        self.current_project_path = None
        self._source_meta         = {}   # {title, author, cover_path} set when file is loaded

        # Watch-folder daemon
        self._watch_active = False
        self._watch_thread = None

        # Conversion timing (for time-remaining estimate)
        self._conv_start_t  = 0.0
        self._conv_n_done   = 0
        self._conv_n_total  = 0

        self.dark_mode = self.settings.get("dark_mode", False)
        self._setup_theme()
        self._build_menu()
        self._build_ui()

        self.status_var.set("Loading voices…")
        threading.Thread(target=self._load_voices_thread, daemon=True).start()

    # ── Theme ─────────────────────────────────────────────────────────

    def _setup_theme(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("aqua")
        except tk.TclError:
            self.style.theme_use("clam")
        self._apply_colors()

    def _apply_colors(self):
        if self.dark_mode:
            bg, fg, ebg    = "#1e1e1e", "#e0e0e0", "#2d2d2d"
            sel, bdr, muted = "#3a6fd8", "#3a3a3a", "#888888"
        else:
            bg, fg, ebg    = "#f5f5f7", "#1d1d1f", "#ffffff"
            sel, bdr, muted = "#0071e3", "#d2d2d7", "#86868b"

        self.colors = dict(bg=bg, fg=fg, entry_bg=ebg,
                           select_bg=sel, border=bdr, muted=muted)
        self.root.configure(bg=bg)
        s = self.style
        s.configure(".", background=bg, foreground=fg, fieldbackground=ebg)
        s.configure("TFrame", background=bg)
        s.configure("TLabel", background=bg, foreground=fg)
        s.configure("TLabelframe", background=bg, foreground=fg)
        s.configure("TLabelframe.Label", background=bg, foreground=fg, font=FONT_SMALL)
        s.configure("TNotebook", background=bg)
        s.configure("TNotebook.Tab", background=bg, foreground=fg, padding=[14, 5])
        s.map("TNotebook.Tab",
              background=[("selected", sel)],
              foreground=[("selected", "#ffffff")])
        s.configure("Accent.TButton", foreground="#ffffff", background=sel)
        s.configure("Green.TLabel",   foreground="#34c759", background=bg)
        s.configure("Blue.TLabel",    foreground=sel,       background=bg)
        s.configure("Muted.TLabel",   foreground=muted,     background=bg)
        s.configure("Warn.TLabel",    foreground="#ff9f0a", background=bg)
        s.configure("Header.TLabel",  background=bg, foreground=fg,    font=FONT_HEADER)
        s.configure("Sub.TLabel",     background=bg, foreground=muted, font=FONT_SMALL)
        s.configure("Section.TLabel", background=bg, foreground=fg,    font=FONT_SUBHEADER)

    def _toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self.settings["dark_mode"] = self.dark_mode
        self._save_settings()
        self._apply_colors()
        c = self.colors
        self.text_area.configure(bg=c["entry_bg"], fg=c["fg"], insertbackground=c["fg"])
        self.voice_list.configure(bg=c["entry_bg"], fg=c["fg"],
                                  selectbackground=c["select_bg"])

    # ── Menu ──────────────────────────────────────────────────────────

    def _build_menu(self):
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)

        # App
        app_m = tk.Menu(self.menubar, tearoff=0)
        app_m.add_command(label="Toggle Dark Mode", command=self._toggle_dark_mode,
                          accelerator="Cmd+D")
        app_m.add_separator()
        app_m.add_command(label="Quit", command=self.root.quit, accelerator="Cmd+Q")
        self.menubar.add_cascade(label="TTS2MP3", menu=app_m)

        # File
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.file_menu.add_command(label="New Project",      command=self._new_project)
        self.file_menu.add_command(label="Open Project…",    command=self._open_project,
                                   accelerator="Cmd+O")
        self.file_menu.add_command(label="Save Project",     command=self._save_project,
                                   accelerator="Cmd+S")
        self.file_menu.add_command(label="Save Project As…", command=self._save_project_as,
                                   accelerator="Cmd+Shift+S")
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Open Text File…",  command=self._open_and_load)
        self.recent_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label="Recent Files", menu=self.recent_menu)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Convert to Audio", command=self.convert,
                                   accelerator="Cmd+R")
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Play Output",         command=self.play_output)
        self.file_menu.add_command(label="Show in Finder",      command=self.reveal_in_finder)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Conversion History…", command=self._open_history_dialog)
        self.menubar.add_cascade(label="File", menu=self.file_menu)

        # Voices — populated after load
        self.voices_menu = tk.Menu(self.menubar, tearoff=0)
        self.voices_menu.add_command(label="(loading voices…)", state="disabled")
        self.menubar.add_cascade(label="Voices", menu=self.voices_menu)

        # Edit
        edit_m = tk.Menu(self.menubar, tearoff=0)
        edit_m.add_command(label="Find & Replace…",     command=self._open_find_replace,
                           accelerator="Cmd+H")
        edit_m.add_separator()
        edit_m.add_command(label="Paste from Clipboard", command=self._paste_clipboard,
                           accelerator="Cmd+V")
        edit_m.add_command(label="Copy All Text",        command=self._copy_text,
                           accelerator="Cmd+Shift+C")
        edit_m.add_separator()
        edit_m.add_command(label="Clear Text",  command=self._clear_text)
        edit_m.add_command(label="Select All",
                           command=lambda: self.text_area.tag_add("sel", "1.0", "end"))
        self.menubar.add_cascade(label="Edit", menu=edit_m)

        # Tools
        tools_m = tk.Menu(self.menubar, tearoff=0)
        tools_m.add_command(label="RTF to Text Converter…",
                            command=self._open_rtf_converter,
                            accelerator="Cmd+T")
        tools_m.add_command(label="EPUB to Text Converter…",
                            command=self._open_epub_converter,
                            accelerator="Cmd+E")
        tools_m.add_command(label="PDF to Text Converter…",
                            command=self._open_pdf_converter,
                            accelerator="Cmd+P")
        tools_m.add_separator()
        tools_m.add_command(label="Batch Text to Audio…",
                            command=self._open_batch_audio_converter,
                            accelerator="Cmd+B")
        tools_m.add_command(label="Audiobook Converter (M4B)…",
                            command=self._open_audiobook_converter)
        tools_m.add_separator()
        tools_m.add_command(label="Pronunciation Dictionary…",
                            command=self._open_pronunciation_editor)
        tools_m.add_command(label="Voice Comparison…",
                            command=self._open_voice_compare)
        tools_m.add_command(label="Character Voices…",
                            command=self._open_character_voices)
        tools_m.add_separator()
        tools_m.add_command(label="Watch Folder…",
                            command=self._open_watch_folder)
        tools_m.add_command(label="Generate Podcast RSS…",
                            command=self._open_podcast_rss)
        self.menubar.add_cascade(label="Tools", menu=tools_m)

        # Bindings
        self.root.bind("<Command-d>",       lambda e: self._toggle_dark_mode())
        self.root.bind("<Command-q>",       lambda e: self.root.quit())
        self.root.bind("<Command-o>",         lambda e: self._open_project())
        self.root.bind("<Command-s>",         lambda e: self._save_project())
        self.root.bind("<Command-Shift-s>",   lambda e: self._save_project_as())
        self.root.bind("<Command-r>",         lambda e: self.convert())
        self.root.bind("<Command-h>",         lambda e: self._open_find_replace())
        self.root.bind("<Command-Shift-c>",   lambda e: self._copy_text())
        self.root.bind("<Command-t>",         lambda e: self._open_rtf_converter())
        self.root.bind("<Command-e>",         lambda e: self._open_epub_converter())
        self.root.bind("<Command-p>",         lambda e: self._open_pdf_converter())
        self.root.bind("<Command-b>",         lambda e: self._open_batch_audio_converter())

        self._rebuild_recent_menu()

    # ── Voices Menu (built after voice load) ──────────────────────────

    def _rebuild_voices_menu(self):
        m = self.voices_menu
        m.delete(0, "end")

        # Staff Picks
        picks_sub = tk.Menu(m, tearoff=0)
        for label, vid in STAFF_PICKS.items():
            dname = voice_display_name(vid)
            picks_sub.add_command(
                label=f"{label}  —  {dname}",
                command=lambda v=vid: self._select_voice_by_id(v))
        m.add_cascade(label="Staff Picks", menu=picks_sub)

        # Favorites (dynamic)
        self.fav_menu = tk.Menu(m, tearoff=0)
        m.add_cascade(label="Favorites", menu=self.fav_menu)
        self._rebuild_fav_menu()

        m.add_separator()

        # Group by language code → locale → voices
        lang_map = {}
        for v in self.all_voices:
            lc = v["Locale"].split("-")[0]
            lang_map.setdefault(lc, {}).setdefault(v["Locale"], []).append(v)

        for lc in sorted(lang_map):
            lang_name  = LANG_NAMES.get(lc, lc.upper())
            locales    = lang_map[lc]
            total      = sum(len(vs) for vs in locales.values())
            lang_sub   = tk.Menu(m, tearoff=0)

            for locale in sorted(locales):
                voices = sorted(locales[locale], key=lambda x: x["ShortName"])
                if len(locales) == 1:
                    # Single locale — voices directly in lang_sub
                    for v in voices:
                        lang_sub.add_command(
                            label=self._voice_menu_label(v),
                            command=lambda vid=v["ShortName"]: self._select_voice_by_id(vid))
                else:
                    # Sub-menu per locale
                    locale_sub = tk.Menu(lang_sub, tearoff=0)
                    for v in voices:
                        locale_sub.add_command(
                            label=self._voice_menu_label(v),
                            command=lambda vid=v["ShortName"]: self._select_voice_by_id(vid))
                    lang_sub.add_cascade(label=locale, menu=locale_sub)

            m.add_cascade(label=f"{lang_name}  ({total})", menu=lang_sub)

    def _voice_menu_label(self, v):
        dname  = voice_display_name(v["ShortName"])
        gchar  = v["Gender"][0]
        traits = ", ".join(v.get("VoiceTag", {}).get("VoicePersonalities", [])[:2])
        return f"{dname} ({gchar})  {traits}"

    def _rebuild_fav_menu(self):
        if self.fav_menu is None:
            return
        self.fav_menu.delete(0, "end")
        if not self.favorites:
            self.fav_menu.add_command(label="(no favorites yet)", state="disabled")
            return
        for fid in self.favorites:
            self.fav_menu.add_command(
                label=f"{voice_display_name(fid)}  —  {fid}",
                command=lambda v=fid: self._select_voice_by_id(v))

    def _select_voice_by_id(self, voice_id):
        raw = self.voice_search.get()
        if raw and raw != "Search voices…":
            self.voice_search.set("")
        self.lang_filter.set("All")
        self.gender_filter.set("All")
        self.fav_only.set(False)
        self._filter_voices()
        for i, v in enumerate(self.filtered_voices):
            if v["ShortName"] == voice_id:
                self.voice_list.selection_clear(0, "end")
                self.voice_list.selection_set(i)
                self.voice_list.see(i)
                self._on_voice_click(None)
                return

    # ── Recent Files ──────────────────────────────────────────────────

    def _rebuild_recent_menu(self):
        self.recent_menu.delete(0, "end")
        recents = self.settings.get("recent_files", [])
        if not recents:
            self.recent_menu.add_command(label="(none)", state="disabled")
            return
        for path in recents:
            self.recent_menu.add_command(
                label=os.path.basename(path),
                command=lambda p=path: self._load_file(p))
        self.recent_menu.add_separator()
        self.recent_menu.add_command(label="Clear Recent", command=self._clear_recent)

    def _add_recent(self, path):
        recents = self.settings.get("recent_files", [])
        if path in recents:
            recents.remove(path)
        recents.insert(0, path)
        self.settings["recent_files"] = recents[:MAX_RECENT]
        self._save_settings()
        self._rebuild_recent_menu()

    def _clear_recent(self):
        self.settings["recent_files"] = []
        self._save_settings()
        self._rebuild_recent_menu()

    # ── Main UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=(16, 12, 16, 8))
        outer.pack(fill="both", expand=True)

        # Header
        hdr = ttk.Frame(outer)
        hdr.pack(fill="x", pady=(0, 10))
        ttk.Label(hdr, text="TTS2MP3 Studio", style="Header.TLabel").pack(side="left")
        self.voice_count_var = tk.StringVar(value="Loading voices…")
        ttk.Label(hdr, textvariable=self.voice_count_var, style="Sub.TLabel").pack(
            side="left", padx=(12, 0), anchor="s", pady=(0, 3))

        # Bottom bar is packed first so it always reserves space before the panes expand
        self._build_bottom_bar(outer)

        # 2-pane
        panes = ttk.PanedWindow(outer, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(0, 8))
        left  = ttk.Frame(panes, padding=(0, 0, 8, 0))
        right = ttk.Frame(panes, padding=(8, 0, 0, 0))
        panes.add(left,  weight=2)
        panes.add(right, weight=3)

        self._build_voice_panel(left)
        self._build_content_panel(right)

    # ── Voice Panel ───────────────────────────────────────────────────

    def _build_voice_panel(self, parent):
        ttk.Label(parent, text="Voice", style="Section.TLabel").pack(anchor="w", pady=(0, 6))

        # Quick pick
        prow = ttk.Frame(parent)
        prow.pack(fill="x", pady=(0, 6))
        ttk.Label(prow, text="Quick pick:", font=FONT_SMALL).pack(side="left")
        self.picks_combo = ttk.Combobox(prow, values=list(STAFF_PICKS.keys()),
                                        width=22, state="readonly", font=FONT_SMALL)
        self.picks_combo.pack(side="left", padx=(6, 0))
        self.picks_combo.bind("<<ComboboxSelected>>", self._select_staff_pick)

        # Search
        self.voice_search = tk.StringVar()
        self.voice_search.trace_add("write", lambda *_: self._filter_voices())
        search_entry = ttk.Entry(parent, textvariable=self.voice_search, font=FONT_SMALL)
        search_entry.pack(fill="x", pady=(0, 4))
        self._add_placeholder(search_entry, "Search voices…")

        # Filters
        frow = ttk.Frame(parent)
        frow.pack(fill="x", pady=(0, 6))
        self.lang_filter = ttk.Combobox(frow, width=10, state="readonly", font=FONT_CAPTION)
        self.lang_filter.set("All")
        self.lang_filter.bind("<<ComboboxSelected>>", lambda e: self._filter_voices())
        self.lang_filter.pack(side="left", padx=(0, 6))

        self.gender_filter = ttk.Combobox(frow, values=["All", "Female", "Male"],
                                          width=7, state="readonly", font=FONT_CAPTION)
        self.gender_filter.set("All")
        self.gender_filter.bind("<<ComboboxSelected>>", lambda e: self._filter_voices())
        self.gender_filter.pack(side="left", padx=(0, 6))

        self.fav_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(frow, text="Favorites only", variable=self.fav_only,
                        command=self._filter_voices).pack(side="left")

        # List
        lf = ttk.Frame(parent)
        lf.pack(fill="both", expand=True, pady=(0, 6))
        sb = ttk.Scrollbar(lf)
        sb.pack(side="right", fill="y")
        self.voice_list = tk.Listbox(
            lf, yscrollcommand=sb.set, font=FONT_MONO, selectmode="browse",
            bg=self.colors["entry_bg"], fg=self.colors["fg"],
            selectbackground=self.colors["select_bg"],
            activestyle="none", borderwidth=0, highlightthickness=1,
            highlightcolor=self.colors["border"],
        )
        self.voice_list.pack(fill="both", expand=True)
        sb.config(command=self.voice_list.yview)
        self.voice_list.bind("<<ListboxSelect>>", self._on_voice_click)

        # Chosen voice status
        self.chosen_label = ttk.Label(parent, text="No voice selected",
                                      style="Muted.TLabel", font=FONT_BODY)
        self.chosen_label.pack(anchor="w", pady=(0, 6))

        # Buttons row 1
        r1 = ttk.Frame(parent)
        r1.pack(fill="x", pady=(0, 4))
        self.use_voice_btn = ttk.Button(r1, text="Use This Voice",
                                        command=self._commit_voice, style="Accent.TButton")
        self.use_voice_btn.pack(side="left", padx=(0, 6))
        self.stop_btn = ttk.Button(r1, text="Stop Preview",
                                   command=self.stop_preview, state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 6))
        self.fav_btn = ttk.Button(r1, text="★ Favorite", command=self.toggle_favorite)
        self.fav_btn.pack(side="right")

        # Buttons row 2 — cache
        r2 = ttk.Frame(parent)
        r2.pack(fill="x")
        self.dl_btn = ttk.Button(r2, text="Download All Favorites",
                                 command=self._download_all_favorites)
        self.dl_btn.pack(side="left", padx=(0, 6))
        ttk.Button(r2, text="Clear Cache", command=self._clear_cache).pack(side="left")
        self.cache_label = ttk.Label(r2, text="", style="Muted.TLabel", font=FONT_CAPTION)
        self.cache_label.pack(side="right")
        self.root.after(200, self._update_cache_size_label)

    # ── Content Panel ─────────────────────────────────────────────────

    def _build_content_panel(self, parent):
        ttk.Label(parent, text="Text", style="Section.TLabel").pack(anchor="w", pady=(0, 6))

        # File row
        fr = ttk.Frame(parent)
        fr.pack(fill="x", pady=(0, 6))
        ttk.Button(fr, text="Open File…", command=self._open_and_load).pack(side="left")
        ttk.Button(fr, text="Paste",      command=self._paste_clipboard).pack(side="left", padx=(4, 0))
        self.file_label = ttk.Label(fr, text="No file loaded",
                                    style="Muted.TLabel", font=FONT_CAPTION)
        self.file_label.pack(side="left", padx=(8, 0))
        ttk.Button(fr, text="Clear", command=self._clear_text).pack(side="right")
        ttk.Button(fr, text="Copy",  command=self._copy_text).pack(side="right", padx=(0, 4))

        # Text area
        tf = ttk.Frame(parent)
        tf.pack(fill="both", expand=True, pady=(0, 4))
        ts = ttk.Scrollbar(tf)
        ts.pack(side="right", fill="y")
        self.text_area = tk.Text(
            tf, wrap="word", font=FONT_BODY, yscrollcommand=ts.set,
            borderwidth=0, highlightthickness=1, highlightcolor=self.colors["border"],
            bg=self.colors["entry_bg"], fg=self.colors["fg"],
            insertbackground=self.colors["fg"], padx=10, pady=10,
        )
        self.text_area.pack(fill="both", expand=True)
        ts.config(command=self.text_area.yview)
        self.text_area.bind("<KeyRelease>", lambda e: self._update_word_count())

        # Stats + font size
        stats_row = ttk.Frame(parent)
        stats_row.pack(fill="x", pady=(0, 10))
        self.word_count_var = tk.StringVar(value="0 words  |  0 chars  |  ~0s")
        ttk.Label(stats_row, textvariable=self.word_count_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(side="left")

        self.font_size_var = tk.IntVar(value=self.settings.get("font_size", 12))
        ttk.Label(stats_row, text="A", font=FONT_CAPTION,
                  style="Muted.TLabel").pack(side="right", padx=(0, 2))
        ttk.Button(stats_row, text="+", width=2,
                   command=self._font_size_up).pack(side="right")
        ttk.Button(stats_row, text="−", width=2,
                   command=self._font_size_down).pack(side="right", padx=(0, 2))
        self._apply_font_size()

        # Settings
        ttk.Label(parent, text="Settings", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        sg = ttk.Frame(parent)
        sg.pack(fill="x", pady=(0, 8))
        self.speed_var  = tk.IntVar(value=self.settings.get("speed",  0))
        self.pitch_var  = tk.IntVar(value=self.settings.get("pitch",  0))
        self.volume_var = tk.IntVar(value=self.settings.get("volume", 0))
        self._build_slider(sg, "Speed",  self.speed_var,  "%",  0)
        self._build_slider(sg, "Pitch",  self.pitch_var,  "Hz", 1)
        self._build_slider(sg, "Volume", self.volume_var, "%",  2)
        ttk.Button(sg, text="Reset All", command=self._reset_sliders).grid(
            row=3, column=1, sticky="e", pady=(4, 0))

        # Output
        ttk.Label(parent, text="Output", style="Section.TLabel").pack(anchor="w", pady=(0, 6))

        fmt_row = ttk.Frame(parent)
        fmt_row.pack(fill="x", pady=(0, 4))
        ttk.Label(fmt_row, text="Format:", font=FONT_SMALL).pack(side="left")
        fmt_values = list(EXPORT_FORMATS.keys()) if self.ffmpeg else ["MP3"]
        self.format_var = tk.StringVar(value=self.settings.get("export_format", "MP3"))
        fmt_cb = ttk.Combobox(fmt_row, textvariable=self.format_var,
                              values=fmt_values, width=6, state="readonly", font=FONT_SMALL)
        fmt_cb.pack(side="left", padx=(4, 8))
        fmt_cb.bind("<<ComboboxSelected>>", self._on_format_change)

        ttk.Label(fmt_row, text="Quality:", font=FONT_SMALL).pack(side="left")
        self.quality_var = tk.StringVar(value=self.settings.get("quality", ""))
        self.quality_cb  = ttk.Combobox(fmt_row, textvariable=self.quality_var,
                                         width=16, state="readonly", font=FONT_SMALL)
        self.quality_cb.pack(side="left", padx=(4, 0))
        self._refresh_quality_options()

        if not self.ffmpeg:
            ttk.Label(fmt_row, text="Install ffmpeg to enable WAV/FLAC/AAC/OGG/OPUS/M4B",
                      style="Muted.TLabel", font=FONT_CAPTION).pack(side="left", padx=(8, 0))

        # Processing options
        proc_lf = ttk.LabelFrame(parent, text="Processing", padding=(8, 4))
        proc_lf.pack(fill="x", pady=(0, 4))

        pr1 = ttk.Frame(proc_lf)
        pr1.pack(fill="x", pady=(0, 2))
        self.normalize_text_var  = tk.BooleanVar(value=self.settings.get("normalize_text", True))
        self.normalize_audio_var = tk.BooleanVar(value=self.settings.get("normalize_audio", False))
        self.clean_pdf_var       = tk.BooleanVar(value=self.settings.get("clean_pdf", True))
        ttk.Checkbutton(pr1, text="Normalize text (numbers/dates/currency)",
                        variable=self.normalize_text_var,
                        command=self._save_proc_settings).pack(side="left")
        ttk.Checkbutton(pr1, text="Normalize audio (loudnorm)",
                        variable=self.normalize_audio_var,
                        command=self._save_proc_settings).pack(side="left", padx=(16, 0))

        pr2 = ttk.Frame(proc_lf)
        pr2.pack(fill="x")
        ttk.Checkbutton(pr2, text="Clean PDF artifacts",
                        variable=self.clean_pdf_var,
                        command=self._save_proc_settings).pack(side="left")
        ttk.Label(pr2, text="Paragraph pause:", font=FONT_SMALL).pack(side="left", padx=(16, 4))
        pause_labels = [p[0] for p in PARA_PAUSE_OPTIONS]
        self.para_pause_var = tk.StringVar(
            value=self.settings.get("para_pause", "Short (0.5s)"))
        ttk.Combobox(pr2, textvariable=self.para_pause_var,
                     values=pause_labels, width=14, state="readonly",
                     font=FONT_SMALL).pack(side="left")
        self.para_pause_var.trace_add("write", lambda *_: self._save_proc_settings())

        path_row = ttk.Frame(parent)
        path_row.pack(fill="x", pady=(0, 4))
        ttk.Label(path_row, text="Save to:", font=FONT_SMALL).pack(side="left")
        self.output_path = tk.StringVar()
        ttk.Entry(path_row, textvariable=self.output_path, font=FONT_SMALL).pack(
            side="left", fill="x", expand=True, padx=6)
        ttk.Button(path_row, text="Browse…", command=self.browse_output).pack(side="left")

        post_row = ttk.Frame(parent)
        post_row.pack(fill="x", pady=(4, 0))
        self.play_btn   = ttk.Button(post_row, text="Open in App",
                                     command=self.play_output, state="disabled")
        self.play_btn.pack(side="left", padx=(0, 6))
        self.reveal_btn = ttk.Button(post_row, text="Show in Finder",
                                     command=self.reveal_in_finder, state="disabled")
        self.reveal_btn.pack(side="left")

        # ── Inline playback bar ──────────────────────────────────────
        pb_lf = ttk.LabelFrame(parent, text="Playback", padding=(6, 4))
        pb_lf.pack(fill="x", pady=(6, 0))

        pb_ctrl = ttk.Frame(pb_lf)
        pb_ctrl.pack(fill="x", pady=(0, 4))

        self.play_pause_btn = ttk.Button(pb_ctrl, text="▶  Play",
                                         command=self._toggle_playback, state="disabled")
        self.play_pause_btn.pack(side="left", padx=(0, 4))
        ttk.Button(pb_ctrl, text="⏹", width=3,
                   command=self._stop_playback).pack(side="left", padx=(0, 8))

        self.playback_time_var = tk.StringVar(value="—")
        ttk.Label(pb_ctrl, textvariable=self.playback_time_var,
                  font=FONT_SMALL, style="Muted.TLabel", width=13).pack(side="left")

        self.playback_pos_var = tk.DoubleVar(value=0)
        self.playback_seek_scale = ttk.Scale(
            pb_lf, variable=self.playback_pos_var, from_=0, to=100, orient="horizontal")
        self.playback_seek_scale.pack(fill="x")
        self.playback_seek_scale.bind(
            "<ButtonRelease-1>",
            lambda e: self._on_seek(self.playback_pos_var.get()))

        # DnD on text area (if tkinterdnd2 available)
        if _HAS_DND:
            try:
                self.text_area.drop_target_register(DND_FILES)
                self.text_area.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

    def _build_slider(self, parent, label, var, unit, row):
        ttk.Label(parent, text=f"{label}:", width=7, font=FONT_SMALL).grid(
            row=row, column=0, sticky="w", pady=2)
        val_lbl = ttk.Label(parent, text=f"+0{unit}", width=6, font=FONT_SMALL)
        scale = ttk.Scale(parent, from_=-50, to=50, variable=var, orient="horizontal")
        scale.grid(row=row, column=1, sticky="ew", padx=(0, 6), pady=2)
        val_lbl.grid(row=row, column=2, pady=2)
        scale.configure(command=lambda v, l=val_lbl, u=unit: l.configure(
            text=f"{int(float(v)):+d}{u}"))
        ttk.Button(parent, text="Reset", width=5,
                   command=lambda: var.set(0)).grid(row=row, column=3, padx=(4, 0), pady=2)
        parent.columnconfigure(1, weight=1)

    def _reset_sliders(self):
        self.speed_var.set(0)
        self.pitch_var.set(0)
        self.volume_var.set(0)

    def _on_format_change(self, _=None):
        fmt  = self.format_var.get()
        ext  = EXPORT_FORMATS[fmt][0]
        path = self.output_path.get()
        if path:
            self.output_path.set(os.path.splitext(path)[0] + ext)
        self.settings["export_format"] = fmt
        self._save_settings()
        if hasattr(self, "quality_cb"):
            self._refresh_quality_options()

    # ── Bottom Bar ────────────────────────────────────────────────────

    def _build_bottom_bar(self, parent):
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(4, 0))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(bar, textvariable=self.status_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(side="left")

        self.convert_btn = ttk.Button(bar, text="Convert to Audio",
                                      command=self.convert, style="Accent.TButton")
        self.convert_btn.pack(side="right")

        self.pct_label = ttk.Label(bar, text="", width=5,
                                   style="Muted.TLabel", font=FONT_SMALL)
        self.pct_label.pack(side="right", padx=(0, 6))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(bar, variable=self.progress_var,
                                            maximum=100, length=200)
        self.progress_bar.pack(side="right", padx=(0, 4))

    # ── Utility helpers ───────────────────────────────────────────────

    @staticmethod
    def _add_placeholder(entry, text):
        def on_in(_):
            if entry.get() == text:
                entry.delete(0, "end")
        def on_out(_):
            if not entry.get():
                entry.insert(0, text)
        entry.insert(0, text)
        entry.bind("<FocusIn>",  on_in)
        entry.bind("<FocusOut>", on_out)

    def _paste_clipboard(self):
        try:
            self.text_area.insert("insert", self.root.clipboard_get())
            self._update_word_count()
        except tk.TclError:
            pass

    def _copy_text(self):
        text = self.text_area.get("1.0", "end").strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status_var.set("Copied to clipboard")

    def _update_progress(self, pct):
        self.progress_var.set(pct)
        self.pct_label.config(text=f"{int(pct)}%")

    def _clear_progress(self):
        self.progress_var.set(0)
        self.pct_label.config(text="")

    # ── Voice Loading ─────────────────────────────────────────────────

    def _load_voices_thread(self):
        offline = False
        # ── online edge-tts voices ────────────────────────────────────
        try:
            voices = run_async(edge_tts.list_voices())
            for v in voices:
                v.setdefault("Backend", "edge_tts")
            voices.sort(key=lambda v: v["ShortName"])
            self.all_voices = voices
            self._save_voice_list_cache()
        except Exception:
            cached = self._load_voice_list_cache()
            if cached:
                for v in cached:
                    v.setdefault("Backend", "edge_tts")
                self.all_voices = cached
                offline = True
            else:
                self.all_voices = []
                offline = True

        # ── macOS offline voices (always merged in) ───────────────────
        mac_voices = self._load_macos_voices_cached()
        if not mac_voices:
            mac_voices = _list_macos_voices()
            if mac_voices:
                try:
                    with open(MACOS_VOICE_CACHE, "w") as f:
                        json.dump(mac_voices, f)
                except Exception:
                    pass
        # Avoid duplicating by short name
        existing_names = {v["ShortName"] for v in self.all_voices}
        self.all_voices += [v for v in mac_voices if v["ShortName"] not in existing_names]

        if not self.all_voices:
            self.root.after(0, lambda: self.status_var.set(
                "No voices available — check internet or macOS say voices."))
            return

        locales = sorted(set(v["Locale"] for v in self.all_voices))
        self.root.after(0, lambda: self._voices_loaded(locales, offline))

    def _load_macos_voices_cached(self):
        try:
            with open(MACOS_VOICE_CACHE) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _voices_loaded(self, locales, offline=False):
        self.lang_filter["values"] = ["All"] + locales
        self._filter_voices()
        n_tts = sum(1 for v in self.all_voices if v.get("Backend") != "macos")
        n_mac = sum(1 for v in self.all_voices if v.get("Backend") == "macos")
        n     = len(self.all_voices)
        status_parts = [f"{n_tts} online" if n_tts else "", f"{n_mac} offline" if n_mac else ""]
        detail = "  (" + ", ".join(p for p in status_parts if p) + ")"
        self.voice_count_var.set(f"{n} voices{detail}")
        self.status_var.set(f"Ready — {n} voices{detail}")
        self._update_cache_size_label()
        self._rebuild_voices_menu()

        last = self.settings.get("last_voice", "en-US-AndrewNeural")
        for i, v in enumerate(self.filtered_voices):
            if v["ShortName"] == last:
                self.voice_list.selection_set(i)
                self.voice_list.see(i)
                self.chosen_voice = v
                self._update_chosen_label(v)
                break

    def _filter_voices(self):
        if not hasattr(self, "lang_filter"):
            return
        raw    = self.voice_search.get()
        search = "" if raw in ("", "Search voices…") else raw.lower()
        lang   = self.lang_filter.get()
        gender = self.gender_filter.get()
        favs   = self.fav_only.get()

        out = []
        for v in self.all_voices:
            if lang != "All" and v["Locale"] != lang:
                continue
            if gender != "All" and v["Gender"] != gender:
                continue
            if favs and v["ShortName"] not in self.favorites:
                continue
            if search:
                dname    = voice_display_name(v["ShortName"]).lower()
                haystack = f"{v['ShortName']} {dname} {v['Gender']} {v['Locale']}".lower()
                haystack += " " + " ".join(
                    v.get("VoiceTag", {}).get("VoicePersonalities", [])).lower()
                if search not in haystack:
                    continue
            out.append(v)

        self.filtered_voices = out
        self.voice_list.delete(0, "end")
        for v in out:
            name   = v["ShortName"]
            dname  = voice_display_name(name)
            locale = v["Locale"]
            gchar  = v["Gender"][0]
            traits = ", ".join(v.get("VoiceTag", {}).get("VoicePersonalities", [])[:2])
            fav    = " \u2605" if name in self.favorites else ""
            cached = " \u2601" if self._is_preview_cached(name) else ""
            backend = "☁" if v.get("Backend", "edge_tts") == "edge_tts" else "⊕"
            self.voice_list.insert("end",
                f"{backend} {dname:<13} {locale:<9} {gchar}  {traits}{fav}{cached}")

    def _get_selected_voice(self):
        sel = self.voice_list.curselection()
        if not sel:
            messagebox.showinfo("No Voice", "Select a voice first.")
            return None
        return self.filtered_voices[sel[0]]

    def _update_chosen_label(self, voice):
        dname  = voice_display_name(voice["ShortName"])
        traits = ", ".join(voice.get("VoiceTag", {}).get("VoicePersonalities", [])[:3])
        self.chosen_label.config(
            text=f"\u2713  {dname}  ({voice['ShortName']}, {voice['Gender']}, {traits})",
            style="Green.TLabel")

    def _select_staff_pick(self, _):
        vid = STAFF_PICKS.get(self.picks_combo.get())
        if vid:
            self._select_voice_by_id(vid)

    def _on_voice_click(self, _):
        sel = self.voice_list.curselection()
        if not sel:
            return
        voice = self.filtered_voices[sel[0]]
        if self.previewing:
            self.stop_preview()

        dname = voice_display_name(voice["ShortName"])
        self.chosen_label.config(text=f"Previewing {dname}…", style="Blue.TLabel")

        text = self.text_area.get("1.0", "end").strip()
        if not text:
            text = "Hello! This is a preview of this voice. How does it sound?"
        preview_text = text[:200]

        self._preview_gen += 1
        my_gen = self._preview_gen

        self.previewing = True
        self.stop_btn.config(state="normal")
        self.status_var.set(f"Previewing {voice['ShortName']}…")

        vname       = voice["ShortName"]
        cached_path = self._preview_cache_path(vname)
        custom      = (self.speed_var.get() != 0 or self.pitch_var.get() != 0
                       or self.volume_var.get() != 0)

        v_backend = voice.get("Backend", "edge_tts")

        def do_preview():
            tmp = None
            try:
                if os.path.isfile(cached_path) and not custom:
                    play = cached_path
                else:
                    t = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                    t.close()
                    tmp = t.name
                    rate  = f"{self.speed_var.get():+d}%"
                    pitch = f"{self.pitch_var.get():+d}Hz"
                    vol   = f"{self.volume_var.get():+d}%"
                    if v_backend == "macos":
                        self._synthesize_macos(preview_text, vname, tmp,
                                               rate=rate, pitch=pitch, volume=vol)
                    else:
                        run_async(edge_tts.Communicate(
                            preview_text, vname,
                            rate=rate, pitch=pitch, volume=vol,
                        ).save(tmp))
                    play = tmp

                # Another voice was selected while we were downloading — don't play
                if my_gen != self._preview_gen:
                    return

                self.preview_process = subprocess.Popen(["afplay", play])
                self.preview_process.wait()
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Preview error: {e}"))
            finally:
                if tmp:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
                if my_gen == self._preview_gen:
                    self.root.after(0, self._preview_done)

        threading.Thread(target=do_preview, daemon=True).start()

    def _commit_voice(self):
        voice = self._get_selected_voice()
        if not voice:
            return
        self.chosen_voice = voice
        self._update_chosen_label(voice)
        self.status_var.set(f"Voice set: {voice['ShortName']}")
        self.settings["last_voice"] = voice["ShortName"]
        self._save_settings()

    def stop_preview(self):
        self.previewing = False
        if self.preview_process:
            try:
                self.preview_process.terminate()
            except OSError:
                pass
            self.preview_process = None
        self._preview_done()

    def _preview_done(self):
        self.previewing = False
        self.stop_btn.config(state="disabled")
        if not self.converting:
            self.status_var.set(
                f"Voice set: {self.chosen_voice['ShortName']}" if self.chosen_voice else "Ready")

    # ── Favorites ─────────────────────────────────────────────────────

    def toggle_favorite(self):
        voice = self._get_selected_voice()
        if not voice:
            return
        name = voice["ShortName"]
        if name in self.favorites:
            self.favorites.remove(name)
        else:
            self.favorites.append(name)
            if not self._is_preview_cached(name):
                self.status_var.set(f"Caching {name} for offline…")
                self._auto_cache_favorite(name)
        self._save_favorites()
        self._filter_voices()
        self._update_cache_size_label()
        self._rebuild_fav_menu()

    def _load_favorites(self):
        try:
            with open(FAVORITES_FILE) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_favorites(self):
        with open(FAVORITES_FILE, "w") as f:
            json.dump(self.favorites, f)

    def _load_settings(self):
        try:
            with open(SETTINGS_FILE) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_settings(self):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self.settings, f)

    # ── Cache ─────────────────────────────────────────────────────────

    def _cache_key(self, voice, text, rate, pitch, volume):
        blob = f"{voice}|{text}|{rate}|{pitch}|{volume}"
        return hashlib.sha256(blob.encode()).hexdigest()[:24]

    def _preview_cache_path(self, name):
        return os.path.join(PREVIEW_CACHE_DIR, f"{name}.mp3")

    def _conv_cache_path(self, key):
        return os.path.join(CONVERSION_CACHE_DIR, f"{key}.mp3")

    def _is_preview_cached(self, name):
        return os.path.isfile(self._preview_cache_path(name))

    def _cache_preview(self, name):
        path = self._preview_cache_path(name)
        if not os.path.isfile(path):
            run_async(edge_tts.Communicate(
                "Hello! This is a preview of this voice. How does it sound?", name
            ).save(path))
        return path

    def _auto_cache_favorite(self, name):
        def go():
            try:
                self._cache_preview(name)
                self.root.after(0, lambda: (self._filter_voices(),
                                            self._update_cache_size_label()))
            except Exception:
                pass
        threading.Thread(target=go, daemon=True).start()

    def _download_all_favorites(self):
        if not self.favorites:
            messagebox.showinfo("No Favorites", "Favorite some voices first.")
            return
        self.dl_btn.config(state="disabled")
        total = len(self.favorites)

        def go():
            done = failed = 0
            for name in list(self.favorites):
                try:
                    self._cache_preview(name)
                except Exception:
                    failed += 1
                done += 1
                pct = int(done / total * 100)
                self.root.after(0, self._update_progress, pct)
                self.root.after(0, lambda d=done, t=total: self.status_var.set(
                    f"Downloading voices… {d}/{t}"))

            def done_cb():
                self.dl_btn.config(state="normal")
                self._filter_voices()
                self._update_cache_size_label()
                self._clear_progress()
                msg = f"Downloaded {done - failed}/{total} previews."
                if failed:
                    msg += f"  ({failed} failed)"
                self.status_var.set(msg)
            self.root.after(0, done_cb)

        threading.Thread(target=go, daemon=True).start()

    def _update_cache_size_label(self):
        total = count = 0
        for dp, _, fns in os.walk(CACHE_DIR):
            for fn in fns:
                total += os.path.getsize(os.path.join(dp, fn))
                if dp == PREVIEW_CACHE_DIR:
                    count += 1
        sz = (f"{total/(1024*1024):.1f} MB" if total >= 1024*1024
              else f"{total/1024:.0f} KB")
        self.cache_label.config(text=f"{count}/{len(self.favorites)} cached  |  {sz}")

    def _clear_cache(self):
        if not messagebox.askyesno("Clear Cache",
                                   "Delete all cached previews and conversions?"):
            return
        shutil.rmtree(CACHE_DIR, ignore_errors=True)
        os.makedirs(PREVIEW_CACHE_DIR, exist_ok=True)
        os.makedirs(CONVERSION_CACHE_DIR, exist_ok=True)
        self._filter_voices()
        self._update_cache_size_label()
        self.status_var.set("Cache cleared")

    def _save_voice_list_cache(self):
        try:
            with open(VOICE_LIST_CACHE, "w") as f:
                json.dump(self.all_voices, f)
        except Exception:
            pass

    def _load_voice_list_cache(self):
        try:
            with open(VOICE_LIST_CACHE) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    # ── RTF to Text Tool ──────────────────────────────────────────────

    def _open_rtf_converter(self):
        """Open a standalone RTF → plain-text converter dialog."""
        win = tk.Toplevel(self.root)
        win.title("RTF to Text Converter")
        win.geometry("780x560")
        win.minsize(600, 400)
        win.transient(self.root)
        bg = self.colors["bg"]
        win.configure(bg=bg)

        # ── top controls ──
        ctrl = ttk.Frame(win, padding=(12, 10, 12, 6))
        ctrl.pack(fill="x")

        ttk.Label(ctrl, text="RTF to Text Converter",
                  style="Section.TLabel").pack(side="left")

        btn_frame = ttk.Frame(ctrl)
        btn_frame.pack(side="right")

        load_btn   = ttk.Button(btn_frame, text="Add RTF File…")
        load_btn.pack(side="left", padx=(0, 6))
        batch_btn  = ttk.Button(btn_frame, text="Batch Add Files…")
        batch_btn.pack(side="left", padx=(0, 6))
        clear_b    = ttk.Button(btn_frame, text="Clear")
        clear_b.pack(side="left", padx=(0, 6))

        # ── file queue list ──
        queue_frame = ttk.LabelFrame(win, text="Files", padding=6)
        queue_frame.pack(fill="x", padx=12, pady=(0, 6))

        queue_sb = ttk.Scrollbar(queue_frame, orient="vertical")
        queue_sb.pack(side="right", fill="y")
        file_list = tk.Listbox(
            queue_frame, height=5, font=FONT_MONO,
            yscrollcommand=queue_sb.set, selectmode="extended",
            bg=self.colors["entry_bg"], fg=self.colors["fg"],
            selectbackground=self.colors["select_bg"],
            activestyle="none", borderwidth=0, highlightthickness=1,
            highlightcolor=self.colors["border"],
        )
        file_list.pack(fill="x", expand=True)
        queue_sb.config(command=file_list.yview)

        remove_btn = ttk.Button(queue_frame, text="Remove Selected",
                                command=lambda: self._rtf_remove_selected(file_list))
        remove_btn.pack(anchor="e", pady=(4, 0))

        # ── paned output area ──
        pane = ttk.PanedWindow(win, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        left_f  = ttk.LabelFrame(pane, text="RTF Source",  padding=4)
        right_f = ttk.LabelFrame(pane, text="Plain Text",  padding=4)
        pane.add(left_f,  weight=1)
        pane.add(right_f, weight=1)

        rtf_sb  = ttk.Scrollbar(left_f)
        rtf_sb.pack(side="right", fill="y")
        rtf_box = tk.Text(
            left_f, wrap="word", font=FONT_MONO, state="disabled",
            yscrollcommand=rtf_sb.set, borderwidth=0, highlightthickness=0,
            bg=self.colors["entry_bg"], fg=self.colors["muted"],
            insertbackground=self.colors["fg"], padx=6, pady=6,
        )
        rtf_box.pack(fill="both", expand=True)
        rtf_sb.config(command=rtf_box.yview)

        txt_sb  = ttk.Scrollbar(right_f)
        txt_sb.pack(side="right", fill="y")
        txt_box = tk.Text(
            right_f, wrap="word", font=FONT_BODY,
            yscrollcommand=txt_sb.set, borderwidth=0, highlightthickness=0,
            bg=self.colors["entry_bg"], fg=self.colors["fg"],
            insertbackground=self.colors["fg"], padx=6, pady=6,
        )
        txt_box.pack(fill="both", expand=True)
        txt_sb.config(command=txt_box.yview)

        # ── bottom action bar ──
        bot = ttk.Frame(win, padding=(12, 4, 12, 10))
        bot.pack(fill="x")

        status_var = tk.StringVar(value="Add one or more RTF files to get started.")
        ttk.Label(bot, textvariable=status_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(side="left")

        use_btn  = ttk.Button(bot, text="Load into TTS Editor",
                              style="Accent.TButton")
        use_btn.pack(side="right")
        save_btn = ttk.Button(bot, text="Save as .txt…")
        save_btn.pack(side="right", padx=(0, 6))
        conv_btn = ttk.Button(bot, text="Convert Selected")
        conv_btn.pack(side="right", padx=(0, 6))

        # ── state shared by callbacks ──
        file_paths = []   # parallel to file_list entries
        converted  = {}   # path → plain text

        def add_files(paths):
            for p in paths:
                if p not in file_paths:
                    file_paths.append(p)
                    file_list.insert("end", os.path.basename(p))
            if file_paths:
                status_var.set(f"{len(file_paths)} file(s) queued.")

        def on_load():
            paths = filedialog.askopenfilenames(
                parent=win,
                title="Select RTF File(s)",
                filetypes=[("RTF Files", "*.rtf"), ("All Files", "*.*")],
            )
            if paths:
                add_files(paths)

        def on_batch():
            folder = filedialog.askdirectory(parent=win,
                                             title="Select folder to scan for .rtf files")
            if not folder:
                return
            found = [os.path.join(r, f)
                     for r, _, fs in os.walk(folder)
                     for f in fs if f.lower().endswith(".rtf")]
            if found:
                add_files(found)
                status_var.set(f"Found {len(found)} RTF file(s) in folder.")
            else:
                status_var.set("No .rtf files found in that folder.")

        def on_clear():
            file_list.delete(0, "end")
            file_paths.clear()
            converted.clear()
            _set_text(rtf_box, "")
            _set_text(txt_box, "")
            status_var.set("Cleared.")

        def on_convert_selected():
            sel = file_list.curselection()
            targets = [file_paths[i] for i in sel] if sel else file_paths
            if not targets:
                status_var.set("No files to convert.")
                return
            errors = []
            for path in targets:
                try:
                    plain = self._rtf_file_to_text(path)
                    converted[path] = plain
                except Exception as e:
                    errors.append(f"{os.path.basename(path)}: {e}")

            # Show first converted result in the panels
            first = targets[0]
            if first in converted:
                raw = self._read_raw(first)
                _set_text(rtf_box, raw)
                _set_text(txt_box, converted[first])

            if errors:
                status_var.set(f"Done with {len(errors)} error(s): {errors[0]}")
            else:
                status_var.set(
                    f"Converted {len(targets)} file(s). "
                    "Select a file in the list to preview it.")

        def on_list_select(event):
            sel = file_list.curselection()
            if not sel:
                return
            path = file_paths[sel[0]]
            try:
                raw = self._read_raw(path)
                _set_text(rtf_box, raw)
            except Exception:
                _set_text(rtf_box, "(could not read file)")
            if path in converted:
                _set_text(txt_box, converted[path])
            else:
                _set_text(txt_box, "(not yet converted — click Convert Selected)")

        def on_save():
            sel  = file_list.curselection()
            path = file_paths[sel[0]] if sel else (file_paths[0] if file_paths else None)
            if not path or path not in converted:
                messagebox.showinfo("Nothing to Save",
                                    "Convert a file first, then save.",
                                    parent=win)
                return
            default = os.path.splitext(path)[0] + ".txt"
            out = filedialog.asksaveasfilename(
                parent=win,
                initialfile=os.path.basename(default),
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            )
            if out:
                with open(out, "w", encoding="utf-8") as f:
                    f.write(converted[path])
                status_var.set(f"Saved: {os.path.basename(out)}")

        def on_use_in_editor():
            sel  = file_list.curselection()
            path = file_paths[sel[0]] if sel else (file_paths[0] if file_paths else None)
            if not path:
                messagebox.showinfo("No File Selected",
                                    "Select a file in the list first.",
                                    parent=win)
                return
            if path not in converted:
                # Auto-convert on the way in
                try:
                    converted[path] = self._rtf_file_to_text(path)
                except Exception as e:
                    messagebox.showerror("Conversion Error", str(e), parent=win)
                    return
            self.text_area.delete("1.0", "end")
            self.text_area.insert("1.0", converted[path])
            self._update_word_count()
            self.file_label.config(text=os.path.basename(path))
            self.status_var.set(f"Loaded from RTF: {os.path.basename(path)}")
            self._add_recent(path)
            win.destroy()

        # ── wire up buttons ──
        load_btn.config(command=on_load)
        batch_btn.config(command=on_batch)
        clear_b.config(command=on_clear)
        conv_btn.config(command=on_convert_selected)
        save_btn.config(command=on_save)
        use_btn.config(command=on_use_in_editor)
        file_list.bind("<<ListboxSelect>>", on_list_select)

        # Allow dragging RTF files onto the file list (macOS)
        try:
            file_list.drop_target_register("DND_Files")  # type: ignore
            file_list.dnd_bind("<<Drop>>",
                               lambda e: add_files(win.tk.splitlist(e.data)))
        except Exception:
            pass  # tkinterdnd2 not installed — silent fallback

    @staticmethod
    def _rtf_remove_selected(file_list):
        for i in reversed(file_list.curselection()):
            file_list.delete(i)

    @staticmethod
    def _rtf_file_to_text(path):
        """Read an RTF file and return stripped plain text.

        Strategy:
          1. macOS textutil  — handles Apple-generated RTF (cocoartf) perfectly.
          2. striprtf        — cross-platform fallback.
          3. _clean_rtf_artifacts — scrubs any control words that slipped through.
        """
        # ── 1. textutil (macOS built-in, handles cocoartf perfectly) ──
        try:
            result = subprocess.run(
                ["textutil", "-convert", "txt", "-stdout", path],
                capture_output=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout:
                text = result.stdout.decode("utf-8", errors="replace")
                return _clean_rtf_artifacts(text)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass  # Not macOS or timed out — fall through

        # ── 2. striprtf fallback ───────────────────────────────────────
        with open(path, "rb") as f:
            raw = f.read()
        try:
            decoded = raw.decode("utf-8")
        except UnicodeDecodeError:
            decoded = raw.decode("latin-1")
        text = rtf_to_text(decoded)

        # ── 3. Scrub any leaked RTF artifacts ─────────────────────────
        text = _clean_rtf_artifacts(text)
        return text.encode("utf-8", errors="replace").decode("utf-8")

    @staticmethod
    def _read_raw(path):
        """Return raw file content as a string for display purposes."""
        with open(path, "rb") as f:
            raw = f.read()
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1")

    # ── EPUB extraction ───────────────────────────────────────────────

    @staticmethod
    def _epub_file_to_text(path):
        """Extract plain text from an EPUB file, preserving chapter order."""
        book   = _epub.read_epub(path, options={"ignore_ncx": True})
        parts  = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup  = BeautifulSoup(item.get_content(), "html.parser")
            # Remove script / style noise
            for tag in soup(["script", "style"]):
                tag.decompose()
            chunk = soup.get_text(separator="\n")
            chunk = "\n".join(line for line in chunk.splitlines() if line.strip())
            if chunk:
                parts.append(chunk)
        text = "\n\n".join(parts)
        return text.encode("utf-8", errors="replace").decode("utf-8").strip()

    @staticmethod
    def _epub_metadata(path):
        """Return {title, author, chapters} dict for display."""
        book     = _epub.read_epub(path, options={"ignore_ncx": True})
        title    = book.get_metadata("DC", "title")
        author   = book.get_metadata("DC", "creator")
        chapters = [item.get_name()
                    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]
        return {
            "title":    title[0][0]  if title  else "Unknown",
            "author":   author[0][0] if author else "Unknown",
            "chapters": chapters,
        }

    # ── PDF extraction ────────────────────────────────────────────────

    @staticmethod
    def _pdf_file_to_text(path):
        """Extract plain text from a PDF using PyMuPDF."""
        if not _HAS_FITZ:
            raise RuntimeError("PDF support requires PyMuPDF (pip install PyMuPDF)")
        doc   = fitz.open(path)
        parts = []
        for page in doc:
            text = page.get_text("text")
            text = "\n".join(line for line in text.splitlines() if line.strip())
            if text:
                parts.append(text)
        doc.close()
        text = "\n\n".join(parts)
        return text.encode("utf-8", errors="replace").decode("utf-8").strip()

    @staticmethod
    def _pdf_metadata(path):
        """Return {title, author, pages} dict for display."""
        if not _HAS_FITZ:
            return {"title": os.path.basename(path), "author": "Unknown", "pages": 0}
        doc  = fitz.open(path)
        meta = doc.metadata or {}
        pages = doc.page_count
        doc.close()
        return {
            "title":  meta.get("title")  or os.path.basename(path),
            "author": meta.get("author") or "Unknown",
            "pages":  pages,
        }

    # ── EPUB Converter Tool ───────────────────────────────────────────

    def _open_epub_converter(self):
        """Standalone EPUB → plain-text converter dialog."""
        self._open_doc_converter(
            title        = "EPUB to Text Converter",
            filetypes    = [("EPUB Books", "*.epub"), ("All Files", "*.*")],
            ext          = ".epub",
            extract_fn   = self._epub_file_to_text,
            meta_fn      = self._epub_metadata,
            meta_fmt     = lambda m: (
                f"Title: {m['title']}  |  Author: {m['author']}  "
                f"|  {len(m['chapters'])} chapter(s)"
            ),
            raw_label    = "EPUB Contents (chapters)",
            raw_fn       = lambda p: "\n".join(
                self._epub_metadata(p)["chapters"]),
        )

    # ── PDF Converter Tool ────────────────────────────────────────────

    def _open_pdf_converter(self):
        """Standalone PDF → plain-text converter with batch export."""
        win = tk.Toplevel(self.root)
        win.title("PDF to Text Converter")
        win.geometry("860x660")
        win.minsize(680, 500)
        win.transient(self.root)
        win.configure(bg=self.colors["bg"])

        # ── header ────────────────────────────────────────────────────
        ctrl = ttk.Frame(win, padding=(12, 10, 12, 6))
        ctrl.pack(fill="x")
        ttk.Label(ctrl, text="PDF to Text Converter",
                  style="Section.TLabel").pack(side="left")

        btn_f = ttk.Frame(ctrl)
        btn_f.pack(side="right")
        add_btn   = ttk.Button(btn_f, text="Add PDF File…")
        add_btn.pack(side="left", padx=(0, 6))
        scan_btn  = ttk.Button(btn_f, text="Scan Folder…")
        scan_btn.pack(side="left", padx=(0, 6))
        clear_btn = ttk.Button(btn_f, text="Clear All")
        clear_btn.pack(side="left")

        # ── file queue ────────────────────────────────────────────────
        queue_lf = ttk.LabelFrame(win, text="PDF Queue", padding=6)
        queue_lf.pack(fill="x", padx=12, pady=(0, 6))

        q_sb = ttk.Scrollbar(queue_lf, orient="vertical")
        q_sb.pack(side="right", fill="y")
        file_list = tk.Listbox(
            queue_lf, height=5, font=FONT_MONO,
            yscrollcommand=q_sb.set, selectmode="extended",
            bg=self.colors["entry_bg"], fg=self.colors["fg"],
            selectbackground=self.colors["select_bg"],
            activestyle="none", borderwidth=0, highlightthickness=1,
            highlightcolor=self.colors["border"],
        )
        file_list.pack(fill="x", expand=True)
        q_sb.config(command=file_list.yview)

        meta_var = tk.StringVar(value="")
        ttk.Label(queue_lf, textvariable=meta_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(anchor="w", pady=(4, 0))

        ttk.Button(queue_lf, text="Remove Selected",
                   command=lambda: self._rtf_remove_selected(file_list)
                   ).pack(anchor="e", pady=(4, 0))

        # ── batch export controls ─────────────────────────────────────
        batch_lf = ttk.LabelFrame(win, text="Batch Export", padding=8)
        batch_lf.pack(fill="x", padx=12, pady=(0, 6))

        # Output folder row
        frow = ttk.Frame(batch_lf)
        frow.pack(fill="x", pady=(0, 6))
        ttk.Label(frow, text="Output folder:", font=FONT_SMALL).pack(side="left")
        out_folder_var = tk.StringVar(value="Same folder as each PDF")
        out_folder_entry = ttk.Entry(frow, textvariable=out_folder_var,
                                     font=FONT_SMALL, state="readonly")
        out_folder_entry.pack(side="left", fill="x", expand=True, padx=6)

        def choose_folder():
            folder = filedialog.askdirectory(parent=win,
                                             title="Choose output folder for .txt files")
            if folder:
                out_folder_var.set(folder)

        def reset_folder():
            out_folder_var.set("Same folder as each PDF")

        ttk.Button(frow, text="Browse…", command=choose_folder).pack(side="left")
        ttk.Button(frow, text="Reset",   command=reset_folder).pack(side="left", padx=(4, 0))

        # Batch progress row
        prog_row = ttk.Frame(batch_lf)
        prog_row.pack(fill="x", pady=(0, 4))

        batch_progress_var = tk.DoubleVar(value=0)
        batch_pbar = ttk.Progressbar(prog_row, variable=batch_progress_var,
                                     maximum=100, length=300)
        batch_pbar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        batch_pct_var = tk.StringVar(value="")
        ttk.Label(prog_row, textvariable=batch_pct_var,
                  width=5, font=FONT_SMALL).pack(side="left")

        # Batch action buttons
        bact_row = ttk.Frame(batch_lf)
        bact_row.pack(fill="x")
        batch_export_btn = ttk.Button(bact_row, text="Batch Export All → .txt",
                                      style="Accent.TButton")
        batch_export_btn.pack(side="left", padx=(0, 8))
        batch_sel_btn = ttk.Button(bact_row, text="Export Selected → .txt")
        batch_sel_btn.pack(side="left")
        batch_status_var = tk.StringVar(value="Queue PDFs above, then click Batch Export.")
        ttk.Label(bact_row, textvariable=batch_status_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(side="left", padx=(12, 0))

        # ── preview panes ─────────────────────────────────────────────
        pane = ttk.PanedWindow(win, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        left_f  = ttk.LabelFrame(pane, text="PDF Info",       padding=4)
        right_f = ttk.LabelFrame(pane, text="Extracted Text", padding=4)
        pane.add(left_f,  weight=1)
        pane.add(right_f, weight=2)

        l_sb = ttk.Scrollbar(left_f)
        l_sb.pack(side="right", fill="y")
        src_box = tk.Text(
            left_f, wrap="word", font=FONT_MONO, state="disabled",
            yscrollcommand=l_sb.set, borderwidth=0, highlightthickness=0,
            bg=self.colors["entry_bg"], fg=self.colors["muted"],
            padx=6, pady=6,
        )
        src_box.pack(fill="both", expand=True)
        l_sb.config(command=src_box.yview)

        r_sb = ttk.Scrollbar(right_f)
        r_sb.pack(side="right", fill="y")
        txt_box = tk.Text(
            right_f, wrap="word", font=FONT_BODY,
            yscrollcommand=r_sb.set, borderwidth=0, highlightthickness=0,
            bg=self.colors["entry_bg"], fg=self.colors["fg"],
            insertbackground=self.colors["fg"], padx=6, pady=6,
        )
        txt_box.pack(fill="both", expand=True)
        r_sb.config(command=txt_box.yview)

        # ── single-file bottom bar ────────────────────────────────────
        bot = ttk.Frame(win, padding=(12, 4, 12, 10))
        bot.pack(fill="x")
        single_status_var = tk.StringVar(value="Add PDF files to begin.")
        ttk.Label(bot, textvariable=single_status_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(side="left")
        use_btn    = ttk.Button(bot, text="Load into TTS Editor",
                                style="Accent.TButton")
        use_btn.pack(side="right")
        save_one_btn = ttk.Button(bot, text="Save Selected as .txt…")
        save_one_btn.pack(side="right", padx=(0, 6))
        conv_btn   = ttk.Button(bot, text="Preview Selected")
        conv_btn.pack(side="right", padx=(0, 6))

        # ── state ─────────────────────────────────────────────────────
        file_paths = []
        converted  = {}   # path → plain text

        # ── helpers ───────────────────────────────────────────────────
        def add_files(paths):
            for p in paths:
                if p not in file_paths:
                    file_paths.append(p)
                    file_list.insert("end", os.path.basename(p))
            if file_paths:
                single_status_var.set(f"{len(file_paths)} PDF(s) queued.")

        def resolve_output_path(src_path):
            """Return the .txt output path for a given PDF."""
            base = os.path.splitext(os.path.basename(src_path))[0] + ".txt"
            folder = out_folder_var.get()
            if folder == "Same folder as each PDF":
                folder = os.path.dirname(src_path)
            return os.path.join(folder, base)

        def on_add():
            paths = filedialog.askopenfilenames(
                parent=win, title="Select PDF File(s)",
                filetypes=[("PDF Documents", "*.pdf"), ("All Files", "*.*")])
            if paths:
                add_files(paths)

        def on_scan():
            folder = filedialog.askdirectory(parent=win,
                                             title="Scan folder for PDF files")
            if not folder:
                return
            found = [os.path.join(r, f)
                     for r, _, fs in os.walk(folder)
                     for f in fs if f.lower().endswith(".pdf")]
            if found:
                add_files(found)
                single_status_var.set(
                    f"Found {len(found)} PDF(s) in folder.")
            else:
                single_status_var.set("No PDF files found in that folder.")

        def on_clear():
            file_list.delete(0, "end")
            file_paths.clear()
            converted.clear()
            _set_text(src_box, ""); src_box.config(state="disabled")
            _set_text(txt_box, "")
            meta_var.set("")
            batch_progress_var.set(0)
            batch_pct_var.set("")
            single_status_var.set("Cleared.")
            batch_status_var.set("Queue PDFs above, then click Batch Export.")

        def on_list_select(_event):
            sel = file_list.curselection()
            if not sel:
                return
            path = file_paths[sel[0]]
            try:
                meta = self._pdf_metadata(path)
                meta_var.set(
                    f"Title: {meta['title']}  |  Author: {meta['author']}"
                    f"  |  {meta['pages']} page(s)")
                info = "\n".join(f"{k}: {v}" for k, v in meta.items())
                _set_text(src_box, info)
                src_box.config(state="disabled")
            except Exception as err:
                _set_text(src_box, f"(could not read: {err})")
                src_box.config(state="disabled")
            if path in converted:
                _set_text(txt_box, converted[path])
            else:
                _set_text(txt_box, "(not yet extracted — click Preview Selected)")

        def on_preview_selected():
            sel     = file_list.curselection()
            targets = [file_paths[i] for i in sel] if sel else list(file_paths)
            if not targets:
                single_status_var.set("No files selected.")
                return
            conv_btn.config(state="disabled")
            single_status_var.set(f"Extracting {len(targets)} file(s)…")

            def bg():
                errors = []
                for p in targets:
                    try:
                        converted[p] = self._pdf_file_to_text(p)
                    except Exception as err:
                        errors.append(f"{os.path.basename(p)}: {err}")

                def done():
                    first = next((p for p in targets if p in converted), None)
                    if first:
                        _set_text(txt_box, converted[first])
                    conv_btn.config(state="normal")
                    single_status_var.set(
                        f"Done.{f'  {len(errors)} error(s).' if errors else ''}")
                win.after(0, done)
            threading.Thread(target=bg, daemon=True).start()

        def on_save_one():
            sel  = file_list.curselection()
            path = (file_paths[sel[0]] if sel
                    else (file_paths[0] if file_paths else None))
            if not path or path not in converted:
                messagebox.showinfo("Nothing to Save",
                                    "Preview a file first, then save.",
                                    parent=win)
                return
            default = os.path.splitext(path)[0] + ".txt"
            out = filedialog.asksaveasfilename(
                parent=win,
                initialfile=os.path.basename(default),
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
            if out:
                with open(out, "w", encoding="utf-8") as f:
                    f.write(converted[path])
                single_status_var.set(f"Saved: {os.path.basename(out)}")

        def on_use_in_editor():
            sel  = file_list.curselection()
            path = (file_paths[sel[0]] if sel
                    else (file_paths[0] if file_paths else None))
            if not path:
                messagebox.showinfo("No File Selected",
                                    "Select a file in the list first.",
                                    parent=win)
                return
            if path not in converted:
                try:
                    converted[path] = self._pdf_file_to_text(path)
                except Exception as err:
                    messagebox.showerror("Extraction Error", str(err), parent=win)
                    return
            self.text_area.delete("1.0", "end")
            self.text_area.insert("1.0", converted[path])
            self._update_word_count()
            self.file_label.config(text=os.path.basename(path))
            self.status_var.set(f"Loaded: {os.path.basename(path)}")
            self._add_recent(path)
            win.destroy()

        def _run_batch_export(targets):
            """Background thread: convert each PDF and write a .txt file."""
            total   = len(targets)
            saved   = []
            errors  = []

            for i, path in enumerate(targets, start=1):
                base = os.path.basename(path)
                win.after(0, lambda b=base, n=i, t=total:
                           batch_status_var.set(f"Exporting {n}/{t}: {b}"))

                try:
                    text   = self._pdf_file_to_text(path)
                    converted[path] = text
                    out    = resolve_output_path(path)
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    with open(out, "w", encoding="utf-8") as f:
                        f.write(text)
                    saved.append(out)
                except Exception as err:
                    errors.append(f"{base}: {err}")

                pct = int(i / total * 100)
                win.after(0, lambda p=pct: (
                    batch_progress_var.set(p),
                    batch_pct_var.set(f"{p}%")))

            def done():
                batch_export_btn.config(state="normal")
                batch_sel_btn.config(state="normal")
                # Refresh list display to show any selection
                if file_list.curselection():
                    on_list_select(None)

                if errors:
                    summary = (f"Exported {len(saved)}/{total} files.\n\n"
                               "Errors:\n" + "\n".join(errors))
                    messagebox.showwarning("Batch Export Complete", summary,
                                           parent=win)
                    batch_status_var.set(
                        f"Done — {len(saved)} exported, {len(errors)} error(s).")
                else:
                    batch_status_var.set(
                        f"All {len(saved)} file(s) exported successfully.")
                    # Show where files landed
                    folder = out_folder_var.get()
                    if folder == "Same folder as each PDF":
                        folder = os.path.dirname(targets[0])
                    if messagebox.askyesno(
                            "Open Output Folder",
                            f"Exported {len(saved)} .txt file(s).\n\n"
                            f"Open output folder in Finder?",
                            parent=win):
                        subprocess.Popen(["open", folder])

            win.after(0, done)

        def on_batch_export(selected_only=False):
            if selected_only:
                sel     = file_list.curselection()
                targets = [file_paths[i] for i in sel]
                if not targets:
                    batch_status_var.set("No files selected.")
                    return
            else:
                targets = list(file_paths)
                if not targets:
                    batch_status_var.set("No files queued.")
                    return

            batch_export_btn.config(state="disabled")
            batch_sel_btn.config(state="disabled")
            batch_progress_var.set(0)
            batch_pct_var.set("0%")
            threading.Thread(
                target=_run_batch_export, args=(targets,), daemon=True).start()

        # ── wire up ───────────────────────────────────────────────────
        add_btn.config(command=on_add)
        scan_btn.config(command=on_scan)
        clear_btn.config(command=on_clear)
        conv_btn.config(command=on_preview_selected)
        save_one_btn.config(command=on_save_one)
        use_btn.config(command=on_use_in_editor)
        batch_export_btn.config(command=lambda: on_batch_export(selected_only=False))
        batch_sel_btn.config(command=lambda: on_batch_export(selected_only=True))
        file_list.bind("<<ListboxSelect>>", on_list_select)

    # ── Shared document-converter dialog ─────────────────────────────

    def _open_doc_converter(self, *, title, filetypes, ext,
                             extract_fn, meta_fn, meta_fmt,
                             raw_label, raw_fn):
        """
        Generic converter dialog shared by EPUB and PDF tools.
        extract_fn(path) → plain text str
        meta_fn(path)    → metadata dict
        meta_fmt(dict)   → one-line summary string
        raw_fn(path)     → string shown in the left "source" panel
        """
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("820x580")
        win.minsize(640, 420)
        win.transient(self.root)
        win.configure(bg=self.colors["bg"])

        # ── top controls ──────────────────────────────────────────────
        ctrl = ttk.Frame(win, padding=(12, 10, 12, 6))
        ctrl.pack(fill="x")
        ttk.Label(ctrl, text=title, style="Section.TLabel").pack(side="left")

        btn_f = ttk.Frame(ctrl)
        btn_f.pack(side="right")
        load_btn  = ttk.Button(btn_f, text=f"Add {ext.upper()[1:]} File…")
        load_btn.pack(side="left", padx=(0, 6))
        batch_btn = ttk.Button(btn_f, text="Batch Add Files…")
        batch_btn.pack(side="left", padx=(0, 6))
        clear_btn = ttk.Button(btn_f, text="Clear")
        clear_btn.pack(side="left")

        # ── file queue ────────────────────────────────────────────────
        queue_lf = ttk.LabelFrame(win, text="Files", padding=6)
        queue_lf.pack(fill="x", padx=12, pady=(0, 6))

        q_sb = ttk.Scrollbar(queue_lf, orient="vertical")
        q_sb.pack(side="right", fill="y")
        file_list = tk.Listbox(
            queue_lf, height=4, font=FONT_MONO,
            yscrollcommand=q_sb.set, selectmode="extended",
            bg=self.colors["entry_bg"], fg=self.colors["fg"],
            selectbackground=self.colors["select_bg"],
            activestyle="none", borderwidth=0, highlightthickness=1,
            highlightcolor=self.colors["border"],
        )
        file_list.pack(fill="x", expand=True)
        q_sb.config(command=file_list.yview)

        meta_var = tk.StringVar(value="")
        ttk.Label(queue_lf, textvariable=meta_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(anchor="w", pady=(4, 0))

        remove_btn = ttk.Button(queue_lf, text="Remove Selected",
                                command=lambda: self._rtf_remove_selected(file_list))
        remove_btn.pack(anchor="e", pady=(4, 0))

        # ── side-by-side preview ──────────────────────────────────────
        pane = ttk.PanedWindow(win, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        left_f  = ttk.LabelFrame(pane, text=raw_label, padding=4)
        right_f = ttk.LabelFrame(pane, text="Extracted Text",  padding=4)
        pane.add(left_f,  weight=1)
        pane.add(right_f, weight=2)

        l_sb = ttk.Scrollbar(left_f)
        l_sb.pack(side="right", fill="y")
        src_box = tk.Text(
            left_f, wrap="word", font=FONT_MONO, state="disabled",
            yscrollcommand=l_sb.set, borderwidth=0, highlightthickness=0,
            bg=self.colors["entry_bg"], fg=self.colors["muted"],
            padx=6, pady=6,
        )
        src_box.pack(fill="both", expand=True)
        l_sb.config(command=src_box.yview)

        r_sb = ttk.Scrollbar(right_f)
        r_sb.pack(side="right", fill="y")
        txt_box = tk.Text(
            right_f, wrap="word", font=FONT_BODY,
            yscrollcommand=r_sb.set, borderwidth=0, highlightthickness=0,
            bg=self.colors["entry_bg"], fg=self.colors["fg"],
            insertbackground=self.colors["fg"], padx=6, pady=6,
        )
        txt_box.pack(fill="both", expand=True)
        r_sb.config(command=txt_box.yview)

        # ── bottom bar ────────────────────────────────────────────────
        bot = ttk.Frame(win, padding=(12, 4, 12, 10))
        bot.pack(fill="x")

        status_var = tk.StringVar(value=f"Add one or more {ext.upper()[1:]} files to begin.")
        ttk.Label(bot, textvariable=status_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(side="left")

        use_btn  = ttk.Button(bot, text="Load into TTS Editor",
                              style="Accent.TButton")
        use_btn.pack(side="right")
        save_btn = ttk.Button(bot, text="Save as .txt…")
        save_btn.pack(side="right", padx=(0, 6))
        conv_btn = ttk.Button(bot, text="Convert Selected")
        conv_btn.pack(side="right", padx=(0, 6))

        # ── shared state ──────────────────────────────────────────────
        file_paths = []
        converted  = {}   # path → plain text

        # ── callbacks ─────────────────────────────────────────────────
        def add_files(paths):
            for p in paths:
                if p not in file_paths:
                    file_paths.append(p)
                    file_list.insert("end", os.path.basename(p))
            if file_paths:
                status_var.set(f"{len(file_paths)} file(s) queued.")

        def on_load():
            paths = filedialog.askopenfilenames(
                parent=win, title=f"Select {ext.upper()[1:]} File(s)",
                filetypes=filetypes)
            if paths:
                add_files(paths)

        def on_batch():
            folder = filedialog.askdirectory(
                parent=win, title=f"Scan folder for *{ext} files")
            if not folder:
                return
            found = [os.path.join(r, f)
                     for r, _, fs in os.walk(folder)
                     for f in fs if f.lower().endswith(ext)]
            if found:
                add_files(found)
                status_var.set(f"Found {len(found)} {ext.upper()[1:]} file(s).")
            else:
                status_var.set(f"No {ext} files found in that folder.")

        def on_clear():
            file_list.delete(0, "end")
            file_paths.clear()
            converted.clear()
            _set_text(src_box, "")
            src_box.config(state="disabled")
            _set_text(txt_box, "")
            meta_var.set("")
            status_var.set("Cleared.")

        def on_list_select(_event):
            sel = file_list.curselection()
            if not sel:
                return
            path = file_paths[sel[0]]
            # Show source info in left panel
            try:
                raw = raw_fn(path)
                _set_text(src_box, raw)
                src_box.config(state="disabled")
                meta = meta_fn(path)
                meta_var.set(meta_fmt(meta))
            except Exception as err:
                _set_text(src_box, f"(could not read: {err})")
                src_box.config(state="disabled")
            # Show extracted text if already converted
            if path in converted:
                _set_text(txt_box, converted[path])
            else:
                _set_text(txt_box, "(not yet converted — click Convert Selected)")

        def _do_convert_bg(targets):
            """Run conversion in a background thread."""
            errors = []
            for path in targets:
                try:
                    converted[path] = extract_fn(path)
                except Exception as err:
                    errors.append(f"{os.path.basename(path)}: {err}")

            def done():
                first = next((p for p in targets if p in converted), None)
                if first:
                    _set_text(txt_box, converted[first])
                    try:
                        meta = meta_fn(first)
                        meta_var.set(meta_fmt(meta))
                    except Exception:
                        pass
                conv_btn.config(state="normal")
                if errors:
                    status_var.set(
                        f"Done — {len(errors)} error(s): {errors[0]}")
                else:
                    status_var.set(
                        f"Converted {len(targets)} file(s). "
                        "Select a file to preview it.")
            win.after(0, done)

        def on_convert_selected():
            sel     = file_list.curselection()
            targets = [file_paths[i] for i in sel] if sel else list(file_paths)
            if not targets:
                status_var.set("No files to convert.")
                return
            conv_btn.config(state="disabled")
            status_var.set(f"Converting {len(targets)} file(s)…")
            threading.Thread(
                target=_do_convert_bg, args=(targets,), daemon=True).start()

        def on_save():
            sel  = file_list.curselection()
            path = (file_paths[sel[0]] if sel
                    else (file_paths[0] if file_paths else None))
            if not path or path not in converted:
                messagebox.showinfo("Nothing to Save",
                                    "Convert a file first, then save.",
                                    parent=win)
                return
            default = os.path.splitext(path)[0] + ".txt"
            out = filedialog.asksaveasfilename(
                parent=win,
                initialfile=os.path.basename(default),
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            )
            if out:
                with open(out, "w", encoding="utf-8") as f:
                    f.write(converted[path])
                status_var.set(f"Saved: {os.path.basename(out)}")

        def on_use_in_editor():
            sel  = file_list.curselection()
            path = (file_paths[sel[0]] if sel
                    else (file_paths[0] if file_paths else None))
            if not path:
                messagebox.showinfo("No File Selected",
                                    "Select a file in the list first.",
                                    parent=win)
                return
            if path not in converted:
                try:
                    converted[path] = extract_fn(path)
                except Exception as err:
                    messagebox.showerror("Conversion Error", str(err), parent=win)
                    return
            self.text_area.delete("1.0", "end")
            self.text_area.insert("1.0", converted[path])
            self._update_word_count()
            self.file_label.config(text=os.path.basename(path))
            self.status_var.set(f"Loaded: {os.path.basename(path)}")
            self._add_recent(path)
            win.destroy()

        # Wire up
        load_btn.config(command=on_load)
        batch_btn.config(command=on_batch)
        clear_btn.config(command=on_clear)
        conv_btn.config(command=on_convert_selected)
        save_btn.config(command=on_save)
        use_btn.config(command=on_use_in_editor)
        file_list.bind("<<ListboxSelect>>", on_list_select)

    # ── File Handling ─────────────────────────────────────────────────

    def _open_and_load(self):
        path = filedialog.askopenfilename(
            filetypes=[("Supported Files", "*.txt *.md *.rtf *.epub *.pdf"),
                       ("Text Files", "*.txt *.md"),
                       ("Rich Text Format", "*.rtf"),
                       ("EPUB Books", "*.epub"),
                       ("PDF Documents", "*.pdf"),
                       ("All Files", "*.*")])
        if path:
            self._load_file(path)

    def _load_file(self, path):
        if not os.path.isfile(path):
            messagebox.showwarning("Not Found", f"File not found:\n{path}")
            return

        if os.path.splitext(path)[1].lower() == ".pdf":
            self._load_pdf_and_convert(path)
            return

        try:
            content = self._read_file(path)
        except Exception as e:
            messagebox.showerror("Read Error", f"Could not read file:\n{e}")
            return
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", content)
        self._update_word_count()
        if not self.output_path.get():
            fmt = self.format_var.get()
            self.output_path.set(os.path.splitext(path)[0] + EXPORT_FORMATS[fmt][0])
        self.file_label.config(text=os.path.basename(path))
        self.status_var.set(f"Loaded: {os.path.basename(path)}")
        self._add_recent(path)

    def _load_pdf_and_convert(self, path):
        """Extract PDF text in background, populate editor, then auto-convert."""
        base = os.path.basename(path)
        fmt  = self.format_var.get()
        ext  = EXPORT_FORMATS[fmt][0]

        self.file_label.config(text=base)
        self.status_var.set(f"Extracting text from PDF: {base}…")
        self._add_recent(path)

        if not self.output_path.get():
            self.output_path.set(os.path.splitext(path)[0] + ext)

        def bg():
            try:
                text = self._pdf_file_to_text(path)
            except Exception as e:
                self.root.after(0, lambda err=str(e): (
                    self.status_var.set(f"PDF extraction failed: {err}"),
                    messagebox.showerror("PDF Error",
                                         f"Could not extract text from PDF:\n{err}")))
                return

            def on_text_ready():
                self.text_area.delete("1.0", "end")
                self.text_area.insert("1.0", text)
                self._update_word_count()
                self.status_var.set(
                    f"PDF loaded: {base} — starting conversion…")
                # Small delay so the UI can repaint before the conversion thread starts
                self.root.after(150, self.convert)

            self.root.after(0, on_text_ready)

        threading.Thread(target=bg, daemon=True).start()

    def _read_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".rtf":
            return self._rtf_file_to_text(path)
        if ext == ".epub":
            # Capture metadata for later tag embedding
            try:
                meta = self._epub_metadata(path)
                self._source_meta = {
                    "title":  meta.get("title", ""),
                    "author": meta.get("author", ""),
                }
            except Exception:
                pass
            return self._epub_file_to_text(path)
        if ext == ".pdf":
            text = self._pdf_file_to_text(path)
            # OCR fallback for image-based PDFs
            if not text.strip() and self.tesseract:
                text = self._ocr_pdf(path)
            if self.clean_pdf_var.get():
                text = _clean_pdf_text(text)
            return text
        if ext == ".md":
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return _strip_markdown(f.read())
        # Plain text fallback
        with open(path, "rb") as f:
            raw = f.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        return text.encode("utf-8", errors="replace").decode("utf-8")

    def browse_output(self):
        fmt = self.format_var.get()
        ext = EXPORT_FORMATS[fmt][0]
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(f"{fmt} Files", f"*{ext}"), ("All Files", "*.*")])
        if path:
            self.output_path.set(path)

    def _clear_text(self):
        self.text_area.delete("1.0", "end")
        self._update_word_count()
        self.file_label.config(text="No file loaded")

    def _update_word_count(self):
        text  = self.text_area.get("1.0", "end").strip()
        words = len(text.split()) if text else 0
        chars = len(text)
        adj   = max(0.1, 1 + self.speed_var.get() / 100)
        secs  = int(words / (WPM_ESTIMATE * adj) * 60) if words else 0
        if secs >= 60:
            dur = f"~{secs//60}m {secs%60:02d}s"
        else:
            dur = f"~{secs}s" if secs else "—"
        self.word_count_var.set(f"{words:,} words  |  {chars:,} chars  |  {dur}")

    # ── Conversion ────────────────────────────────────────────────────

    def convert(self):
        if not self.chosen_voice:
            messagebox.showinfo("No Voice",
                                "Select a voice then click \"Use This Voice\".")
            return
        text = self.text_area.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("No Text", "Enter or load text first.")
            return

        fmt = self.format_var.get()
        ext = EXPORT_FORMATS[fmt][0]
        out = self.output_path.get()
        if not out:
            out = filedialog.asksaveasfilename(
                defaultextension=ext,
                filetypes=[(f"{fmt} Files", f"*{ext}"), ("All Files", "*.*")])
            if not out:
                return
            self.output_path.set(out)

        # Enforce correct extension for the selected format
        if not out.lower().endswith(ext.lower()):
            out = os.path.splitext(out)[0] + ext
            self.output_path.set(out)

        # Ensure output directory exists
        out_dir = os.path.dirname(out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        words = len(text.split())
        if words > 15000:
            if not messagebox.askyesno("Long Text",
                                       f"{words:,} words — conversion may take a while. Continue?"):
                return

        self.converting = True
        self.convert_btn.config(state="disabled")
        self.play_btn.config(state="disabled")
        self.reveal_btn.config(state="disabled")
        self._update_progress(0)
        self.status_var.set(f"Converting with {self.chosen_voice['ShortName']}…")

        self.settings["last_voice"] = self.chosen_voice["ShortName"]
        self._save_settings()

        threading.Thread(
            target=self._do_convert,
            args=(text, self.chosen_voice["ShortName"], out, fmt),
            daemon=True,
        ).start()

    # ── Core TTS conversion (no UI side-effects) ─────────────────────

    def _convert_to_audio_file(self, text, voice_name, out_path, fmt,
                                rate="+0%", pitch="+0Hz", volume="+0%",
                                progress_cb=None):
        """
        Convert *text* to an audio file at *out_path* in *fmt*.
        Applies pronunciation substitutions + optional text normalisation,
        chunks long text, synthesises via edge_tts or macOS say, injects
        inter-paragraph silence, concatenates via ffmpeg, applies quality
        preset and optional loudnorm, embeds metadata, and writes the cache.
        progress_cb(pct: int) is called periodically if provided.
        Raises on failure.  Does NOT touch any main-window widgets.
        """
        # ── pre-processing ────────────────────────────────────────────
        text = self._apply_pronunciations(text)
        if getattr(self, "normalize_text_var", None) and self.normalize_text_var.get():
            text = _normalize_text(text)

        backend = "macos"
        for v in self.all_voices:
            if v["ShortName"] == voice_name:
                backend = v.get("Backend", "edge_tts")
                break

        chunks  = _chunk_text(text)
        n       = len(chunks)
        tmp_dir = None
        tmp_mp3 = None

        # paragraph pause duration (seconds)
        para_pause = 0.0
        if getattr(self, "para_pause_var", None):
            lbl = self.para_pause_var.get()
            for name, secs in PARA_PAUSE_OPTIONS:
                if name == lbl:
                    para_pause = secs
                    break

        # quality preset extra ffmpeg args
        quality_extra = []
        if getattr(self, "quality_var", None):
            qlbl = self.quality_var.get()
            for label, args in QUALITY_PRESETS.get(fmt, []):
                if label == qlbl:
                    quality_extra = args
                    break

        MAX_RETRIES = 3

        def _synthesise_chunk(ct, ck_path):
            """Synthesise one chunk to ck_path; retry up to MAX_RETRIES times."""
            ck_fd, ck_tmp = tempfile.mkstemp(suffix=".mp3", dir=CONVERSION_CACHE_DIR)
            os.close(ck_fd)
            last_err = None
            for attempt in range(MAX_RETRIES):
                try:
                    if backend == "macos":
                        self._synthesize_macos(ct, voice_name, ck_tmp,
                                               rate=rate, pitch=pitch, volume=volume)
                    else:
                        async def _stream(ct=ct, p=ck_tmp):
                            with open(p, "wb") as f:
                                async for part in edge_tts.Communicate(
                                    ct, voice_name,
                                    rate=rate, pitch=pitch, volume=volume
                                ).stream():
                                    if part["type"] == "audio":
                                        f.write(part["data"])
                        run_async(_stream())

                    if os.path.isfile(ck_tmp) and os.path.getsize(ck_tmp) > 0:
                        shutil.move(ck_tmp, ck_path)
                        return
                    last_err = RuntimeError("synthesis returned no audio data")
                except Exception as e:
                    last_err = e
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)   # 1 s, 2 s backoff
                finally:
                    if os.path.isfile(ck_tmp):
                        try:
                            os.unlink(ck_tmp)
                        except OSError:
                            pass
            raise RuntimeError(f"Synthesis failed after {MAX_RETRIES} attempts: {last_err}")

        try:
            key       = self._cache_key(voice_name, text, rate, pitch, volume)
            cache_mp3 = self._conv_cache_path(key)

            if os.path.isfile(cache_mp3) and os.path.getsize(cache_mp3) > 0:
                if progress_cb:
                    progress_cb(70)
            elif n == 1 and para_pause == 0.0:
                # ── single-chunk, no silence ──────────────────────────
                total = len(text)
                done  = 0
                tmp_fd, tmp_mp3 = tempfile.mkstemp(suffix=".mp3",
                                                   dir=CONVERSION_CACHE_DIR)
                os.close(tmp_fd)
                if backend == "macos":
                    _synthesise_chunk(text, tmp_mp3)
                else:
                    async def stream():
                        nonlocal done
                        with open(tmp_mp3, "wb") as f:
                            async for chunk in edge_tts.Communicate(
                                text, voice_name, rate=rate, pitch=pitch, volume=volume
                            ).stream():
                                if chunk["type"] == "audio":
                                    f.write(chunk["data"])
                                elif chunk["type"] == "WordBoundary":
                                    done = min(total, done + len(chunk.get("text", "")) + 1)
                                    if progress_cb:
                                        progress_cb(min(80, int(done / total * 80)))
                    run_async(stream())

                if not (os.path.isfile(tmp_mp3) and os.path.getsize(tmp_mp3) > 0):
                    raise RuntimeError("TTS synthesis returned no audio data.")

                shutil.move(tmp_mp3, cache_mp3)
                tmp_mp3 = None
            else:
                # ── multi-chunk (or silence needed) ───────────────────
                tmp_dir        = tempfile.mkdtemp(dir=CONVERSION_CACHE_DIR)
                chunk_files    = []   # successfully synthesised chunks
                partial_saved  = False

                silence_path = None
                if para_pause > 0.0 and self.ffmpeg:
                    silence_path = os.path.join(tmp_dir, "silence.mp3")
                    self._make_silence_clip(para_pause, silence_path)

                for ci, ct in enumerate(chunks):
                    ck     = self._cache_key(voice_name, ct, rate, pitch, volume)
                    ck_path = self._conv_cache_path(ck)

                    if not (os.path.isfile(ck_path) and os.path.getsize(ck_path) > 0):
                        try:
                            _synthesise_chunk(ct, ck_path)
                        except Exception as e:
                            # Partial output: save what we have so far
                            if chunk_files and self.ffmpeg:
                                partial_dir = os.path.dirname(out_path)
                                base, ext2  = os.path.splitext(os.path.basename(out_path))
                                partial_out = os.path.join(partial_dir,
                                                           f"{base}_partial{ext2}")
                                try:
                                    clist = os.path.join(tmp_dir, "partial_concat.txt")
                                    with open(clist, "w") as fl:
                                        for cf in chunk_files:
                                            fl.write(f"file '{cf}'\n")
                                    subprocess.run(
                                        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                                         "-i", clist, "-acodec", "copy", partial_out],
                                        capture_output=True, check=False)
                                    partial_saved = True
                                except Exception:
                                    pass
                            raise RuntimeError(
                                f"Chunk {ci+1}/{n} failed: {e}"
                                + (f"\n(Partial output saved: {partial_out})"
                                   if partial_saved else ""))

                    chunk_files.append(ck_path)
                    if silence_path and ci < n - 1:
                        chunk_files.append(silence_path)
                    if progress_cb:
                        progress_cb(min(80, int((ci + 1) / n * 80)))

                # Concat all into cache entry
                concat_list = os.path.join(tmp_dir, "concat.txt")
                with open(concat_list, "w") as f:
                    for cf in chunk_files:
                        f.write(f"file '{cf}'\n")
                cfd, concat_tmp = tempfile.mkstemp(suffix=".mp3",
                                                   dir=CONVERSION_CACHE_DIR)
                os.close(cfd)
                result = subprocess.run(
                    ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                     "-i", concat_list, "-acodec", "copy", concat_tmp],
                    capture_output=True)
                if result.returncode != 0:
                    raise RuntimeError(
                        "ffmpeg chunk concat failed: "
                        + result.stderr.decode(errors="replace")[:300])
                shutil.move(concat_tmp, cache_mp3)

            if progress_cb:
                progress_cb(88)

            # ── format conversion ─────────────────────────────────────
            base_ffmpeg_args = list(EXPORT_FORMATS[fmt][1] or [])
            # Override bitrate args with quality preset if provided
            if quality_extra and base_ffmpeg_args:
                # Remove existing -b:a / -q:a from base args if quality_extra supplies them
                if quality_extra[0] in ("-b:a", "-q:a"):
                    for flag in ("-b:a", "-q:a"):
                        try:
                            idx = base_ffmpeg_args.index(flag)
                            base_ffmpeg_args.pop(idx)    # remove flag
                            base_ffmpeg_args.pop(idx)    # remove value
                        except ValueError:
                            pass
                base_ffmpeg_args = base_ffmpeg_args + quality_extra

            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            if not base_ffmpeg_args:          # MP3 native copy or no conversion
                if os.path.abspath(cache_mp3) != os.path.abspath(out_path):
                    shutil.copy2(cache_mp3, out_path)
            else:
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", cache_mp3] + base_ffmpeg_args + [out_path],
                    capture_output=True)
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(
                        result.returncode, "ffmpeg", result.stderr)

            if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
                raise RuntimeError(f"Output file is missing or empty: {out_path}")

            if progress_cb:
                progress_cb(92)

            # ── audio normalisation (loudnorm) ────────────────────────
            if (getattr(self, "normalize_audio_var", None)
                    and self.normalize_audio_var.get() and self.ffmpeg):
                nfd, norm_tmp = tempfile.mkstemp(
                    suffix=os.path.splitext(out_path)[1], dir=CONVERSION_CACHE_DIR)
                os.close(nfd)
                res = subprocess.run(
                    ["ffmpeg", "-y", "-i", out_path,
                     "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                     "-ar", "44100", norm_tmp],
                    capture_output=True)
                if res.returncode == 0 and os.path.getsize(norm_tmp) > 0:
                    shutil.move(norm_tmp, out_path)
                else:
                    try:
                        os.unlink(norm_tmp)
                    except OSError:
                        pass

            if progress_cb:
                progress_cb(96)

            # ── metadata embedding ────────────────────────────────────
            meta = getattr(self, "_source_meta", {})
            if meta and self.ffmpeg:
                self._embed_metadata(
                    out_path, fmt,
                    title=meta.get("title", ""),
                    author=meta.get("author", ""),
                    cover_path=meta.get("cover_path"))

            if progress_cb:
                progress_cb(100)

            # ── history record ────────────────────────────────────────
            try:
                self._record_history({
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "voice":  voice_name,
                    "format": fmt,
                    "output": out_path,
                    "chars":  len(text),
                    "chunks": n,
                })
            except Exception:
                pass

        finally:
            for tmp in [tmp_mp3]:
                if tmp and os.path.isfile(tmp):
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    # ── Batch Text to Audio converter ────────────────────────────────

    def _open_batch_audio_converter(self):
        """Dialog: queue text/RTF/EPUB/PDF files → convert each to audio."""
        win = tk.Toplevel(self.root)
        win.title("Batch Text to Audio")
        win.geometry("820x640")
        win.minsize(640, 480)
        win.transient(self.root)
        win.configure(bg=self.colors["bg"])

        # ── header ────────────────────────────────────────────────────
        ctrl = ttk.Frame(win, padding=(12, 10, 12, 6))
        ctrl.pack(fill="x")
        ttk.Label(ctrl, text="Batch Text to Audio",
                  style="Section.TLabel").pack(side="left")

        btn_f = ttk.Frame(ctrl)
        btn_f.pack(side="right")
        add_btn  = ttk.Button(btn_f, text="Add Files…")
        add_btn.pack(side="left", padx=(0, 6))
        scan_btn = ttk.Button(btn_f, text="Scan Folder…")
        scan_btn.pack(side="left", padx=(0, 6))
        clear_btn = ttk.Button(btn_f, text="Clear All")
        clear_btn.pack(side="left")

        # ── file queue ────────────────────────────────────────────────
        queue_lf = ttk.LabelFrame(win, text="Input Files", padding=6)
        queue_lf.pack(fill="x", padx=12, pady=(0, 6))

        q_sb = ttk.Scrollbar(queue_lf, orient="vertical")
        q_sb.pack(side="right", fill="y")
        file_list = tk.Listbox(
            queue_lf, height=5, font=FONT_MONO,
            yscrollcommand=q_sb.set, selectmode="extended",
            bg=self.colors["entry_bg"], fg=self.colors["fg"],
            selectbackground=self.colors["select_bg"],
            activestyle="none", borderwidth=0, highlightthickness=1,
            highlightcolor=self.colors["border"],
        )
        file_list.pack(fill="x", expand=True)
        q_sb.config(command=file_list.yview)

        ttk.Button(queue_lf, text="Remove Selected",
                   command=lambda: self._rtf_remove_selected(file_list)
                   ).pack(anchor="e", pady=(4, 0))

        # ── conversion settings ───────────────────────────────────────
        settings_lf = ttk.LabelFrame(win, text="Conversion Settings", padding=8)
        settings_lf.pack(fill="x", padx=12, pady=(0, 6))

        row1 = ttk.Frame(settings_lf)
        row1.pack(fill="x", pady=(0, 4))

        # Voice indicator
        ttk.Label(row1, text="Voice:", font=FONT_SMALL).pack(side="left")
        voice_name = (self.chosen_voice["ShortName"]
                      if self.chosen_voice else "No voice selected — pick one in the main window")
        voice_var = tk.StringVar(value=voice_name)
        ttk.Label(row1, textvariable=voice_var,
                  font=FONT_SMALL, style="Blue.TLabel").pack(side="left", padx=(6, 20))

        # Format selector
        ttk.Label(row1, text="Format:", font=FONT_SMALL).pack(side="left")
        batch_fmt_var = tk.StringVar(value=self.format_var.get())
        fmt_cb = ttk.Combobox(row1, textvariable=batch_fmt_var,
                              values=list(EXPORT_FORMATS.keys()),
                              state="readonly", width=7, font=FONT_SMALL)
        fmt_cb.pack(side="left", padx=(6, 0))

        row2 = ttk.Frame(settings_lf)
        row2.pack(fill="x")

        # Output folder
        ttk.Label(row2, text="Output folder:", font=FONT_SMALL).pack(side="left")
        out_folder_var = tk.StringVar(value="Same folder as each source file")
        out_folder_entry = ttk.Entry(row2, textvariable=out_folder_var,
                                     font=FONT_SMALL, state="readonly")
        out_folder_entry.pack(side="left", fill="x", expand=True, padx=6)

        def choose_out_folder():
            folder = filedialog.askdirectory(parent=win,
                                             title="Choose output folder for audio files")
            if folder:
                out_folder_var.set(folder)

        def reset_out_folder():
            out_folder_var.set("Same folder as each source file")

        ttk.Button(row2, text="Browse…", command=choose_out_folder).pack(side="left")
        ttk.Button(row2, text="Reset",   command=reset_out_folder).pack(side="left", padx=(4, 0))

        # ── batch progress ────────────────────────────────────────────
        prog_lf = ttk.LabelFrame(win, text="Progress", padding=8)
        prog_lf.pack(fill="x", padx=12, pady=(0, 6))

        file_status_var = tk.StringVar(value="")
        ttk.Label(prog_lf, textvariable=file_status_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(anchor="w")

        # Per-file bar
        pf_row = ttk.Frame(prog_lf)
        pf_row.pack(fill="x", pady=(4, 2))
        ttk.Label(pf_row, text="File:", width=8, font=FONT_CAPTION).pack(side="left")
        file_prog_var = tk.DoubleVar(value=0)
        file_pbar = ttk.Progressbar(pf_row, variable=file_prog_var, maximum=100)
        file_pbar.pack(side="left", fill="x", expand=True, padx=(0, 6))
        file_pct_var = tk.StringVar(value="")
        ttk.Label(pf_row, textvariable=file_pct_var,
                  width=5, font=FONT_SMALL).pack(side="left")

        # Overall bar
        ov_row = ttk.Frame(prog_lf)
        ov_row.pack(fill="x")
        ttk.Label(ov_row, text="Total:", width=8, font=FONT_CAPTION).pack(side="left")
        overall_prog_var = tk.DoubleVar(value=0)
        overall_pbar = ttk.Progressbar(ov_row, variable=overall_prog_var, maximum=100)
        overall_pbar.pack(side="left", fill="x", expand=True, padx=(0, 6))
        overall_pct_var = tk.StringVar(value="")
        ttk.Label(ov_row, textvariable=overall_pct_var,
                  width=5, font=FONT_SMALL).pack(side="left")

        # ── action bar ────────────────────────────────────────────────
        act_row = ttk.Frame(win, padding=(12, 4, 12, 10))
        act_row.pack(fill="x")

        convert_all_btn = ttk.Button(act_row, text="Convert All → Audio",
                                     style="Accent.TButton")
        convert_all_btn.pack(side="left", padx=(0, 8))
        convert_sel_btn = ttk.Button(act_row, text="Convert Selected → Audio")
        convert_sel_btn.pack(side="left")
        batch_action_status = tk.StringVar(
            value="Add files above, then click Convert.")
        ttk.Label(act_row, textvariable=batch_action_status,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(side="left", padx=(12, 0))

        # ── state ─────────────────────────────────────────────────────
        file_paths = []
        _running   = [False]

        SUPPORTED_TYPES = {".txt", ".rtf", ".epub", ".pdf"}

        def extract_text(path):
            ext = os.path.splitext(path)[1].lower()
            if ext == ".txt":
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            elif ext == ".rtf":
                return self._rtf_file_to_text(path)
            elif ext == ".epub":
                return self._epub_file_to_text(path)
            elif ext == ".pdf":
                return self._pdf_file_to_text(path)
            else:
                raise ValueError(f"Unsupported file type: {ext}")

        def resolve_output_path(src_path):
            stem = os.path.splitext(os.path.basename(src_path))[0]
            fmt  = batch_fmt_var.get()
            ext  = EXPORT_FORMATS[fmt][0]
            folder = out_folder_var.get()
            if folder == "Same folder as each source file":
                folder = os.path.dirname(src_path)
            return os.path.join(folder, stem + ext)

        def add_files(paths):
            for p in paths:
                if p not in file_paths:
                    file_paths.append(p)
                    file_list.insert("end", os.path.basename(p))

        def on_add():
            types = [
                ("Text & Document Files",
                 "*.txt *.rtf *.epub *.pdf"),
                ("Text files",  "*.txt"),
                ("RTF files",   "*.rtf"),
                ("EPUB files",  "*.epub"),
                ("PDF files",   "*.pdf"),
                ("All files",   "*.*"),
            ]
            paths = filedialog.askopenfilenames(parent=win, filetypes=types,
                                                title="Add text files for batch conversion")
            if paths:
                add_files(paths)

        def on_scan():
            folder = filedialog.askdirectory(parent=win,
                                             title="Scan folder for text files")
            if not folder:
                return
            found = []
            for root_dir, _, files in os.walk(folder):
                for fname in sorted(files):
                    if os.path.splitext(fname)[1].lower() in SUPPORTED_TYPES:
                        found.append(os.path.join(root_dir, fname))
            if found:
                add_files(found)
                batch_action_status.set(f"Added {len(found)} file(s) from scan.")
            else:
                batch_action_status.set("No supported files found in folder.")

        def on_clear():
            file_paths.clear()
            file_list.delete(0, "end")
            file_prog_var.set(0)
            file_pct_var.set("")
            overall_prog_var.set(0)
            overall_pct_var.set("")
            file_status_var.set("")
            batch_action_status.set("Add files above, then click Convert.")

        def run_batch(targets):
            if not targets:
                win.after(0, lambda: batch_action_status.set("No files queued."))
                return

            voice = self.chosen_voice
            if not voice:
                win.after(0, lambda: messagebox.showwarning(
                    "No Voice",
                    "Select a voice in the main window first.",
                    parent=win))
                win.after(0, _unlock_buttons)
                return

            fmt   = batch_fmt_var.get()
            rate  = f"{self.speed_var.get():+d}%"
            pitch = f"{self.pitch_var.get():+d}Hz"
            vol   = f"{self.volume_var.get():+d}%"
            total = len(targets)
            saved = []
            errors = []

            for i, path in enumerate(targets, start=1):
                base = os.path.basename(path)
                win.after(0, lambda b=base, n=i, t=total:
                           file_status_var.set(f"Converting {n}/{t}: {b}"))
                win.after(0, lambda: (file_prog_var.set(0), file_pct_var.set("0%")))

                def make_file_cb(n=i, t=total):
                    def cb(pct):
                        win.after(0, lambda p=pct: (
                            file_prog_var.set(p),
                            file_pct_var.set(f"{p}%"),
                        ))
                        overall_pct = int(((n - 1 + pct / 100) / t) * 100)
                        win.after(0, lambda p=overall_pct: (
                            overall_prog_var.set(p),
                            overall_pct_var.set(f"{p}%"),
                        ))
                    return cb

                try:
                    text    = extract_text(path)
                    out     = resolve_output_path(path)
                    self._convert_to_audio_file(
                        text, voice["ShortName"], out, fmt,
                        rate=rate, pitch=pitch, volume=vol,
                        progress_cb=make_file_cb())
                    saved.append(out)
                except Exception as err:
                    errors.append(f"{base}: {err}")

                overall_pct = int(i / total * 100)
                win.after(0, lambda p=overall_pct: (
                    overall_prog_var.set(p),
                    overall_pct_var.set(f"{p}%"),
                ))

            def done():
                _unlock_buttons()
                if errors:
                    summary = (f"Converted {len(saved)}/{total} files.\n\n"
                               "Errors:\n" + "\n".join(errors))
                    messagebox.showwarning("Batch Conversion Complete", summary,
                                           parent=win)
                    file_status_var.set(
                        f"Done — {len(saved)} converted, {len(errors)} error(s).")
                    batch_action_status.set(
                        f"{len(saved)}/{total} converted — see warnings for errors.")
                else:
                    file_status_var.set(
                        f"All {len(saved)} file(s) converted successfully.")
                    batch_action_status.set(f"Done! {len(saved)} audio file(s) saved.")
                    folder = out_folder_var.get()
                    if folder == "Same folder as each source file" and saved:
                        folder = os.path.dirname(saved[0])
                    if messagebox.askyesno(
                            "Open Output Folder",
                            f"Converted {len(saved)} file(s).\nOpen output folder in Finder?",
                            parent=win):
                        subprocess.Popen(["open", folder])

            win.after(0, done)

        def _lock_buttons():
            convert_all_btn.config(state="disabled")
            convert_sel_btn.config(state="disabled")
            add_btn.config(state="disabled")
            scan_btn.config(state="disabled")

        def _unlock_buttons():
            _running[0] = False
            convert_all_btn.config(state="normal")
            convert_sel_btn.config(state="normal")
            add_btn.config(state="normal")
            scan_btn.config(state="normal")

        def on_convert(selected_only=False):
            if _running[0]:
                return
            if selected_only:
                sel     = file_list.curselection()
                targets = [file_paths[i] for i in sel]
                if not targets:
                    batch_action_status.set("No files selected.")
                    return
            else:
                targets = list(file_paths)
                if not targets:
                    batch_action_status.set("No files queued.")
                    return

            _running[0] = True
            _lock_buttons()
            overall_prog_var.set(0)
            overall_pct_var.set("0%")
            file_prog_var.set(0)
            file_pct_var.set("0%")
            batch_action_status.set(f"Starting — {len(targets)} file(s)…")
            threading.Thread(target=run_batch, args=(targets,), daemon=True).start()

        # ── wire up ───────────────────────────────────────────────────
        add_btn.config(command=on_add)
        scan_btn.config(command=on_scan)
        clear_btn.config(command=on_clear)
        convert_all_btn.config(command=lambda: on_convert(selected_only=False))
        convert_sel_btn.config(command=lambda: on_convert(selected_only=True))

    def _do_convert(self, text, voice_name, out_path, fmt):
        rate   = f"{self.speed_var.get():+d}%"
        pitch  = f"{self.pitch_var.get():+d}Hz"
        volume = f"{self.volume_var.get():+d}%"

        # Detect cache hit up-front (after pronunciation substitution) for status msg
        processed  = self._apply_pronunciations(text)
        key        = self._cache_key(voice_name, processed, rate, pitch, volume)
        cache_mp3  = self._conv_cache_path(key)
        from_cache = os.path.isfile(cache_mp3) and os.path.getsize(cache_mp3) > 0

        self._conv_start_t = time.time()

        def progress_cb(pct):
            self.root.after(0, self._update_progress, pct)
            if pct > 5 and not from_cache:
                elapsed = time.time() - self._conv_start_t
                remaining = elapsed / (pct / 100) - elapsed
                if remaining >= 60:
                    eta = f"~{int(remaining / 60)}m {int(remaining % 60)}s remaining"
                else:
                    eta = f"~{int(remaining)}s remaining"
                self.root.after(0, self.status_var.set,
                                f"Converting… {pct}%  ({eta})")

        try:
            self._convert_to_audio_file(
                text, voice_name, out_path, fmt,
                rate=rate, pitch=pitch, volume=volume,
                progress_cb=progress_cb)

            self.output_file = out_path

            def on_done():
                self.converting = False
                self.convert_btn.config(state="normal")
                self.play_btn.config(state="normal")
                self.reveal_btn.config(state="normal")
                self.play_pause_btn.config(state="normal")
                self._player_file = out_path
                self._update_cache_size_label()
                kb  = os.path.getsize(out_path) / 1024
                src = "  (from cache)" if from_cache else ""
                n_chunks = len(_chunk_text(processed))
                chunk_note = f"  ({n_chunks} chunks)" if n_chunks > 1 else ""
                self.status_var.set(
                    f"Saved: {os.path.basename(out_path)}{src}{chunk_note}  ({kb:.0f} KB)")
                self.root.after(4000, self._clear_progress)
                # Pre-load duration for playback bar
                if self.ffmpeg:
                    threading.Thread(
                        target=lambda: self._preload_duration(out_path),
                        daemon=True).start()

            self.root.after(0, on_done)

        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode(errors="replace")[:600] if e.stderr else "(no output)"
            err_msg = f"ffmpeg failed (exit {e.returncode}):\n{stderr}"
            def on_err(msg=err_msg):
                self.converting = False
                self.convert_btn.config(state="normal")
                self._clear_progress()
                self.status_var.set("Format conversion failed")
                messagebox.showerror("ffmpeg Error", msg)
            self.root.after(0, on_err)

        except Exception as e:
            err_msg = str(e)
            def on_err(msg=err_msg):
                self.converting = False
                self.convert_btn.config(state="normal")
                self._clear_progress()
                self.status_var.set(f"Conversion failed: {msg}")
                messagebox.showerror("Conversion Error", msg)
            self.root.after(0, on_err)

    # ── Pronunciation Dictionary ──────────────────────────────────────

    def _load_pronunciations(self):
        try:
            with open(PRONUNCIATION_FILE) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_pronunciations(self):
        with open(PRONUNCIATION_FILE, "w") as f:
            json.dump(self.pronunciations, f, indent=2)

    def _apply_pronunciations(self, text):
        """Apply all pronunciation substitutions to *text* before TTS."""
        for entry in self.pronunciations:
            find    = entry.get("find", "")
            replace = entry.get("replace", "")
            if not find:
                continue
            if entry.get("whole_word", False):
                text = re.sub(r'\b' + re.escape(find) + r'\b', replace, text)
            else:
                text = text.replace(find, replace)
        return text

    def _open_pronunciation_editor(self):
        """Dialog to manage the pronunciation substitution dictionary."""
        win = tk.Toplevel(self.root)
        win.title("Pronunciation Dictionary")
        win.geometry("640x480")
        win.minsize(500, 360)
        win.transient(self.root)
        win.configure(bg=self.colors["bg"])

        # ── header ────────────────────────────────────────────────────
        hdr = ttk.Frame(win, padding=(12, 10, 12, 4))
        hdr.pack(fill="x")
        ttk.Label(hdr, text="Pronunciation Dictionary",
                  style="Section.TLabel").pack(side="left")
        ttk.Label(
            hdr,
            text="Substitutions are applied to text before TTS conversion.",
            style="Muted.TLabel", font=FONT_CAPTION,
        ).pack(side="left", padx=(12, 0))

        # ── table ─────────────────────────────────────────────────────
        tbl_f = ttk.Frame(win, padding=(12, 0, 12, 0))
        tbl_f.pack(fill="both", expand=True)

        cols = ("find", "replace", "whole_word")
        tree = ttk.Treeview(tbl_f, columns=cols, show="headings", selectmode="browse")
        tree.heading("find",       text="Find")
        tree.heading("replace",    text="Replace with")
        tree.heading("whole_word", text="Whole word")
        tree.column("find",       width=200, stretch=True)
        tree.column("replace",    width=200, stretch=True)
        tree.column("whole_word", width=90,  stretch=False, anchor="center")
        vsb = ttk.Scrollbar(tbl_f, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def _refresh_tree():
            tree.delete(*tree.get_children())
            for e in self.pronunciations:
                ww = "✓" if e.get("whole_word") else ""
                tree.insert("", "end", values=(e["find"], e["replace"], ww))

        _refresh_tree()

        # ── edit row ──────────────────────────────────────────────────
        edit_lf = ttk.LabelFrame(win, text="Add / Edit Entry", padding=8)
        edit_lf.pack(fill="x", padx=12, pady=6)

        er = ttk.Frame(edit_lf)
        er.pack(fill="x")
        ttk.Label(er, text="Find:",    width=10, font=FONT_SMALL).grid(row=0, column=0, sticky="w")
        find_var = tk.StringVar()
        ttk.Entry(er, textvariable=find_var, font=FONT_SMALL).grid(
            row=0, column=1, sticky="ew", padx=(4, 12))
        ttk.Label(er, text="Replace:", width=10, font=FONT_SMALL).grid(row=0, column=2, sticky="w")
        replace_var = tk.StringVar()
        ttk.Entry(er, textvariable=replace_var, font=FONT_SMALL).grid(
            row=0, column=3, sticky="ew", padx=4)
        whole_var = tk.BooleanVar()
        ttk.Checkbutton(er, text="Whole word only", variable=whole_var).grid(
            row=1, column=1, sticky="w", pady=(4, 0))
        er.columnconfigure(1, weight=1)
        er.columnconfigure(3, weight=1)

        def on_tree_select(_=None):
            sel = tree.selection()
            if not sel:
                return
            idx  = tree.index(sel[0])
            entry = self.pronunciations[idx]
            find_var.set(entry.get("find", ""))
            replace_var.set(entry.get("replace", ""))
            whole_var.set(entry.get("whole_word", False))

        tree.bind("<<TreeviewSelect>>", on_tree_select)

        def on_add():
            f = find_var.get().strip()
            r = replace_var.get()
            if not f:
                return
            self.pronunciations.append(
                {"find": f, "replace": r, "whole_word": whole_var.get()})
            self._save_pronunciations()
            _refresh_tree()
            find_var.set("")
            replace_var.set("")
            whole_var.set(False)

        def on_update():
            sel = tree.selection()
            if not sel:
                on_add()
                return
            idx  = tree.index(sel[0])
            f    = find_var.get().strip()
            r    = replace_var.get()
            if not f:
                return
            self.pronunciations[idx] = {
                "find": f, "replace": r, "whole_word": whole_var.get()}
            self._save_pronunciations()
            _refresh_tree()

        def on_delete():
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            del self.pronunciations[idx]
            self._save_pronunciations()
            _refresh_tree()
            find_var.set("")
            replace_var.set("")

        # ── button bar ────────────────────────────────────────────────
        bb = ttk.Frame(win, padding=(12, 0, 12, 10))
        bb.pack(fill="x")
        ttk.Button(bb, text="Add New",        command=on_add,    style="Accent.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(bb, text="Update Selected", command=on_update).pack(side="left", padx=(0, 6))
        ttk.Button(bb, text="Delete Selected", command=on_delete).pack(side="left")

        # Built-in suggestions
        sug_btn = ttk.Button(bb, text="Load Defaults", command=lambda: _load_defaults())
        sug_btn.pack(side="right")

        DEFAULT_PRONUNCIATIONS = [
            {"find": "Dr.",    "replace": "Doctor",    "whole_word": False},
            {"find": "Mr.",    "replace": "Mister",    "whole_word": False},
            {"find": "Mrs.",   "replace": "Misses",    "whole_word": False},
            {"find": "Ms.",    "replace": "Miss",      "whole_word": False},
            {"find": "St.",    "replace": "Saint",     "whole_word": False},
            {"find": "vs.",    "replace": "versus",    "whole_word": False},
            {"find": "etc.",   "replace": "etcetera",  "whole_word": False},
            {"find": "i.e.",   "replace": "that is",   "whole_word": False},
            {"find": "e.g.",   "replace": "for example", "whole_word": False},
            {"find": "API",    "replace": "A P I",     "whole_word": True},
            {"find": "URL",    "replace": "U R L",     "whole_word": True},
            {"find": "NASA",   "replace": "NASA",      "whole_word": True},
            {"find": "AI",     "replace": "A I",       "whole_word": True},
        ]

        def _load_defaults():
            existing_finds = {e["find"] for e in self.pronunciations}
            added = 0
            for d in DEFAULT_PRONUNCIATIONS:
                if d["find"] not in existing_finds:
                    self.pronunciations.append(d)
                    added += 1
            if added:
                self._save_pronunciations()
                _refresh_tree()

    # ── Inline Playback ───────────────────────────────────────────────

    def _preload_duration(self, path):
        dur = self._get_audio_duration(path)
        def ui():
            self._player_dur = dur
            self.playback_seek_scale.config(to=max(1, dur))
            self.playback_time_var.set(f"0:00 / {self._fmt_time(dur)}")
        self.root.after(0, ui)

    @staticmethod
    def _get_audio_duration(path):
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", path],
                capture_output=True, timeout=10)
            if r.returncode == 0:
                return float(r.stdout.decode().strip())
        except Exception:
            pass
        return 0.0

    @staticmethod
    def _fmt_time(secs):
        secs = max(0, int(secs))
        return f"{secs // 60}:{secs % 60:02d}"

    def _toggle_playback(self):
        if not self._player_file or not os.path.isfile(self._player_file):
            if self.output_file and os.path.isfile(self.output_file):
                self._player_file = self.output_file
            else:
                return

        if self._player_proc is None:
            self._start_inline_play(self._player_file)
        elif self._player_paused:
            try:
                os.kill(self._player_proc.pid, signal.SIGCONT)
            except (ProcessLookupError, OSError):
                pass
            self._player_start  = time.time() - self._player_pos
            self._player_paused = False
            self._schedule_player_tick()
            self._update_playback_btn()
        else:
            try:
                os.kill(self._player_proc.pid, signal.SIGSTOP)
            except (ProcessLookupError, OSError):
                pass
            self._player_paused = True
            if self._player_timer:
                self.root.after_cancel(self._player_timer)
                self._player_timer = None
            self._update_playback_btn()

    def _start_inline_play(self, path, start_pos=0.0):
        self._player_start  = time.time() - start_pos
        self._player_pos    = start_pos
        self._player_paused = False
        self._player_proc   = subprocess.Popen(["afplay", path])
        self._schedule_player_tick()
        self._update_playback_btn()

    def _stop_playback(self):
        if self._player_proc:
            try:
                self._player_proc.terminate()
            except OSError:
                pass
            self._player_proc = None
        if self._player_timer:
            self.root.after_cancel(self._player_timer)
            self._player_timer = None
        self._player_paused = False
        self._player_pos    = 0.0
        self.playback_pos_var.set(0)
        if self._player_dur > 0:
            self.playback_time_var.set(f"0:00 / {self._fmt_time(self._player_dur)}")
        else:
            self.playback_time_var.set("—")
        self._update_playback_btn()

    def _schedule_player_tick(self):
        self._player_timer = self.root.after(500, self._player_tick)

    def _player_tick(self):
        if self._player_proc is None or self._player_paused:
            return
        if self._player_proc.poll() is not None:
            # Playback finished naturally
            self._player_proc  = None
            self._player_pos   = 0.0
            self.playback_pos_var.set(0)
            if self._player_dur > 0:
                self.playback_time_var.set(f"0:00 / {self._fmt_time(self._player_dur)}")
            self._update_playback_btn()
            return

        self._player_pos = time.time() - self._player_start
        if self._player_dur > 0:
            self.playback_pos_var.set(min(self._player_dur, self._player_pos))
            self.playback_time_var.set(
                f"{self._fmt_time(self._player_pos)} / {self._fmt_time(self._player_dur)}")
        self._schedule_player_tick()

    def _update_playback_btn(self):
        if not hasattr(self, "play_pause_btn"):
            return
        playing = self._player_proc is not None and not self._player_paused
        self.play_pause_btn.config(text="⏸  Pause" if playing else "▶  Play")

    def _on_seek(self, val):
        if not self._player_file or not self.ffmpeg:
            return
        seek_pos = float(val)
        # Stop current playback
        if self._player_proc:
            try:
                self._player_proc.terminate()
            except OSError:
                pass
            self._player_proc = None
        if self._player_timer:
            self.root.after_cancel(self._player_timer)
            self._player_timer = None

        def do_seek():
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
            os.close(tmp_fd)
            r = subprocess.run(
                ["ffmpeg", "-y", "-ss", str(seek_pos), "-i", self._player_file,
                 "-acodec", "copy", tmp_path],
                capture_output=True)
            if r.returncode == 0:
                self.root.after(0, lambda: self._start_inline_play(tmp_path, seek_pos))
            else:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        threading.Thread(target=do_seek, daemon=True).start()

    # ── Open-in-App / Finder ──────────────────────────────────────────

    def play_output(self):
        if self.output_file and os.path.isfile(self.output_file):
            subprocess.Popen(["open", self.output_file])

    def reveal_in_finder(self):
        if self.output_file and os.path.isfile(self.output_file):
            subprocess.Popen(["open", "-R", self.output_file])

    # ── Drag & Drop ───────────────────────────────────────────────────

    def _on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        for path in paths:
            ext = os.path.splitext(path)[1].lower()
            if ext in (".txt", ".rtf", ".epub", ".pdf"):
                self._load_file(path)
                return

    # ── Audiobook Converter (M4B) ─────────────────────────────────────

    def _open_audiobook_converter(self):
        """EPUB → chapter-aware M4B audiobook with embedded chapter markers."""
        if not self.ffmpeg:
            messagebox.showwarning(
                "ffmpeg Required",
                "The audiobook converter requires ffmpeg. Please install it and restart.")
            return

        win = tk.Toplevel(self.root)
        win.title("Audiobook Converter (M4B)")
        win.geometry("780x680")
        win.minsize(620, 520)
        win.transient(self.root)
        win.configure(bg=self.colors["bg"])

        # ── header ────────────────────────────────────────────────────
        ctrl = ttk.Frame(win, padding=(12, 10, 12, 6))
        ctrl.pack(fill="x")
        ttk.Label(ctrl, text="Audiobook Converter (M4B)",
                  style="Section.TLabel").pack(side="left")

        load_btn = ttk.Button(ctrl, text="Open EPUB…")
        load_btn.pack(side="right")

        # ── book info ─────────────────────────────────────────────────
        info_lf = ttk.LabelFrame(win, text="Book", padding=6)
        info_lf.pack(fill="x", padx=12, pady=(0, 6))
        book_info_var = tk.StringVar(value="No EPUB loaded")
        ttk.Label(info_lf, textvariable=book_info_var,
                  style="Muted.TLabel", font=FONT_SMALL).pack(anchor="w")

        # ── chapter list ──────────────────────────────────────────────
        ch_lf = ttk.LabelFrame(win, text="Chapters", padding=6)
        ch_lf.pack(fill="x", padx=12, pady=(0, 6))

        ch_sb = ttk.Scrollbar(ch_lf, orient="vertical")
        ch_sb.pack(side="right", fill="y")
        ch_list = tk.Listbox(
            ch_lf, height=7, font=FONT_MONO, selectmode="extended",
            yscrollcommand=ch_sb.set,
            bg=self.colors["entry_bg"], fg=self.colors["fg"],
            selectbackground=self.colors["select_bg"],
            activestyle="none", borderwidth=0, highlightthickness=1,
            highlightcolor=self.colors["border"],
        )
        ch_list.pack(fill="x", expand=True)
        ch_sb.config(command=ch_list.yview)

        ch_ctrl = ttk.Frame(ch_lf)
        ch_ctrl.pack(fill="x", pady=(4, 0))
        sel_all_btn = ttk.Button(ch_ctrl, text="Select All",
                                 command=lambda: ch_list.selection_set(0, "end"))
        sel_all_btn.pack(side="left", padx=(0, 6))
        sel_none_btn = ttk.Button(ch_ctrl, text="Select None",
                                  command=lambda: ch_list.selection_clear(0, "end"))
        sel_none_btn.pack(side="left")
        ch_count_var = tk.StringVar(value="")
        ttk.Label(ch_ctrl, textvariable=ch_count_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(side="right")

        # ── settings ──────────────────────────────────────────────────
        set_lf = ttk.LabelFrame(win, text="Settings", padding=8)
        set_lf.pack(fill="x", padx=12, pady=(0, 6))

        sr = ttk.Frame(set_lf)
        sr.pack(fill="x", pady=(0, 4))
        ttk.Label(sr, text="Voice:", font=FONT_SMALL).pack(side="left")
        voice_name_str = (self.chosen_voice["ShortName"]
                          if self.chosen_voice else "No voice selected")
        ab_voice_var = tk.StringVar(value=voice_name_str)
        ttk.Label(sr, textvariable=ab_voice_var,
                  style="Blue.TLabel", font=FONT_SMALL).pack(side="left", padx=(6, 0))

        or_ = ttk.Frame(set_lf)
        or_.pack(fill="x")
        ttk.Label(or_, text="Output:", font=FONT_SMALL).pack(side="left")
        ab_out_var = tk.StringVar()
        ttk.Entry(or_, textvariable=ab_out_var, font=FONT_SMALL).pack(
            side="left", fill="x", expand=True, padx=6)

        def browse_ab_out():
            p = filedialog.asksaveasfilename(
                parent=win, defaultextension=".m4b",
                filetypes=[("M4B Audiobook", "*.m4b"), ("All Files", "*.*")])
            if p:
                ab_out_var.set(p)

        ttk.Button(or_, text="Browse…", command=browse_ab_out).pack(side="left")

        # ── progress ──────────────────────────────────────────────────
        prog_lf = ttk.LabelFrame(win, text="Progress", padding=8)
        prog_lf.pack(fill="x", padx=12, pady=(0, 6))

        ab_status_var = tk.StringVar(value="Load an EPUB to begin.")
        ttk.Label(prog_lf, textvariable=ab_status_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(anchor="w")
        ab_prog_var = tk.DoubleVar(value=0)
        ab_pbar = ttk.Progressbar(prog_lf, variable=ab_prog_var, maximum=100)
        ab_pbar.pack(fill="x", pady=(4, 0))

        # ── action bar ────────────────────────────────────────────────
        act = ttk.Frame(win, padding=(12, 4, 12, 10))
        act.pack(fill="x")
        convert_ab_btn = ttk.Button(act, text="Convert to Audiobook",
                                    style="Accent.TButton", state="disabled")
        convert_ab_btn.pack(side="left")
        ttk.Label(act,
                  text="Converts selected chapters; embeds chapter markers in output M4B.",
                  style="Muted.TLabel", font=FONT_CAPTION).pack(side="left", padx=(12, 0))

        # ── state ─────────────────────────────────────────────────────
        chapters_data = []   # list of (title, text)
        _running      = [False]

        def load_epub():
            path = filedialog.askopenfilename(
                parent=win,
                filetypes=[("EPUB Books", "*.epub"), ("All Files", "*.*")])
            if not path:
                return
            try:
                ab_status_var.set("Extracting chapters…")
                chs = self._epub_chapters(path)
                if not chs:
                    ab_status_var.set("No chapters found in this EPUB.")
                    return
                chapters_data.clear()
                chapters_data.extend(chs)
                ch_list.delete(0, "end")
                for i, (title, _) in enumerate(chs, 1):
                    ch_list.insert("end", f"{i:>3}.  {title}")
                ch_list.selection_set(0, "end")

                meta = self._epub_metadata(path)
                book_info_var.set(
                    f"{meta['title']}  —  {meta['author']}  "
                    f"({len(chs)} chapter(s))")
                ch_count_var.set(f"{len(chs)} chapter(s)")

                # Suggest output path
                stem = os.path.splitext(os.path.basename(path))[0]
                ab_out_var.set(os.path.join(os.path.dirname(path), stem + ".m4b"))
                convert_ab_btn.config(state="normal")
                ab_status_var.set(f"Loaded {len(chs)} chapters.  Select chapters and convert.")
            except Exception as err:
                ab_status_var.set(f"Error: {err}")

        def run_conversion():
            sel = ch_list.curselection()
            if not sel:
                ab_status_var.set("Select at least one chapter.")
                return
            if not ab_out_var.get():
                ab_status_var.set("Choose an output path first.")
                return
            if not self.chosen_voice:
                messagebox.showwarning(
                    "No Voice",
                    "Select a voice in the main window first.",
                    parent=win)
                return

            targets = [chapters_data[i] for i in sel]
            total   = len(targets)
            out     = ab_out_var.get()
            voice   = self.chosen_voice["ShortName"]
            rate    = f"{self.speed_var.get():+d}%"
            pitch   = f"{self.pitch_var.get():+d}Hz"
            volume  = f"{self.volume_var.get():+d}%"

            _running[0] = True
            convert_ab_btn.config(state="disabled")
            load_btn.config(state="disabled")

            def bg():
                chapter_mp3s   = []
                chapter_titles = []
                tmp_dir        = tempfile.mkdtemp()
                errors         = []

                for i, (title, text) in enumerate(targets, 1):
                    win.after(0, lambda t=title, n=i, tot=total:
                               ab_status_var.set(f"Converting chapter {n}/{tot}: {t}"))
                    ch_mp3 = os.path.join(tmp_dir, f"ch_{i:04d}.mp3")
                    try:
                        self._convert_to_audio_file(
                            text, voice, ch_mp3, "MP3",
                            rate=rate, pitch=pitch, volume=volume,
                            progress_cb=lambda p, n=i, tot=total: win.after(
                                0, lambda pct=int((n-1+p/100)/tot*100):
                                   ab_prog_var.set(pct)))
                        chapter_mp3s.append(ch_mp3)
                        chapter_titles.append(title)
                    except Exception as err:
                        errors.append(f"Chapter {i} ({title}): {err}")

                if not chapter_mp3s:
                    win.after(0, lambda: (
                        ab_status_var.set("All chapters failed — nothing to assemble."),
                        convert_ab_btn.config(state="normal"),
                        load_btn.config(state="normal")))
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    _running[0] = False
                    return

                win.after(0, lambda: ab_status_var.set("Assembling M4B with chapter markers…"))

                try:
                    self._assemble_m4b(chapter_mp3s, chapter_titles, out)
                    shutil.rmtree(tmp_dir, ignore_errors=True)

                    def done():
                        _running[0] = False
                        convert_ab_btn.config(state="normal")
                        load_btn.config(state="normal")
                        ab_prog_var.set(100)
                        kb = os.path.getsize(out) / 1024
                        ab_status_var.set(
                            f"Done! {os.path.basename(out)}  ({kb:.0f} KB)"
                            + (f"  —  {len(errors)} chapter error(s)" if errors else ""))
                        if errors:
                            messagebox.showwarning(
                                "Partial Success",
                                "Some chapters failed:\n" + "\n".join(errors),
                                parent=win)
                        elif messagebox.askyesno(
                                "Open Output", "Audiobook created. Open in Finder?",
                                parent=win):
                            subprocess.Popen(["open", "-R", out])

                    win.after(0, done)

                except Exception as err:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    _running[0] = False
                    win.after(0, lambda e=str(err): (
                        ab_status_var.set(f"Assembly failed: {e}"),
                        convert_ab_btn.config(state="normal"),
                        load_btn.config(state="normal")))

            threading.Thread(target=bg, daemon=True).start()

        load_btn.config(command=load_epub)
        convert_ab_btn.config(command=run_conversion)

    @staticmethod
    def _epub_chapters(path):
        """Return list of (title, text) for each non-empty EPUB chapter."""
        book     = _epub.read_epub(path, options={"ignore_ncx": True})
        chapters = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            for tag in soup(["script", "style"]):
                tag.decompose()
            heading = soup.find(["h1", "h2", "h3"])
            title   = heading.get_text().strip() if heading else item.get_name()
            text    = soup.get_text(separator="\n")
            text    = "\n".join(ln for ln in text.splitlines() if ln.strip())
            if text.strip():
                chapters.append((title, text))
        return chapters

    def _assemble_m4b(self, chapter_mp3s, chapter_titles, out_path):
        """Concatenate MP3 chapter files into a chapter-marked M4B."""
        tmp_dir = tempfile.mkdtemp()
        try:
            # Get durations via ffprobe
            durations = [self._get_audio_duration(p) for p in chapter_mp3s]

            # Build ffmpeg concat list
            concat_file = os.path.join(tmp_dir, "concat.txt")
            with open(concat_file, "w") as f:
                for mp3 in chapter_mp3s:
                    f.write(f"file '{mp3}'\n")

            # Build ffmetadata with chapter entries
            meta_file = os.path.join(tmp_dir, "meta.txt")
            with open(meta_file, "w", encoding="utf-8") as f:
                f.write(";FFMETADATA1\n")
                pos = 0.0
                for title, dur in zip(chapter_titles, durations):
                    start_ms = int(pos * 1000)
                    end_ms   = int((pos + dur) * 1000)
                    f.write(f"\n[CHAPTER]\nTIMEBASE=1/1000\n"
                            f"START={start_ms}\nEND={end_ms}\n"
                            f"title={title}\n")
                    pos += dur

            # Step 1: concat MP3s
            concat_mp3 = os.path.join(tmp_dir, "full.mp3")
            r = subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                 "-i", concat_file, "-acodec", "copy", concat_mp3],
                capture_output=True)
            if r.returncode != 0:
                raise RuntimeError(
                    "MP3 concat failed: " + r.stderr.decode(errors="replace")[:300])

            # Step 2: convert to M4B with chapter metadata
            r = subprocess.run(
                ["ffmpeg", "-y", "-i", concat_mp3, "-i", meta_file,
                 "-map_metadata", "1", "-acodec", "aac", "-b:a", "128k",
                 out_path],
                capture_output=True)
            if r.returncode != 0:
                raise RuntimeError(
                    "M4B assembly failed: " + r.stderr.decode(errors="replace")[:300])

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ── Voice Comparison Panel ────────────────────────────────────────

    def _open_voice_compare(self):
        """Side-by-side voice audition: generate the same passage in multiple voices."""
        win = tk.Toplevel(self.root)
        win.title("Voice Comparison")
        win.geometry("900x640")
        win.minsize(700, 480)
        win.transient(self.root)
        win.configure(bg=self.colors["bg"])

        # ── sample text bar ───────────────────────────────────────────
        txt_lf = ttk.LabelFrame(win, text="Sample Text", padding=6)
        txt_lf.pack(fill="x", padx=12, pady=(10, 6))

        sample_var = tk.StringVar(
            value=(self.text_area.get("1.0", "200c").strip()
                   or "Hello! This is a voice comparison sample. How does this sound to you?"))
        sample_entry = ttk.Entry(txt_lf, textvariable=sample_var, font=FONT_SMALL)
        sample_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        def from_editor():
            t = self.text_area.get("1.0", "end").strip()[:300]
            if t:
                sample_var.set(t)

        ttk.Button(txt_lf, text="↑ From Editor", command=from_editor).pack(side="left")

        # ── main split ────────────────────────────────────────────────
        split = ttk.PanedWindow(win, orient="horizontal")
        split.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        left_f  = ttk.LabelFrame(split, text="Available Voices", padding=4)
        right_f = ttk.LabelFrame(split, text="Comparison Queue  (up to 6)", padding=4)
        split.add(left_f,  weight=2)
        split.add(right_f, weight=3)

        # Left: voice picker
        lsb = ttk.Scrollbar(left_f)
        lsb.pack(side="right", fill="y")
        picker = tk.Listbox(
            left_f, font=FONT_MONO, selectmode="browse",
            yscrollcommand=lsb.set,
            bg=self.colors["entry_bg"], fg=self.colors["fg"],
            selectbackground=self.colors["select_bg"],
            activestyle="none", borderwidth=0, highlightthickness=1,
            highlightcolor=self.colors["border"],
        )
        picker.pack(fill="both", expand=True)
        lsb.config(command=picker.yview)

        for v in self.filtered_voices:
            dname = voice_display_name(v["ShortName"])
            picker.insert("end",
                f"{dname:<14} {v['Locale']:<9} {v['Gender'][0]}")

        # Right: comparison table
        comp_cols = ("voice", "locale", "status")
        comp_tree = ttk.Treeview(right_f, columns=comp_cols,
                                 show="headings", selectmode="browse")
        comp_tree.heading("voice",  text="Voice")
        comp_tree.heading("locale", text="Locale")
        comp_tree.heading("status", text="Status")
        comp_tree.column("voice",  width=130, stretch=True)
        comp_tree.column("locale", width=90,  stretch=False)
        comp_tree.column("status", width=120, stretch=False)
        rsb = ttk.Scrollbar(right_f, command=comp_tree.yview)
        comp_tree.configure(yscrollcommand=rsb.set)
        comp_tree.pack(side="left", fill="both", expand=True)
        rsb.pack(side="right", fill="y")

        # ── queue management ──────────────────────────────────────────
        mid_row = ttk.Frame(win, padding=(12, 0, 12, 4))
        mid_row.pack(fill="x")

        add_btn   = ttk.Button(mid_row, text="Add Voice →",
                               command=lambda: on_add())
        add_btn.pack(side="left", padx=(0, 6))
        rem_btn   = ttk.Button(mid_row, text="Remove Selected",
                               command=lambda: on_remove())
        rem_btn.pack(side="left", padx=(0, 6))
        clear_q_btn = ttk.Button(mid_row, text="Clear All",
                                 command=lambda: on_clear())
        clear_q_btn.pack(side="left")

        # ── action bar ────────────────────────────────────────────────
        act = ttk.Frame(win, padding=(12, 0, 12, 10))
        act.pack(fill="x")
        gen_btn  = ttk.Button(act, text="▶  Generate & Play All",
                              style="Accent.TButton", command=lambda: on_generate())
        gen_btn.pack(side="left", padx=(0, 8))
        play_sel_btn = ttk.Button(act, text="▶  Play Selected",
                                  command=lambda: on_play_selected())
        play_sel_btn.pack(side="left", padx=(0, 8))
        stop_btn = ttk.Button(act, text="⏹  Stop",
                              command=lambda: on_stop())
        stop_btn.pack(side="left")
        cmp_status_var = tk.StringVar(value="Add voices, then click Generate & Play All.")
        ttk.Label(act, textvariable=cmp_status_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(side="left", padx=(12, 0))

        # ── state ─────────────────────────────────────────────────────
        queue      = []   # list of voice dicts
        previews   = {}   # voice short name → temp mp3 path
        _proc      = [None]
        _gen_flag  = [False]
        MAX_QUEUE  = 6

        def set_status(vid, status):
            for iid in comp_tree.get_children():
                if comp_tree.set(iid, "voice") == voice_display_name(vid):
                    comp_tree.set(iid, "status", status)
                    break

        def on_add():
            sel = picker.curselection()
            if not sel:
                return
            v = self.filtered_voices[sel[0]]
            if len(queue) >= MAX_QUEUE:
                cmp_status_var.set(f"Queue is full ({MAX_QUEUE} voices max).")
                return
            if any(q["ShortName"] == v["ShortName"] for q in queue):
                cmp_status_var.set("Voice already in queue.")
                return
            queue.append(v)
            comp_tree.insert("", "end", values=(
                voice_display_name(v["ShortName"]), v["Locale"], "Pending"))
            cmp_status_var.set(f"{len(queue)} voice(s) in queue.")

        def on_remove():
            sel = comp_tree.selection()
            if not sel:
                return
            idx = comp_tree.index(sel[0])
            v   = queue[idx]
            if v["ShortName"] in previews:
                try:
                    os.unlink(previews.pop(v["ShortName"]))
                except OSError:
                    pass
            del queue[idx]
            comp_tree.delete(sel[0])

        def on_clear():
            for iid in list(comp_tree.get_children()):
                comp_tree.delete(iid)
            for p in previews.values():
                try:
                    os.unlink(p)
                except OSError:
                    pass
            previews.clear()
            queue.clear()
            cmp_status_var.set("Queue cleared.")

        def on_stop():
            _gen_flag[0] = False
            if _proc[0]:
                try:
                    _proc[0].terminate()
                except OSError:
                    pass
                _proc[0] = None
            cmp_status_var.set("Stopped.")

        def on_play_selected():
            sel = comp_tree.selection()
            if not sel:
                return
            idx = comp_tree.index(sel[0])
            v   = queue[idx]
            path = previews.get(v["ShortName"])
            if not path or not os.path.isfile(path):
                cmp_status_var.set("Not yet generated — click Generate & Play All first.")
                return
            if _proc[0]:
                try:
                    _proc[0].terminate()
                except OSError:
                    pass
            _proc[0] = subprocess.Popen(["afplay", path])
            cmp_status_var.set(f"Playing: {voice_display_name(v['ShortName'])}")

        def on_generate():
            if not queue:
                cmp_status_var.set("Add voices first.")
                return
            sample = sample_var.get().strip()
            if not sample:
                cmp_status_var.set("Enter sample text first.")
                return

            gen_btn.config(state="disabled")
            _gen_flag[0] = True

            def bg():
                rate  = f"{self.speed_var.get():+d}%"
                pitch = f"{self.pitch_var.get():+d}Hz"
                vol   = f"{self.volume_var.get():+d}%"
                total = len(queue)

                for i, v in enumerate(list(queue)):
                    if not _gen_flag[0]:
                        break
                    vname = v["ShortName"]
                    win.after(0, lambda vn=vname:
                               set_status(vn, "Generating…"))
                    win.after(0, lambda n=i+1, t=total, dn=voice_display_name(vname):
                               cmp_status_var.set(f"Generating {n}/{t}: {dn}"))

                    try:
                        t = tempfile.NamedTemporaryFile(
                            suffix=".mp3", delete=False)
                        t.close()
                        tmp = t.name
                        if v.get("Backend", "edge_tts") == "macos":
                            self._synthesize_macos(sample, vname, tmp,
                                                   rate=rate, pitch=pitch, volume=vol)
                        else:
                            run_async(edge_tts.Communicate(
                                sample, vname,
                                rate=rate, pitch=pitch, volume=vol
                            ).save(tmp))

                        if os.path.isfile(tmp) and os.path.getsize(tmp) > 0:
                            # Clean up old preview
                            if vname in previews:
                                try:
                                    os.unlink(previews[vname])
                                except OSError:
                                    pass
                            previews[vname] = tmp
                            win.after(0, lambda vn=vname:
                                       set_status(vn, "✓ Ready"))
                        else:
                            win.after(0, lambda vn=vname:
                                       set_status(vn, "✗ No audio"))

                    except Exception as err:
                        win.after(0, lambda vn=vname, e=str(err):
                                   set_status(vn, f"✗ Error"))

                if not _gen_flag[0]:
                    win.after(0, lambda: gen_btn.config(state="normal"))
                    return

                # Play all in sequence
                def play_sequence():
                    for v in list(queue):
                        if not _gen_flag[0]:
                            break
                        vname = v["ShortName"]
                        path  = previews.get(vname)
                        if not path or not os.path.isfile(path):
                            continue
                        win.after(0, lambda dn=voice_display_name(vname):
                                   cmp_status_var.set(f"Playing: {dn}"))
                        _proc[0] = subprocess.Popen(["afplay", path])
                        _proc[0].wait()
                        _proc[0] = None

                    win.after(0, lambda: (
                        gen_btn.config(state="normal"),
                        cmp_status_var.set("Playback complete.")))
                    _gen_flag[0] = False

                threading.Thread(target=play_sequence, daemon=True).start()

            threading.Thread(target=bg, daemon=True).start()

    # ── Quality / processing settings helpers ────────────────────────

    def _refresh_quality_options(self):
        fmt    = self.format_var.get()
        presets = QUALITY_PRESETS.get(fmt, [])
        labels  = [p[0] for p in presets]
        self.quality_cb.config(values=labels)
        if labels:
            cur = self.quality_var.get()
            if cur not in labels:
                self.quality_var.set(labels[0])
            self.quality_cb.config(state="readonly")
        else:
            self.quality_var.set("")
            self.quality_cb.config(state="disabled")

    def _save_proc_settings(self):
        self.settings["normalize_text"]  = self.normalize_text_var.get()
        self.settings["normalize_audio"] = self.normalize_audio_var.get()
        self.settings["clean_pdf"]       = self.clean_pdf_var.get()
        self.settings["para_pause"]      = self.para_pause_var.get()
        self.settings["quality"]         = self.quality_var.get()
        self._save_settings()

    # ── Font size ─────────────────────────────────────────────────────

    def _font_size_up(self):
        self.font_size_var.set(min(24, self.font_size_var.get() + 1))
        self._apply_font_size()

    def _font_size_down(self):
        self.font_size_var.set(max(8, self.font_size_var.get() - 1))
        self._apply_font_size()

    def _apply_font_size(self):
        sz = self.font_size_var.get()
        self.text_area.config(font=("SF Pro Text", sz))
        self.settings["font_size"] = sz
        self._save_settings()

    # ── macOS say synthesis ───────────────────────────────────────────

    def _synthesize_macos(self, text, voice_name, out_path,
                          rate="+0%", pitch="+0Hz", volume="+0%"):
        """
        Synthesise *text* using the macOS `say` command and write an MP3 to
        *out_path*.  The native output is AIFF; we convert via ffmpeg if
        available, otherwise keep as AIFF and rename.
        rate/pitch/volume follow the edge_tts "+N%" convention; macOS `say`
        uses -r (words/min) so we do a rough conversion.
        """
        # Parse rate offset: "+20%" means 20% faster than baseline 175 wpm
        wpm = 175
        try:
            pct = int(rate.rstrip("%"))
            wpm = max(80, min(500, int(175 * (1 + pct / 100))))
        except ValueError:
            pass

        # Strip locale prefix from voice name for `say -v`
        say_name = voice_name
        if ":" in voice_name:
            say_name = voice_name.split(":", 1)[1]
        # macOS voices stored as "macos:Alex" → strip prefix
        if say_name.startswith("macos."):
            say_name = say_name[6:]

        aiff_fd, aiff_tmp = tempfile.mkstemp(suffix=".aiff", dir=CONVERSION_CACHE_DIR)
        os.close(aiff_fd)
        try:
            txt_fd, txt_tmp = tempfile.mkstemp(suffix=".txt", dir=CONVERSION_CACHE_DIR)
            try:
                with os.fdopen(txt_fd, "w", encoding="utf-8") as tf:
                    tf.write(text)
                result = subprocess.run(
                    ["say", "-v", say_name, "-r", str(wpm), "-f", txt_tmp, "-o", aiff_tmp],
                    capture_output=True)
                if result.returncode != 0:
                    raise RuntimeError(
                        "say command failed: "
                        + result.stderr.decode(errors="replace")[:300])
            finally:
                try:
                    os.unlink(txt_tmp)
                except OSError:
                    pass

            if not os.path.isfile(aiff_tmp) or os.path.getsize(aiff_tmp) == 0:
                raise RuntimeError("macOS say produced no audio output.")

            if self.ffmpeg:
                res = subprocess.run(
                    ["ffmpeg", "-y", "-i", aiff_tmp,
                     "-acodec", "libmp3lame", "-b:a", "192k", out_path],
                    capture_output=True)
                if res.returncode != 0:
                    raise RuntimeError(
                        "ffmpeg AIFF→MP3 failed: "
                        + res.stderr.decode(errors="replace")[:300])
            else:
                shutil.copy2(aiff_tmp, out_path)
        finally:
            try:
                os.unlink(aiff_tmp)
            except OSError:
                pass

    # ── Silence clip generator ────────────────────────────────────────

    def _make_silence_clip(self, duration_secs, out_path):
        """Generate a silent MP3 clip of *duration_secs* seconds via ffmpeg."""
        subprocess.run(
            ["ffmpeg", "-y",
             "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
             "-t", str(duration_secs),
             "-acodec", "libmp3lame", "-b:a", "128k",
             out_path],
            capture_output=True, check=True)

    # ── Metadata embedding ────────────────────────────────────────────

    def _embed_metadata(self, out_path, fmt, title="", author="", cover_path=None):
        """Embed ID3/MP4 metadata (and optional cover art) into *out_path* in-place."""
        if not self.ffmpeg:
            return
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
        except Exception:
            pass
        finally:
            if os.path.isfile(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    # ── EPUB cover extraction ─────────────────────────────────────────

    def _extract_epub_cover(self, epub_path):
        """Return a temp file path containing the EPUB cover image, or None."""
        try:
            book = _epub.read_epub(epub_path)
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_COVER or \
                        "cover" in (item.get_name() or "").lower():
                    if item.media_type and item.media_type.startswith("image/"):
                        suffix = ".jpg" if "jpeg" in item.media_type else ".png"
                        fd, tmp = tempfile.mkstemp(suffix=suffix,
                                                   dir=CONVERSION_CACHE_DIR)
                        with os.fdopen(fd, "wb") as f:
                            f.write(item.get_content())
                        return tmp
        except Exception:
            pass
        return None

    # ── OCR for image-based PDFs ──────────────────────────────────────

    def _ocr_pdf(self, path):
        """Run tesseract OCR on each page of a PDF and return extracted text."""
        if not _HAS_FITZ:
            return ""
        text_parts = []
        try:
            doc = fitz.open(path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix  = page.get_pixmap(dpi=200)
                img_fd, img_tmp = tempfile.mkstemp(suffix=".png",
                                                   dir=CONVERSION_CACHE_DIR)
                os.close(img_fd)
                try:
                    pix.save(img_tmp)
                    txt_fd, txt_tmp = tempfile.mkstemp(dir=CONVERSION_CACHE_DIR)
                    os.close(txt_fd)
                    os.unlink(txt_tmp)   # tesseract adds .txt itself
                    res = subprocess.run(
                        ["tesseract", img_tmp, txt_tmp, "-l", "eng"],
                        capture_output=True)
                    out_file = txt_tmp + ".txt"
                    if res.returncode == 0 and os.path.isfile(out_file):
                        with open(out_file, "r", encoding="utf-8", errors="replace") as f:
                            text_parts.append(f.read())
                        os.unlink(out_file)
                finally:
                    try:
                        os.unlink(img_tmp)
                    except OSError:
                        pass
        except Exception as e:
            return f"[OCR error: {e}]"
        return "\n\n".join(text_parts)

    # ── Conversion history ────────────────────────────────────────────

    def _record_history(self, entry):
        records = []
        try:
            with open(HISTORY_FILE) as f:
                records = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        records.append(entry)
        with open(HISTORY_FILE, "w") as f:
            json.dump(records[-500:], f, indent=2)   # keep last 500 entries

    def _open_history_dialog(self):
        records = []
        try:
            with open(HISTORY_FILE) as f:
                records = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        win = tk.Toplevel(self.root)
        win.title("Conversion History")
        win.geometry("860x480")
        win.transient(self.root)
        win.configure(bg=self.colors["bg"])

        cols = ("timestamp", "voice", "format", "chars", "output")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c, w, lbl in [("timestamp", 140, "Time"), ("voice", 180, "Voice"),
                           ("format", 60, "Fmt"), ("chars", 70, "Chars"),
                           ("output", 340, "Output file")]:
            tree.heading(c, text=lbl)
            tree.column(c, width=w, anchor="w")
        sb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        for r in reversed(records):
            tree.insert("", "end", values=(
                r.get("timestamp", ""),
                r.get("voice", ""),
                r.get("format", ""),
                r.get("chars", ""),
                r.get("output", ""),
            ))

        btn_row = ttk.Frame(win, padding=(8, 4))
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Reveal Selected",
                   command=lambda: self._history_reveal(tree, records)).pack(side="left")
        ttk.Button(btn_row, text="Clear History",
                   command=lambda: self._history_clear(tree)).pack(side="left", padx=8)
        ttk.Button(btn_row, text="Close",
                   command=win.destroy).pack(side="right")

    def _history_reveal(self, tree, records):
        sel = tree.selection()
        if not sel:
            return
        idx = len(records) - 1 - tree.index(sel[0])
        path = records[idx].get("output", "")
        if path and os.path.isfile(path):
            subprocess.Popen(["open", "-R", path])

    def _history_clear(self, tree):
        if messagebox.askyesno("Clear History",
                               "Delete all conversion history entries?"):
            try:
                os.unlink(HISTORY_FILE)
            except OSError:
                pass
            for iid in tree.get_children():
                tree.delete(iid)

    # ── Project file (.tts2mp3) ───────────────────────────────────────

    def _new_project(self):
        self.current_project_path = None
        self._clear_text()
        self.output_path.set("")
        self.root.title("TTS2MP3 Studio")

    def _open_project(self, _=None):
        path = filedialog.askopenfilename(
            title="Open Project",
            filetypes=[("TTS2MP3 Project", f"*{PROJECT_EXT}"), ("All Files", "*.*")])
        if not path:
            return
        try:
            with open(path) as f:
                proj = json.load(f)
        except Exception as e:
            messagebox.showerror("Open Project", f"Cannot read project file:\n{e}")
            return
        self.current_project_path = path
        _set_text(self.text_area, proj.get("text", ""))
        self.output_path.set(proj.get("output_path", ""))
        voice_id = proj.get("voice")
        if voice_id:
            self._select_voice_by_id(voice_id)
        for var, key in [(self.speed_var, "speed"), (self.pitch_var, "pitch"),
                         (self.volume_var, "volume")]:
            if key in proj:
                var.set(proj[key])
        self.format_var.set(proj.get("format", "MP3"))
        self._on_format_change()
        self._source_meta = proj.get("source_meta", {})
        self._update_word_count()
        self.root.title(f"TTS2MP3 Studio — {os.path.basename(path)}")

    def _save_project(self, _=None):
        if self.current_project_path:
            self._write_project(self.current_project_path)
        else:
            self._save_project_as()

    def _save_project_as(self, _=None):
        path = filedialog.asksaveasfilename(
            title="Save Project As",
            defaultextension=PROJECT_EXT,
            filetypes=[("TTS2MP3 Project", f"*{PROJECT_EXT}")])
        if not path:
            return
        self.current_project_path = path
        self._write_project(path)
        self.root.title(f"TTS2MP3 Studio — {os.path.basename(path)}")

    def _write_project(self, path):
        proj = {
            "text":        self.text_area.get("1.0", "end-1c"),
            "output_path": self.output_path.get(),
            "voice":       self.chosen_voice["ShortName"] if self.chosen_voice else None,
            "speed":       self.speed_var.get(),
            "pitch":       self.pitch_var.get(),
            "volume":      self.volume_var.get(),
            "format":      self.format_var.get(),
            "source_meta": getattr(self, "_source_meta", {}),
        }
        try:
            with open(path, "w") as f:
                json.dump(proj, f, indent=2)
        except Exception as e:
            messagebox.showerror("Save Project", f"Could not save:\n{e}")

    # ── Find & Replace ────────────────────────────────────────────────

    def _open_find_replace(self, _=None):
        win = tk.Toplevel(self.root)
        win.title("Find & Replace")
        win.geometry("480x160")
        win.resizable(False, False)
        win.transient(self.root)
        win.configure(bg=self.colors["bg"])

        grid = ttk.Frame(win, padding=12)
        grid.pack(fill="both", expand=True)

        ttk.Label(grid, text="Find:",    font=FONT_SMALL).grid(row=0, column=0, sticky="e", padx=(0, 6))
        ttk.Label(grid, text="Replace:", font=FONT_SMALL).grid(row=1, column=0, sticky="e", padx=(0, 6), pady=(6, 0))

        find_var    = tk.StringVar()
        replace_var = tk.StringVar()
        ttk.Entry(grid, textvariable=find_var,    width=36,
                  font=FONT_SMALL).grid(row=0, column=1, sticky="ew")
        ttk.Entry(grid, textvariable=replace_var, width=36,
                  font=FONT_SMALL).grid(row=1, column=1, sticky="ew", pady=(6, 0))
        grid.columnconfigure(1, weight=1)

        count_var = tk.StringVar()
        ttk.Label(grid, textvariable=count_var,
                  style="Muted.TLabel", font=FONT_CAPTION).grid(
            row=2, column=1, sticky="w", pady=(6, 0))

        def do_replace():
            needle = find_var.get()
            if not needle:
                return
            content = self.text_area.get("1.0", "end-1c")
            n = content.count(needle)
            if n == 0:
                count_var.set("No matches found.")
                return
            new_content = content.replace(needle, replace_var.get())
            _set_text(self.text_area, new_content)
            self._update_word_count()
            count_var.set(f"Replaced {n} occurrence(s).")

        btn_row = ttk.Frame(grid)
        btn_row.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btn_row, text="Replace All",
                   command=do_replace).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Close",
                   command=win.destroy).pack(side="left")

    # ── Watch Folder daemon ───────────────────────────────────────────

    def _open_watch_folder(self):
        win = tk.Toplevel(self.root)
        win.title("Watch Folder")
        win.geometry("560x320")
        win.transient(self.root)
        win.configure(bg=self.colors["bg"])

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Watch Folder",
                  style="Section.TLabel").pack(anchor="w", pady=(0, 8))

        in_var  = tk.StringVar(value=self.settings.get("watch_in",  ""))
        out_var = tk.StringVar(value=self.settings.get("watch_out", ""))

        def browse(var, title):
            d = filedialog.askdirectory(title=title)
            if d:
                var.set(d)

        for label, var, btn_title in [
            ("Input folder:",  in_var,  "Select Input Folder"),
            ("Output folder:", out_var, "Select Output Folder"),
        ]:
            r = ttk.Frame(frm)
            r.pack(fill="x", pady=3)
            ttk.Label(r, text=label, font=FONT_SMALL, width=14).pack(side="left")
            ttk.Entry(r, textvariable=var, font=FONT_SMALL).pack(
                side="left", fill="x", expand=True, padx=4)
            ttk.Button(r, text="Browse…",
                       command=lambda v=var, t=btn_title: browse(v, t)).pack(side="left")

        status_var = tk.StringVar(value="Idle")
        ttk.Label(frm, textvariable=status_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(anchor="w", pady=(8, 0))

        def start_watch():
            in_dir  = in_var.get().strip()
            out_dir = out_var.get().strip()
            if not in_dir or not os.path.isdir(in_dir):
                messagebox.showwarning("Watch Folder", "Select a valid input folder.")
                return
            if not out_dir:
                messagebox.showwarning("Watch Folder", "Select an output folder.")
                return
            os.makedirs(out_dir, exist_ok=True)
            self.settings["watch_in"]  = in_dir
            self.settings["watch_out"] = out_dir
            self._save_settings()
            self._watch_active = True
            self._watch_thread = threading.Thread(
                target=self._watch_folder_loop,
                args=(in_dir, out_dir, status_var, win),
                daemon=True)
            self._watch_thread.start()
            start_btn.config(state="disabled")
            stop_btn.config(state="normal")

        def stop_watch():
            self._watch_active = False
            status_var.set("Stopping…")
            start_btn.config(state="normal")
            stop_btn.config(state="disabled")

        btn_row = ttk.Frame(frm)
        btn_row.pack(anchor="w", pady=(12, 0))
        start_btn = ttk.Button(btn_row, text="Start Watching", command=start_watch)
        start_btn.pack(side="left", padx=(0, 8))
        stop_btn  = ttk.Button(btn_row, text="Stop", command=stop_watch, state="disabled")
        stop_btn.pack(side="left")

        if self._watch_active:
            start_btn.config(state="disabled")
            stop_btn.config(state="normal")
            status_var.set("Already running…")

    def _watch_folder_loop(self, in_dir, out_dir, status_var, win):
        seen = set(os.listdir(in_dir))
        EXTS = {".txt", ".rtf", ".epub", ".pdf", ".md"}
        while self._watch_active:
            try:
                current = set(os.listdir(in_dir))
                new     = current - seen
                for fname in sorted(new):
                    if not self._watch_active:
                        break
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in EXTS:
                        continue
                    in_path = os.path.join(in_dir, fname)
                    stem    = os.path.splitext(fname)[0]
                    fmt     = self.format_var.get()
                    out_ext = EXPORT_FORMATS[fmt][0]
                    out_path = os.path.join(out_dir, stem + out_ext)
                    win.after(0, lambda f=fname:
                               status_var.set(f"Converting: {f}"))
                    try:
                        text = self._read_file(in_path)
                        if self.chosen_voice:
                            rate   = f"{self.speed_var.get():+d}%"
                            pitch  = f"{self.pitch_var.get():+d}Hz"
                            volume = f"{self.volume_var.get():+d}%"
                            self._convert_to_audio_file(
                                text, self.chosen_voice["ShortName"],
                                out_path, fmt,
                                rate=rate, pitch=pitch, volume=volume)
                            win.after(0, lambda f=fname:
                                       status_var.set(f"Done: {f}"))
                    except Exception as e:
                        win.after(0, lambda f=fname, err=str(e):
                                   status_var.set(f"Error ({f}): {err[:60]}"))
                seen = current
            except Exception:
                pass
            time.sleep(3)
        win.after(0, lambda: status_var.set("Stopped."))

    # ── Podcast RSS export ────────────────────────────────────────────

    def _open_podcast_rss(self):
        win = tk.Toplevel(self.root)
        win.title("Podcast RSS Export")
        win.geometry("560x420")
        win.transient(self.root)
        win.configure(bg=self.colors["bg"])

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Podcast RSS Export",
                  style="Section.TLabel").pack(anchor="w", pady=(0, 8))

        fields = {}
        for label, key, default in [
            ("Feed title:",       "title",       "My Podcast"),
            ("Author:",           "author",      ""),
            ("Description:",      "description", ""),
            ("Base URL:",         "base_url",    "https://example.com/podcast/"),
            ("Output folder:",    "out_dir",     ""),
        ]:
            r = ttk.Frame(frm)
            r.pack(fill="x", pady=3)
            ttk.Label(r, text=label, font=FONT_SMALL, width=14).pack(side="left")
            var = tk.StringVar(value=self.settings.get(f"rss_{key}", default))
            fields[key] = var
            if key == "out_dir":
                ttk.Entry(r, textvariable=var, font=FONT_SMALL).pack(
                    side="left", fill="x", expand=True, padx=4)
                ttk.Button(r, text="Browse…",
                           command=lambda v=var: v.set(
                               filedialog.askdirectory() or v.get())
                           ).pack(side="left")
            else:
                ttk.Entry(r, textvariable=var, font=FONT_SMALL).pack(
                    side="left", fill="x", expand=True, padx=4)

        status_var = tk.StringVar()
        ttk.Label(frm, textvariable=status_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(anchor="w", pady=(8, 0))

        def generate():
            out_dir  = fields["out_dir"].get().strip()
            base_url = fields["base_url"].get().strip().rstrip("/") + "/"
            title    = fields["title"].get().strip() or "Podcast"
            author   = fields["author"].get().strip()
            desc     = fields["description"].get().strip()

            if not out_dir or not os.path.isdir(out_dir):
                messagebox.showwarning("RSS Export", "Select a valid output folder.")
                return

            # Collect audio files
            audio_exts = {".mp3", ".m4a", ".m4b", ".ogg", ".opus"}
            items = sorted(
                f for f in os.listdir(out_dir)
                if os.path.splitext(f)[1].lower() in audio_exts)

            if not items:
                status_var.set("No audio files found in that folder.")
                return

            lines = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">',
                '  <channel>',
                f'    <title>{title}</title>',
                f'    <itunes:author>{author}</itunes:author>',
                f'    <description>{desc}</description>',
                f'    <link>{base_url}</link>',
            ]
            for fname in items:
                stem   = os.path.splitext(fname)[0]
                fpath  = os.path.join(out_dir, fname)
                size   = os.path.getsize(fpath)
                url    = base_url + fname
                ext    = os.path.splitext(fname)[1].lower()
                mime   = {"mp3": "audio/mpeg", "m4a": "audio/mp4",
                          "m4b": "audio/mp4", "ogg": "audio/ogg",
                          "opus": "audio/ogg"}.get(ext.lstrip("."), "audio/mpeg")
                lines += [
                    '    <item>',
                    f'      <title>{stem}</title>',
                    f'      <enclosure url="{url}" length="{size}" type="{mime}"/>',
                    f'      <guid>{url}</guid>',
                    '    </item>',
                ]
            lines += ["  </channel>", "</rss>"]

            rss_path = os.path.join(out_dir, "feed.rss")
            try:
                with open(rss_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                status_var.set(f"Saved: {rss_path}  ({len(items)} episode(s))")
                for k, v in fields.items():
                    self.settings[f"rss_{k}"] = v.get()
                self._save_settings()
            except Exception as e:
                status_var.set(f"Error: {e}")

        ttk.Button(frm, text="Generate RSS Feed",
                   command=generate).pack(anchor="w", pady=(8, 0))

    # ── Multi-voice character assignment ──────────────────────────────

    def _open_character_voices(self):
        win = tk.Toplevel(self.root)
        win.title("Character Voices")
        win.geometry("700x520")
        win.transient(self.root)
        win.configure(bg=self.colors["bg"])

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Character Voices",
                  style="Section.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Label(frm,
                  text="Assign different TTS voices to named characters in your text.\n"
                       "Pattern: lines starting with  CHARACTER: dialogue",
                  style="Muted.TLabel", font=FONT_CAPTION).pack(anchor="w", pady=(0, 8))

        # Detect characters from text
        text = self.text_area.get("1.0", "end-1c")
        chars = sorted(set(
            m.group(1).strip()
            for m in re.finditer(r'^([A-Z][A-Z\s]{1,24}):', text, re.MULTILINE)
            if len(m.group(1).strip()) >= 2
        ))

        assignments = {}   # char → voice ShortName
        rows_frame = ttk.Frame(frm)
        rows_frame.pack(fill="x")

        voice_names = [v["ShortName"] for v in self.all_voices]
        default_voice = self.chosen_voice["ShortName"] if self.chosen_voice else (
            voice_names[0] if voice_names else "")

        for char in chars:
            r = ttk.Frame(rows_frame)
            r.pack(fill="x", pady=2)
            ttk.Label(r, text=f"{char}:", font=FONT_SMALL, width=20,
                      anchor="e").pack(side="left", padx=(0, 6))
            var = tk.StringVar(value=default_voice)
            assignments[char] = var
            cb = ttk.Combobox(r, textvariable=var, values=voice_names,
                              width=32, state="readonly", font=FONT_SMALL)
            cb.pack(side="left")

        if not chars:
            ttk.Label(rows_frame,
                      text="No CHARACTER: patterns detected in the current text.",
                      style="Muted.TLabel", font=FONT_SMALL).pack(anchor="w")

        status_var = tk.StringVar()
        ttk.Label(frm, textvariable=status_var,
                  style="Muted.TLabel", font=FONT_CAPTION).pack(anchor="w", pady=(8, 0))

        def do_convert():
            if not chars:
                return
            if not self.ffmpeg:
                messagebox.showwarning("Character Voices",
                                       "ffmpeg is required for multi-voice export.")
                return
            out = filedialog.asksaveasfilename(
                title="Save Multi-Voice Audio",
                defaultextension=".mp3",
                filetypes=[("MP3", "*.mp3")])
            if not out:
                return

            def bg():
                try:
                    tmp_dir    = tempfile.mkdtemp(dir=CONVERSION_CACHE_DIR)
                    seg_files  = []
                    # Parse text into (char, line) segments
                    default_char = "__narrator__"
                    segments     = []
                    for line in text.splitlines():
                        m = re.match(r'^([A-Z][A-Z\s]{1,24}):\s*(.*)', line)
                        if m and m.group(1).strip() in assignments:
                            segments.append((m.group(1).strip(), m.group(2).strip()))
                        elif line.strip():
                            segments.append((default_char, line.strip()))

                    total = len(segments)
                    rate   = f"{self.speed_var.get():+d}%"
                    pitch  = f"{self.pitch_var.get():+d}Hz"
                    volume = f"{self.volume_var.get():+d}%"

                    for i, (char, seg_text) in enumerate(segments):
                        if not seg_text:
                            continue
                        vname = (assignments[char].get()
                                 if char in assignments else default_voice)
                        seg_path = os.path.join(tmp_dir, f"seg_{i:05d}.mp3")
                        self._convert_to_audio_file(
                            seg_text, vname, seg_path, "MP3",
                            rate=rate, pitch=pitch, volume=volume)
                        seg_files.append(seg_path)
                        win.after(0, lambda n=i+1, t=total:
                                   status_var.set(f"Segment {n}/{t}…"))

                    # Concat all segments
                    clist = os.path.join(tmp_dir, "concat.txt")
                    with open(clist, "w") as cf:
                        for sf in seg_files:
                            cf.write(f"file '{sf}'\n")
                    subprocess.run(
                        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                         "-i", clist, "-acodec", "copy", out],
                        capture_output=True, check=True)
                    win.after(0, lambda: status_var.set(
                        f"Saved: {os.path.basename(out)}"))
                except Exception as e:
                    win.after(0, lambda err=str(e):
                               status_var.set(f"Error: {err[:80]}"))
                finally:
                    shutil.rmtree(tmp_dir, ignore_errors=True)

            threading.Thread(target=bg, daemon=True).start()

        btn_row = ttk.Frame(frm)
        btn_row.pack(anchor="w", pady=(12, 0))
        ttk.Button(btn_row, text="Export Multi-Voice Audio…",
                   command=do_convert).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Close",
                   command=win.destroy).pack(side="left")



if __name__ == "__main__":
    if _HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    TTS2MP3App(root)
    root.mainloop()

# TTS2MP3 Studio

A full-featured macOS text-to-speech studio that converts text, documents, and ebooks into high-quality audio files — completely offline or with cloud voices.

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Platform](https://img.shields.io/badge/platform-macOS-lightgrey) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

### Voices
- **300+ cloud voices** via Microsoft Edge TTS — neural voices across 50+ languages and locales
- **All macOS offline voices** via the system `say` command — works with zero internet
- Automatic fallback: if the network is unavailable, macOS voices are always available
- Voice preview with live text sample (uses current speed/pitch/volume settings)
- Voice comparison tool — queue up to 6 voices and audition them back-to-back
- Favorites system with one-click offline caching
- Filter by language, gender, or favorites; full-text search across all voices

### Input Formats
- Plain text (`.txt`)
- Rich Text Format (`.rtf`)
- EPUB ebooks (`.epub`) — with automatic chapter detection and metadata extraction
- PDF documents (`.pdf`) — with artifact cleanup (page numbers, headers, hyphenated line breaks)
- Markdown (`.md`) — syntax stripped before synthesis
- OCR fallback for image-based PDFs via [Tesseract](https://github.com/tesseract-ocr/tesseract)
- Drag-and-drop file loading
- Paste from clipboard

### Output Formats
| Format | Extension | Notes |
|--------|-----------|-------|
| MP3 | `.mp3` | Standard (128k), High (192k), Maximum (320k) |
| WAV | `.wav` | Uncompressed PCM |
| FLAC | `.flac` | Lossless |
| AAC | `.m4a` | Standard (128k), High (192k) |
| Audiobook | `.m4b` | With chapter markers |
| OGG Vorbis | `.ogg` | Standard (q4), High (q7) |
| Opus | `.opus` | Standard (96k), High (128k), Maximum (192k) |

### Processing Pipeline
- **Text normalisation** — expands `$1,200` → "one thousand two hundred dollars", `75%` → "seventy-five percent", ISO dates → natural language, comma-formatted numbers
- **Pronunciation dictionary** — custom find-and-replace rules applied before synthesis (e.g. "TTS" → "T T S")
- **Paragraph pause injection** — insert configurable silence (0.5s / 1s / 2s) between paragraphs
- **Audio normalisation** — post-process with `ffmpeg loudnorm` for consistent volume
- **Chunked synthesis** — long texts are split at paragraph/sentence boundaries; each chunk is synthesised independently and concatenated
- **Per-chunk retry** — up to 3 attempts with exponential backoff; partial output saved if a later chunk fails
- **Content-addressed cache** — SHA-256 keyed cache means repeated conversions are instant

### Audiobook Builder (M4B)
- Load an EPUB and auto-detect chapters, or manually compose a chapter list
- Each chapter synthesised separately and assembled into a single `.m4b` with chapter markers
- Cover art extracted from EPUB and embedded into the output file
- ID3/MP4 metadata embedding — title, author, album artist, cover image

### Batch Converter
- Queue multiple files (TXT, RTF, EPUB, PDF, Markdown) for sequential conversion
- Per-file and overall progress bars
- Output naming mirrors source file names
- Custom output folder or same-folder-as-source

### Watch Folder
- Background daemon monitors an input folder for new files
- Automatically converts any new document and writes audio to an output folder
- Supports all input formats; uses the currently selected voice and settings

### Project Files
- Save and restore complete session state — text, voice, speed/pitch/volume, output path, source metadata — as a `.tts2mp3` project file
- Full macOS keyboard shortcut support (`⌘N`, `⌘O`, `⌘S`, `⌘⇧S`)

### Additional Tools
- **Find & Replace** — search and replace text in the editor before synthesis (`⌘H`)
- **Multi-voice character voices** — detect `CHARACTER:` patterns in your text, assign different voices to each character, and export a merged audio file
- **Podcast RSS export** — point at a folder of audio files and generate a valid RSS 2.0/iTunes feed
- **Conversion history** — append-only log of every conversion with timestamp, voice, format, and output path
- **Inline playback** — play the output directly in the app with a seek bar, pause/resume, and time display
- **Dark mode** — full light/dark theme support

---

## Requirements

| Dependency | Purpose | Required |
|------------|---------|----------|
| Python 3.10+ | Runtime | Yes |
| [edge-tts](https://github.com/rany2/edge-tts) | Cloud TTS voices | Yes |
| [PyMuPDF](https://pymupdf.readthedocs.io/) (`fitz`) | PDF extraction | Yes |
| [ebooklib](https://github.com/aerkalov/ebooklib) | EPUB parsing | Yes |
| [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) | HTML parsing | Yes |
| [striprtf](https://github.com/joshy/striprtf) | RTF parsing | Yes |
| [tkinterdnd2](https://github.com/pmgagne/tkinterdnd2) | Drag-and-drop | Optional |
| [ffmpeg](https://ffmpeg.org/) | Format conversion, concat, loudnorm | Strongly recommended |
| [Tesseract](https://github.com/tesseract-ocr/tesseract) | OCR for image PDFs | Optional |
| macOS `say` | Offline TTS | Built-in on macOS |

---

## Installation

```bash
# Clone the repo
git clone https://github.com/jacobavery/TTS2MP3.git
cd TTS2MP3

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install edge-tts PyMuPDF ebooklib beautifulsoup4 striprtf

# Optional: drag-and-drop support
pip install tkinterdnd2

# Install ffmpeg (strongly recommended)
brew install ffmpeg

# Optional: OCR support for image-based PDFs
brew install tesseract

# Launch
python main.py
```

---

## Usage

1. **Select a voice** — browse the voice list on the left, preview with a single click, then press **Use This Voice**
2. **Load text** — open a file, paste from clipboard, or drag and drop a document onto the window
3. **Set output path** — click **Browse…** or type a path; the extension updates automatically when you change format
4. **Convert** — click **Convert to Audio**; a live progress bar and time-remaining estimate appear in the status bar
5. **Play or reveal** — use the inline player or **Open in App** / **Show in Finder** buttons

### Offline Use

Switch to any **⊕** macOS voice in the voice list — these use the system `say` command and require no internet connection. Cloud voices are marked **☁**.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `⌘N` | New project |
| `⌘O` | Open project |
| `⌘S` | Save project |
| `⌘⇧S` | Save project as… |
| `⌘H` | Find & Replace |
| `⌘R` | Convert to audio |

---

## Project Structure

```
TTS2MP3/
├── main.py          # Entire application (~5000 lines)
├── .gitignore
└── README.md
```

Runtime files created on first launch (gitignored):

```
.tts_cache/          # Conversion and preview cache
.tts_settings.json   # User preferences
.tts_favorites.json  # Favorited voices
.tts_pronunciations.json
.tts_history.json    # Conversion log
```

---

## License

MIT

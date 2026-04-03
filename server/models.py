"""Pydantic request/response schemas."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ConvertRequest(BaseModel):
    text: str
    voice: str
    format: str = "MP3"
    quality: str = ""
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"
    normalize_text: bool = False
    normalize_audio: bool = False
    para_pause: float = 0.0
    pronunciations: List[Dict] = Field(default_factory=list)


class ConvertResponse(BaseModel):
    job_id: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int = 0
    error: Optional[str] = None
    download_url: Optional[str] = None


class VoiceItem(BaseModel):
    ShortName: str
    Locale: str
    Gender: str
    Backend: str = "edge_tts"
    Description: str = ""
    VoiceTag: Dict = Field(default_factory=dict)


class VoicesResponse(BaseModel):
    voices: List[VoiceItem]
    count: int


class UploadResponse(BaseModel):
    text: str
    filename: str
    words: int
    chars: int
    metadata: Dict = Field(default_factory=dict)


class PronunciationEntry(BaseModel):
    find: str
    replace: str
    whole_word: bool = False


class SettingsUpdate(BaseModel):
    settings: Dict


class FavoritesUpdate(BaseModel):
    favorites: List[str]


class FavoriteToggle(BaseModel):
    voice: str


class SystemStatus(BaseModel):
    ffmpeg: bool
    tesseract: bool
    cache_size_mb: float
    voice_count: int
    macos_voices: bool


class HistoryRecord(BaseModel):
    timestamp: str
    voice: str
    format: str
    output: str = ""
    chars: int = 0
    chunks: int = 0


class BatchItem(BaseModel):
    filename: str
    text: str


class BatchRequest(BaseModel):
    items: List[BatchItem]
    voice: str
    format: str = "MP3"
    quality: str = ""
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"
    normalize_text: bool = False
    normalize_audio: bool = False
    para_pause: float = 0.0


class BatchResponse(BaseModel):
    batch_id: str
    job_ids: List[str]


class CharacterDetectRequest(BaseModel):
    text: str


class CharacterConvertRequest(BaseModel):
    text: str
    assignments: Dict[str, str]
    default_voice: str
    format: str = "MP3"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"


class CompareRequest(BaseModel):
    text: str
    voices: List[str] = Field(max_length=6)


class ProjectSave(BaseModel):
    text: str
    voice: str
    speed: int = 0
    pitch: int = 0
    volume: int = 0
    format: str = "MP3"
    source_meta: Dict = Field(default_factory=dict)
    name: str = "Untitled"


class PodcastRssRequest(BaseModel):
    title: str = "Podcast"
    author: str = ""
    description: str = ""
    base_url: str
    audio_dir: str

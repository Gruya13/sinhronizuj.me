from pydantic import BaseModel
from typing import List, Optional

class UserRegisterRequest(BaseModel):
    email: str
    password: str

class UserLoginRequest(BaseModel):
    email: str
    password: str

class WaitlistRequest(BaseModel):
    email: str

class VideoRequest(BaseModel):
    url: str
    debug: bool = False
    project_id: Optional[str] = None

class CreateProjectRequest(BaseModel):
    name: str

class SegmentItem(BaseModel):
    id: int
    start: float
    end: float
    original: str
    translated: str
    tts_path: Optional[str] = None
    tts_duration: Optional[float] = None
    status: Optional[str] = "draft"
    voice_type: Optional[str] = "clone"
    volume: Optional[float] = 0.0
    speed: Optional[float] = 1.0
    pitch: Optional[float] = 0.0
    bg_volume: Optional[float] = 0.0
    active_speaker: Optional[bool] = True

class SaveProjectRequest(BaseModel):
    segments: List[SegmentItem]

class SegmentTTSRequest(BaseModel):
    text: str
    voice_type: str = "clone"
    volume: float = 0.0
    speed: float = 1.0
    pitch: float = 0.0
    bg_volume: float = 0.0

class ShortenSegmentRequest(BaseModel):
    text: str

class GenerateAllTTSRequest(BaseModel):
    voice_type: str = "clone"

class RenderRequest(BaseModel):
    voice_type: str = "clone"
    background_volume: float = -5.0
    dubbed_volume: float = 0.0

class MixerSettingsRequest(BaseModel):
    background_volume: float
    dubbed_volume: float

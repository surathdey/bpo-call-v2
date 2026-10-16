from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)]

DISPOSITIONS = ["RPI_CONFIRMED", "WRONG_PARTY", "NO_ANSWER_VOICEMAIL", "FAILED_NUMBER"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc):
        return cls.model_validate(doc) if doc else None

    def to_mongo(self) -> dict:
        data = self.model_dump(exclude={"id"})
        if self.id:
            data["_id"] = ObjectId(self.id)
        return data


class Campaign(BaseDocument):
    name: str
    description: str = ""
    status: str = "draft"  # draft | running | paused | completed
    language: str = "en-US"
    voice_gender: str = "female"
    voice_id: str = ""
    prompt: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    launched_at: Optional[str] = None


class Contact(BaseDocument):
    campaign_id: str
    name: str
    phone: str
    raw_phone: str = ""
    customer_id: str = ""
    language: str = "en-US"
    status: str = "pending"  # pending | queued | calling | completed
    disposition: Optional[str] = None
    review_required: bool = False
    attempts: int = 0
    last_attempt_id: Optional[str] = None
    last_called_at: Optional[str] = None
    last_ended_reason: Optional[str] = None
    last_duration: Optional[float] = None
    last_recording_url: Optional[str] = None
    warnings: List[str] = []
    created_at: str = Field(default_factory=now_iso)


class Classification(BaseModel):
    source: str = "rules"  # rules | llm | provider
    confidence: float = 0.0
    reasoning: str = ""
    ai_classified: bool = False
    raw_disposition: Optional[str] = None


class CallAttempt(BaseDocument):
    campaign_id: str
    contact_id: str
    attempt_number: int = 1
    mode: str = "simulation"
    customer_name: str = ""
    phone: str = ""
    language: str = "en-US"
    voice_id: str = ""
    opening_line: str = ""
    provider_call_id: Optional[str] = None
    provider_status: str = "initiated"
    ended_reason: Optional[str] = None
    disposition: Optional[str] = None
    review_required: bool = False
    classification: Optional[Classification] = None
    transcript: List[Dict[str, Any]] = []
    transcript_text: str = ""
    recording_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    finalized: bool = False
    webhook_events: int = 0
    created_at: str = Field(default_factory=now_iso)
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    finalized_at: Optional[str] = None


class AuditLog(BaseDocument):
    event: str
    entity_type: str = ""
    entity_id: str = ""
    campaign_id: Optional[str] = None
    details: Dict[str, Any] = {}
    actor: str = "supervisor"
    created_at: str = Field(default_factory=now_iso)


class VoiceProfile(BaseModel):
    language: str
    gender: str
    voice_id: str
    label: str = ""


DEFAULT_VOICES = [
    VoiceProfile(language="en-US", gender="female", voice_id="21m00Tcm4TlvDq8ikWAM", label="Rachel"),
    VoiceProfile(language="en-US", gender="male", voice_id="pNInz6obpgDQGcFmaJgB", label="Adam"),
    VoiceProfile(language="es-US", gender="female", voice_id="EXAVITQu4vr4xnSDxMaL", label="Sarah (multilingual)"),
    VoiceProfile(language="es-US", gender="male", voice_id="ErXwobaYiN019PkySvjV", label="Antoni (multilingual)"),
    VoiceProfile(language="fr-CA", gender="female", voice_id="XB0fDUnXU5powFXDhCwa", label="Charlotte (multilingual)"),
    VoiceProfile(language="fr-CA", gender="male", voice_id="onwK4e9ZLuTAKqWW03F9", label="Daniel (multilingual)"),
]


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_mode: str = "simulation"  # simulation | live
    vapi_api_key_encrypted: str = ""
    vapi_api_key_last4: str = ""
    phone_number_id: str = ""
    webhook_base_url: str = ""
    webhook_token: str = ""
    vapi_model_provider: str = "openai"
    vapi_model: str = "gpt-4o"
    elevenlabs_model: str = "eleven_turbo_v2_5"
    company_name: str = "RevLoop"
    default_language: str = "en-US"
    default_voice_gender: str = "female"
    default_prompt: str = "Be warm, brief and professional. Speak clearly and at a calm pace."
    voice_profiles: List[VoiceProfile] = Field(default_factory=lambda: list(DEFAULT_VOICES))
    max_retries: int = 2
    max_concurrent_calls: int = 3
    max_call_duration_seconds: int = 120
    confirm_confidence_threshold: float = 0.8
    default_region: str = "US"
    dnc_numbers: List[str] = []
    enforce_calling_hours: bool = False
    calling_hours_start: int = 9
    calling_hours_end: int = 21
    calling_timezone: str = "America/Toronto"
    updated_at: Optional[str] = None


class SettingsUpdate(BaseModel):
    call_mode: Optional[str] = None
    vapi_api_key: Optional[str] = None
    phone_number_id: Optional[str] = None
    webhook_base_url: Optional[str] = None
    vapi_model_provider: Optional[str] = None
    vapi_model: Optional[str] = None
    elevenlabs_model: Optional[str] = None
    company_name: Optional[str] = None
    default_language: Optional[str] = None
    default_voice_gender: Optional[str] = None
    default_prompt: Optional[str] = None
    voice_profiles: Optional[List[VoiceProfile]] = None
    max_retries: Optional[int] = Field(default=None, ge=0, le=10)
    max_concurrent_calls: Optional[int] = Field(default=None, ge=1, le=50)
    max_call_duration_seconds: Optional[int] = Field(default=None, ge=30, le=900)
    confirm_confidence_threshold: Optional[float] = Field(default=None, ge=0.5, le=1.0)
    default_region: Optional[str] = None
    dnc_numbers: Optional[List[str]] = None
    enforce_calling_hours: Optional[bool] = None
    calling_hours_start: Optional[int] = Field(default=None, ge=0, le=23)
    calling_hours_end: Optional[int] = Field(default=None, ge=1, le=24)
    calling_timezone: Optional[str] = None


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    language: Optional[str] = None
    voice_gender: Optional[str] = None
    voice_id: str = ""
    prompt: Optional[str] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    voice_gender: Optional[str] = None
    voice_id: Optional[str] = None
    prompt: Optional[str] = None


class RetryRequest(BaseModel):
    dispositions: List[str] = ["FAILED_NUMBER", "NO_ANSWER_VOICEMAIL"]
    contact_ids: List[str] = []
    ignore_retry_limit: bool = False

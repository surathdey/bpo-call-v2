from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PyObjectId = Annotated[str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)]

from defaults import (DEFAULT_DISPOSITIONS, DEFAULT_EMOTION, DEFAULT_SCRIPTS, DEFAULT_STATE_RULES,  # noqa: E402
                      DEFAULT_VOICE_PROFILES, DISPOSITION_CODES)

DISPOSITIONS = DISPOSITION_CODES
UNREACHED_STATUSES = ["no-answer", "voicemail", "busy", "failed"]


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
    agent_name: str = ""
    language: str = ""
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
    bank_name: str = ""
    state: str = ""
    language: str = ""
    status: str = "pending"  # pending | queued | calling | completed
    last_call_status: Optional[str] = None
    last_category: Optional[str] = None
    last_summary: Optional[str] = None
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
    bank_name: str = ""
    state: str = ""
    agent_name: str = ""
    language: str = ""
    voice_id: str = ""
    opening_line: str = ""
    call_status: Optional[str] = None  # completed | no-answer | voicemail | busy | failed
    category: Optional[str] = None
    summary: str = ""
    agent_disposition: Optional[str] = None
    agent_summary: str = ""
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
    label: str
    female_voice_id: str = ""
    male_voice_id: str = ""
    tts_model: str = "eleven_multilingual_v2"
    stt_provider: str = "deepgram"
    stt_model: str = "nova-3"
    stt_language: str = ""


class StateRule(BaseModel):
    state: str = Field(min_length=1)
    language: str


class DispositionDef(BaseModel):
    code: str
    category: str = ""
    description: str = ""
    close: str = "denial_close"


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
    default_agent_name: str = ""
    fallback_language: str = "hi-IN"
    state_language_rules: List[StateRule] = Field(default_factory=lambda: [StateRule(**r) for r in DEFAULT_STATE_RULES])
    default_voice_gender: str = "female"
    default_prompt: str = "Keep the call short and respectful."
    emotion_guidelines: str = DEFAULT_EMOTION
    voice_stability: float = 0.4
    voice_style: float = 0.35
    voice_profiles: List[VoiceProfile] = Field(default_factory=lambda: [VoiceProfile(**v) for v in DEFAULT_VOICE_PROFILES])
    script_templates: Dict[str, Dict[str, str]] = Field(default_factory=lambda: {k: dict(v) for k, v in DEFAULT_SCRIPTS.items()})
    dispositions: List[DispositionDef] = Field(default_factory=lambda: [DispositionDef(**d) for d in DEFAULT_DISPOSITIONS])
    unreached_disposition: str = "Final Denial Closing"
    max_retries: int = 2
    max_concurrent_calls: int = 3
    max_call_duration_seconds: int = 120
    confirm_confidence_threshold: float = 0.8
    default_region: str = "IN"
    dnc_numbers: List[str] = []
    enforce_calling_hours: bool = False
    calling_hours_start: int = 9
    calling_hours_end: int = 21
    calling_timezone: str = "Asia/Kolkata"
    updated_at: Optional[str] = None


class SettingsUpdate(BaseModel):
    call_mode: Optional[str] = None
    vapi_api_key: Optional[str] = None
    phone_number_id: Optional[str] = None
    webhook_base_url: Optional[str] = None
    vapi_model_provider: Optional[str] = None
    vapi_model: Optional[str] = None
    default_agent_name: Optional[str] = None
    fallback_language: Optional[str] = None
    state_language_rules: Optional[List[StateRule]] = None
    default_voice_gender: Optional[str] = None
    default_prompt: Optional[str] = None
    emotion_guidelines: Optional[str] = None
    voice_stability: Optional[float] = Field(default=None, ge=0, le=1)
    voice_style: Optional[float] = Field(default=None, ge=0, le=1)
    voice_profiles: Optional[List[VoiceProfile]] = None
    script_templates: Optional[Dict[str, Dict[str, str]]] = None
    dispositions: Optional[List[DispositionDef]] = None
    unreached_disposition: Optional[str] = None
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
    agent_name: str = Field(min_length=1, max_length=40)
    voice_gender: Optional[str] = None
    prompt: Optional[str] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    agent_name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    voice_gender: Optional[str] = None
    prompt: Optional[str] = None


class RetryRequest(BaseModel):
    call_statuses: List[str] = UNREACHED_STATUSES
    dispositions: List[str] = []
    contact_ids: List[str] = []
    ignore_retry_limit: bool = False

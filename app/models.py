from pydantic import BaseModel, Field
from typing import Literal, Optional
from enum import Enum


# Enums for constrained values
class TimeOfDay(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"


class Pressure(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class Interruptibility(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RoleSignal(str, Enum):
    PROFESSIONAL = "professional"
    PERSONAL = "personal"
    MIXED = "mixed"


class RoleType(str, Enum):
    PROFESSIONAL = "professional"
    PERSONAL = "personal"
    CASUAL = "casual"


class Tone(str, Enum):
    PROFESSIONAL = "professional"
    WARM = "warm"
    CASUAL = "casual"


class Verbosity(str, Enum):
    CONCISE = "concise"
    BALANCED = "balanced"


class Hedging(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Time Context (Section 4.1)
class TimeContext(BaseModel):
    current_iso: str
    time_of_day: TimeOfDay
    weekday: bool
    business_hours: bool
    urgency_bias: float = Field(ge=0.0, le=1.0)


# Calendar Context (Section 4.2)
class CalendarContextAvailable(BaseModel):
    summary: str
    pressure: Pressure
    interruptibility: Interruptibility
    role_signal: RoleSignal
    confidence: float = Field(ge=0.0, le=1.0)


class CalendarContextUnavailable(BaseModel):
    status: Literal["unavailable"] = "unavailable"


# Role Guess (Section 4.3)
class RoleProbabilities(BaseModel):
    professional: float = Field(ge=0.0, le=1.0)
    personal: float = Field(ge=0.0, le=1.0)
    casual: float = Field(ge=0.0, le=1.0)


class RoleGuess(BaseModel):
    roles: RoleProbabilities
    primary_role: RoleType
    confidence: float = Field(ge=0.0, le=1.0)


# Lens Schema (Section 5.1)
class ResponsePreferences(BaseModel):
    tone: Tone
    verbosity: Verbosity
    hedging: Hedging


class SituationalContext(BaseModel):
    time_of_day: TimeOfDay
    urgency: Urgency
    interruptibility: Interruptibility


class Lens(BaseModel):
    active_role: RoleType
    role_confidence: float = Field(ge=0.0, le=1.0)
    response_preferences: ResponsePreferences
    situational_context: SituationalContext
    sources_used: list[str]


# API Request/Response Models (Section 8)
class QueryRequest(BaseModel):
    query: str
    preview_lens: bool = False
    calendar_token: Optional[str] = None


class QueryResponse(BaseModel):
    response: str
    lens: Lens
    regenerated: bool
    model: str
    warning: Optional[str] = None


class LensPreviewRequest(BaseModel):
    query: str
    calendar_token: Optional[str] = None


class LensPreviewResponse(BaseModel):
    lens: Lens
    sources_used: list[str]


# Internal models for calendar events
class CalendarEvent(BaseModel):
    start_time: str
    end_time: str
    category: str
    attendee_count: int


# Drift detection result
class DriftResult(BaseModel):
    drift_detected: bool
    drift_type: Optional[Literal["over_certainty", "sycophancy", "ignored_context"]] = None
    modifier: Optional[str] = None

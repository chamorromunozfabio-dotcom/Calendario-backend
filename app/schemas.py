from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

FlowIntensity = Literal["ligero", "moderado", "abundante", "muy_abundante"]
Mood = Literal["muy_bajo", "bajo", "neutral", "bien", "muy_bien"]
Tone = Literal["tranquilo", "alegre", "motivador", "reflexivo"]


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=80)
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    timezone: str | None = Field(default=None, max_length=60)


class CycleSettingsUpdate(BaseModel):
    usual_cycle_length: int | None = Field(default=None, ge=15, le=60)
    usual_period_length: int | None = Field(default=None, ge=1, le=15)
    luteal_phase_length: int | None = Field(default=14, ge=9, le=18)
    last_period_start: date | None = None
    birth_control: bool | None = None
    onboarding_completed: bool | None = None


class EntryCreate(BaseModel):
    start_date: date
    end_date: date | None = None
    flow_intensity: FlowIntensity | None = None
    pain_level: int | None = Field(default=None, ge=0, le=10)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("end_date")
    @classmethod
    def _check_range(cls, v, info):
        start = info.data.get("start_date")
        if v is not None and start is not None and v < start:
            raise ValueError("end_date no puede ser anterior a start_date")
        if start is not None and (start - date.today()).days > 1:
            raise ValueError("start_date no puede estar en el futuro")
        return v


class EntryUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    flow_intensity: FlowIntensity | None = None
    pain_level: int | None = Field(default=None, ge=0, le=10)
    notes: str | None = Field(default=None, max_length=2000)


class LogCreate(BaseModel):
    log_date: date
    mood: Mood | None = None
    energy: int | None = Field(default=None, ge=1, le=5)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    stress: int | None = Field(default=None, ge=1, le=5)
    symptoms: list[str] = Field(default_factory=list, max_length=30)
    routine_changes: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("symptoms")
    @classmethod
    def _sym_len(cls, v):
        return [s[:60] for s in v][:30]


class AIRecommendRequest(BaseModel):
    focus: Literal["bienestar", "nutricion", "descanso", "educativa"] = "bienestar"
    cycle_day: int | None = Field(default=None, ge=1, le=80)
    free_text: str | None = Field(default=None, max_length=500)


class AISupportRequest(BaseModel):
    tone: Tone = "tranquilo"
    mood: Mood | None = None
    free_text: str | None = Field(default=None, max_length=300)


class FavoriteCreate(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    tone: Tone = "tranquilo"


class InvitationCreate(BaseModel):
    share_mood: bool = False
    share_phase_only: bool = True
    share_symptoms: bool = False
    expires_hours: int = Field(default=48, ge=1, le=168)
    max_uses: int = Field(default=1, ge=1, le=5)


class InvitationAccept(BaseModel):
    code: str = Field(min_length=8, max_length=128)


class ConsentCreate(BaseModel):
    purpose: str = Field(min_length=3, max_length=120)
    granted: bool
    version: str = Field(default="v1", max_length=20)

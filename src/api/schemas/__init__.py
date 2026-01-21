"""API Pydantic schemas."""
from datetime import datetime
from pydantic import BaseModel, Field, validator

# Framework Schemas
class FrameworkCreateWeb(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., max_length=500)
    labels: list[str] = Field(..., min_items=1)

    @validator("labels")
    def validate_labels(cls, v):
        if len(v) < 1:
            raise ValueError("At least one label is required")
        return v

class FrameworkUpdateWeb(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = Field(None, max_length=500)
    labels: list[str] | None = None

class AdminFrameworkResponse(BaseModel):
    id: int
    name: str
    description: str | None
    labels_json: str
    created_at: datetime | None = None

    class Config:
        from_attributes = True

# Scenario Schemas
class ScenarioCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    prompt: str = Field(..., min_length=10, max_length=10000)
    student_profile: str = Field(..., min_length=3, max_length=5000)
    framework_id: int
    is_active: bool = True

    # Video fields
    video_url: str | None = None
    video_transcript: str | None = None

    # Bot overrides (Phase 2)
    chat_model: str | None = "gpt-4-turbo"
    chat_temperature: float | None = 0.7
    tutor_enabled: bool = False
    tutor_intervention_threshold: int | None = 3

class ScenarioUpdate(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=200)
    prompt: str | None = Field(None, min_length=10, max_length=10000)
    student_profile: str | None = Field(None, min_length=3, max_length=5000)
    framework_id: int | None = None
    is_active: int | None = Field(None, ge=0, le=1)  # Admin UI sends 0/1

    # Video fields
    video_url: str | None = None
    video_transcript: str | None = None

    # Bot overrides
    chat_model: str | None = None
    chat_temperature: float | None = None
    tutor_enabled: bool | None = None
    tutor_intervention_threshold: int | None = None

class AdminScenarioResponse(BaseModel):
    id: int
    title: str
    prompt: str
    student_profile: str
    framework_id: int
    is_active: int

    # Video fields
    video_url: str | None = None
    video_transcript: str | None = None

    # Bot overrides
    chat_model: str | None = None
    chat_temperature: float | None = None
    tutor_enabled: int | None = None
    tutor_intervention_threshold: int | None = None

    created_at: object | None = None
    updated_at: object | None = None

    class Config:
        from_attributes = True


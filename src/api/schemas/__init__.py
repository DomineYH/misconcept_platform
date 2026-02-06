"""API Pydantic schemas."""
from datetime import datetime
from pydantic import BaseModel, Field, validator

from src.api.schemas.user import (
    UserCreate,
    UserUpdate,
    AdminUserResponse,
)
from src.api.schemas.group import (
    GroupCreate,
    GroupUpdate,
    AdminGroupResponse,
)

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
    tutor_intervention_threshold: int | None = 3

    # Template selection (Phase 2.5)
    student_template_id: int  # Required
    tutor_template_id: int | None = None  # None = tutor disabled

    # Group assignment
    group_ids: list[int] | None = None

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
    tutor_intervention_threshold: int | None = None

    # Template selection
    student_template_id: int | None = None
    tutor_template_id: int | None = None

    # Group assignment
    group_ids: list[int] | None = None

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
    tutor_intervention_threshold: int | None = None

    # Template selection
    student_template_id: int
    tutor_template_id: int | None = None

    created_at: object | None = None
    updated_at: object | None = None

    @property
    def tutor_enabled(self) -> bool:
        """Backward compatibility: tutor enabled if template assigned."""
        return self.tutor_template_id is not None

    class Config:
        from_attributes = True


__all__ = [
    "FrameworkCreateWeb",
    "FrameworkUpdateWeb",
    "AdminFrameworkResponse",
    "ScenarioCreate",
    "ScenarioUpdate",
    "AdminScenarioResponse",
    "UserCreate",
    "UserUpdate",
    "AdminUserResponse",
    "GroupCreate",
    "GroupUpdate",
    "AdminGroupResponse",
]

"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    detail: str
    status_code: int


class LoginRequest(BaseModel):
    """Login request payload."""

    student_uid: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Student unique identifier",
    )
    nickname: str = Field(
        ...,
        min_length=2,
        max_length=30,
        description="Display name",
    )


class ScenarioResponse(BaseModel):
    """Scenario list item response."""

    id: int
    title: str
    student_profile: Optional[str] = None


class SessionCreateRequest(BaseModel):
    """Session creation request."""

    scenario_id: int


class SessionResponse(BaseModel):
    """Session response."""

    id: int
    scenario_id: int
    teacher_id: int
    started_at: datetime
    ended_at: Optional[datetime] = None


class MessageRequest(BaseModel):
    """Message creation request."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Message content",
    )


class MessageResponse(BaseModel):
    """Message response."""

    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime


class QuestionAnalysisResponse(BaseModel):
    """Question analysis response."""

    id: int
    message_id: int
    label: str
    confidence: Optional[float] = None


class SessionSummaryResponse(BaseModel):
    """Session summary response."""

    id: int
    session_id: int
    distribution_json: str
    feedback: Optional[str] = None
    created_at: datetime


# Admin Scenario Management Schemas
class ScenarioCreate(BaseModel):
    """Schema for creating a scenario."""

    title: str = Field(..., min_length=3, max_length=200)
    prompt: str = Field(..., min_length=10, max_length=10000)
    student_profile: str = Field(..., min_length=3, max_length=5000)
    framework_id: int
    is_active: bool = Field(default=True)

    # Phase 2: Bot configuration overrides (all optional)
    chat_model: Optional[str] = Field(
        None,
        pattern=r"^gpt-(3\.5|4|4o|4o-mini)(-turbo)?$",
        description="Override StudentBot model (NULL = global)",
    )
    chat_temperature: Optional[float] = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Override temperature 0.0-2.0 (NULL = global)",
    )
    tutor_enabled: bool = Field(
        default=True, description="Enable/disable TutorBot"
    )
    tutor_intervention_threshold: Optional[int] = Field(
        None,
        ge=1,
        le=10,
        description="Override interventions per 10 questions",
    )

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        """Ensure title is not just whitespace."""
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

    @field_validator("prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        """Ensure prompt is not just whitespace."""
        if not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v.strip()


class ScenarioUpdate(BaseModel):
    """Schema for updating a scenario."""

    title: Optional[str] = Field(None, min_length=3, max_length=200)
    prompt: Optional[str] = Field(
        None, min_length=10, max_length=10000
    )
    student_profile: Optional[str] = Field(
        None, min_length=3, max_length=5000
    )
    framework_id: Optional[int] = None
    is_active: Optional[int] = Field(None, ge=0, le=1)

    # Phase 2: Bot configuration overrides (all optional)
    chat_model: Optional[str] = Field(
        None, pattern=r"^gpt-(3\.5|4|4o|4o-mini)(-turbo)?$"
    )
    chat_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    tutor_enabled: Optional[bool] = None
    tutor_intervention_threshold: Optional[int] = Field(
        None, ge=1, le=10
    )


class AdminScenarioResponse(BaseModel):
    """Schema for admin scenario response."""

    model_config = {"from_attributes": True}

    id: int
    title: str
    prompt: str
    student_profile: str
    framework_id: int
    is_active: int

    # Phase 2: Bot configuration overrides
    chat_model: Optional[str] = None
    chat_temperature: Optional[float] = None
    tutor_enabled: bool = True
    tutor_intervention_threshold: Optional[int] = None


# Admin Framework Management Schemas (Web UI)
class FrameworkCreateWeb(BaseModel):
    """Schema for creating framework via web UI."""

    name: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    labels: list[str] = Field(..., min_length=2, max_length=20)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Ensure name is not just whitespace."""
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        """Ensure description is not just whitespace."""
        if not v.strip():
            raise ValueError("Description cannot be empty")
        return v.strip()

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, v: list[str]) -> list[str]:
        """Validate labels list."""
        if len(v) < 2:
            raise ValueError("At least 2 labels required")
        if len(v) > 20:
            raise ValueError("Maximum 20 labels allowed")
        for label in v:
            if len(label) < 2:
                raise ValueError(f"Label '{label}' too short (min 2 chars)")
            if len(label) > 50:
                raise ValueError(f"Label '{label}' too long (max 50 chars)")
        return v


class FrameworkUpdateWeb(BaseModel):
    """Schema for updating framework via web UI."""

    name: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(
        None, min_length=10, max_length=5000
    )
    labels: Optional[list[str]] = Field(
        None, min_length=2, max_length=20
    )

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure name is not just whitespace if provided."""
        if v is not None and not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip() if v else None

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure description is not just whitespace if provided."""
        if v is not None and not v.strip():
            raise ValueError("Description cannot be empty")
        return v.strip() if v else None

    @field_validator("labels")
    @classmethod
    def validate_labels(
        cls, v: Optional[list[str]]
    ) -> Optional[list[str]]:
        """Validate labels list if provided."""
        if v is None:
            return None
        if len(v) < 2:
            raise ValueError("At least 2 labels required")
        if len(v) > 20:
            raise ValueError("Maximum 20 labels allowed")
        for label in v:
            if len(label) < 2:
                raise ValueError(f"Label '{label}' too short (min 2 chars)")
            if len(label) > 50:
                raise ValueError(f"Label '{label}' too long (max 50 chars)")
        return v


class AdminFrameworkResponse(BaseModel):
    """Schema for admin framework response."""

    model_config = {"from_attributes": True}

    id: int
    name: str
    description: str
    labels_json: str

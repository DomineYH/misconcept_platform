"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


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

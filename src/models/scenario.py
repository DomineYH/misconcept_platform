"""Scenario model for dialogue situations (T024)."""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Float,
    Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.connection import Base


class Scenario(Base):
    """Dialogue scenario with misconception and problem context.

    Phase 2 Extension: Supports per-scenario chatbot configuration override.
    NULL values in chat_* and tutor_* fields mean "use global config".
    """

    __tablename__ = "scenario"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Scenario identity
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # System prompt
    student_profile: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Video fields
    video_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    video_transcript: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Status
    is_active: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )  # Boolean as int

    # Phase 2: Scenario-specific chatbot configuration override
    chat_model: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment=(
            "Override StudentBot model for this scenario "
            "(NULL = use global)"
        ),
    )

    chat_temperature: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Override temperature 0.0-2.0 (NULL = use global)",
    )

    tutor_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Enable/disable TutorBot for this scenario",
    )

    tutor_intervention_threshold: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "Override tutor interventions per 10 questions "
            "(NULL = use global)"
        ),
    )

    # Foreign keys
    framework_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("analysis_framework.id"), nullable=False
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )

    # Relationships
    framework: Mapped["AnalysisFramework"] = relationship(
        "AnalysisFramework", back_populates="scenarios"
    )
    creator: Mapped["User"] = relationship(
        "User", back_populates="scenarios"
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="scenario"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("is_active IN (0, 1)", name="ck_scenario_active"),
    )

    def __repr__(self) -> str:
        config = (
            f"model={self.chat_model or 'global'}, "
            f"tutor={'on' if self.tutor_enabled else 'off'}"
        )
        status = "deleted" if self.deleted_at else "active"
        return (
            f"<Scenario(id={self.id}, "
            f"title={self.title[:30]}, "
            f"{config}, {status})>"
        )

    def mark_deleted(self) -> None:
        """Mark scenario as soft-deleted with UTC timestamp."""
        self.deleted_at = datetime.utcnow()

"""Scenario model for dialogue situations (T024)."""
from datetime import datetime
from sqlalchemy import (
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.connection import Base


class Scenario(Base):
    """Dialogue scenario with misconception and problem context."""

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

    # Status
    is_active: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )  # Boolean as int

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
        return f"<Scenario(id={self.id}, title={self.title[:30]})>"

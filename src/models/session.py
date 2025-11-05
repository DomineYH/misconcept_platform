"""Session model for dialogue instances (T025)."""
from datetime import datetime
from sqlalchemy import Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.connection import Base


class Session(Base):
    """Teacher-student dialogue session instance."""

    __tablename__ = "session"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign keys
    scenario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scenario.id"), nullable=False
    )
    teacher_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=False
    )

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # Relationships
    scenario: Mapped["Scenario"] = relationship(
        "Scenario", back_populates="sessions"
    )
    teacher: Mapped["User"] = relationship(
        "User", back_populates="sessions", foreign_keys=[teacher_id]
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    summary: Mapped["SessionSummary"] = relationship(  # noqa: F821
        "SessionSummary", back_populates="session", uselist=False
    )

    # Indexes
    __table_args__ = (
        Index("ix_session_teacher_started", "teacher_id", "started_at"),
        Index("ix_session_ended", "ended_at"),
    )

    @property
    def is_active(self) -> bool:
        """Check if session is still active (not ended)."""
        return self.ended_at is None

    def __repr__(self) -> str:
        status = "active" if self.is_active else "ended"
        return f"<Session(id={self.id}, status={status})>"

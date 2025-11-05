"""Message model for dialogue turns (T026)."""
from datetime import datetime
from sqlalchemy import (
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.connection import Base


class Message(Base):
    """Individual dialogue message from teacher, student, or tutor."""

    __tablename__ = "message"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Foreign key
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("session.id", ondelete="CASCADE"), nullable=False
    )

    # Message content
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # teacher, student, tutor
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session", back_populates="messages"
    )
    question_analysis: Mapped["QuestionAnalysis"] = relationship(  # noqa: F821
        "QuestionAnalysis", back_populates="message", uselist=False
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "role IN ('teacher', 'student', 'tutor')", name="ck_message_role"
        ),
        Index("ix_message_session_created", "session_id", "created_at"),
        Index("ix_message_session_role", "session_id", "role"),
    )

    def __repr__(self) -> str:
        preview = self.content[:30] + "..." if len(self.content) > 30 else self.content
        return f"<Message(id={self.id}, role={self.role}, content={preview})>"

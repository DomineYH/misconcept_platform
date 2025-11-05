"""User model for teachers, students, and admins (T022)."""
from datetime import datetime
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.connection import Base


class User(Base):
    """User entity with minimal auth (student_uid + nickname)."""

    __tablename__ = "user"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Login credentials
    student_uid: Mapped[str] = mapped_column(String(50), nullable=False)
    nickname: Mapped[str] = mapped_column(String(30), nullable=False)

    # Role enum
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="teacher"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="teacher", foreign_keys="Session.teacher_id"
    )
    scenarios: Mapped[list["Scenario"]] = relationship(
        "Scenario", back_populates="creator"
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("student_uid", "nickname", name="uq_user_creds"),
        CheckConstraint(
            "role IN ('teacher', 'student', 'admin')", name="ck_user_role"
        ),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, uid={self.student_uid}, role={self.role})>"

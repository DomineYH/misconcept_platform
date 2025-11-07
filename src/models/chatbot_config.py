"""ChatbotConfig and ChatbotConfigAudit models for bot configuration."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.connection import Base


class ChatbotConfig(Base):
    """Global chatbot configuration settings."""

    __tablename__ = "chatbot_config"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Configuration fields
    config_key: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    config_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=True
    )

    # Relationship
    updater: Mapped[Optional["User"]] = relationship(
        "User", back_populates="config_updates"
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ChatbotConfig(id={self.id}, "
            f"key='{self.config_key}', "
            f"value='{self.config_value}', "
            f"type='{self.config_type}')>"
        )


class ChatbotConfigAudit(Base):
    """Audit trail for chatbot configuration changes."""

    __tablename__ = "chatbot_config_audit"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Audit fields
    config_key: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text, nullable=False)

    # Who and when
    changed_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # IP address for security tracking
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True
    )

    # Relationship
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ChatbotConfigAudit(id={self.id}, "
            f"key='{self.config_key}', "
            f"by={self.changed_by}, "
            f"at={self.changed_at})>"
        )

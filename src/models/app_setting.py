"""AppSetting model for global application settings (key/value store)."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.connection import Base


class AppSetting(Base):
    """Global application setting keyed by a string key."""

    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<AppSetting(key={self.key}, value={self.value})>"

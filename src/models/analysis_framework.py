"""AnalysisFramework model for pedagogical taxonomies (T023)."""
from datetime import datetime
import json
from sqlalchemy import Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from src.db.connection import Base


class AnalysisFramework(Base):
    """Framework for classifying teacher questions (e.g., leverage)."""

    __tablename__ = "analysis_framework"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Framework identity
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Labels as JSON array
    labels_json: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    scenarios: Mapped[list["Scenario"]] = relationship(
        "Scenario", back_populates="framework"
    )

    @property
    def labels(self) -> list[str]:
        """Parse JSON labels into Python list."""
        return json.loads(self.labels_json)

    @labels.setter
    def labels(self, value: list[str]) -> None:
        """Convert Python list to JSON string."""
        self.labels_json = json.dumps(value)

    @validates("labels_json")
    def validate_labels_json(self, key: str, value: str) -> str:
        """Ensure labels_json is valid JSON array."""
        try:
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise ValueError("labels_json must be JSON array")
            if not (2 <= len(parsed) <= 20):
                raise ValueError("labels must have 2-20 elements")
            return value
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    def __repr__(self) -> str:
        return f"<AnalysisFramework(id={self.id}, name={self.name})>"

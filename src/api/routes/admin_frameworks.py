"""Admin framework management routes (T087-T088)."""
import json
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session
from src.models.user import User
from src.models.analysis_framework import AnalysisFramework

router = APIRouter(tags=["Admin Frameworks"])


# Pydantic schemas
class FrameworkCreate(BaseModel):
    """Schema for creating an analysis framework (T088)."""

    name: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=1000)
    labels: List[str] = Field(..., min_length=2, max_length=20)

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, v: List[str]) -> List[str]:
        """Validate each label length (2-50 chars)."""
        if len(v) < 2:
            raise ValueError("At least 2 labels required")
        if len(v) > 20:
            raise ValueError("Maximum 20 labels allowed")

        for label in v:
            if len(label) < 2:
                raise ValueError(
                    f"Label '{label}' too short (min 2 chars)"
                )
            if len(label) > 50:
                raise ValueError(
                    f"Label '{label}' too long (max 50 chars)"
                )

        return v


class FrameworkResponse(BaseModel):
    """Schema for framework response (T087-T088)."""

    model_config = {"from_attributes": True}

    id: int
    name: str
    description: str
    labels: List[str]

    @field_validator("labels", mode="before")
    @classmethod
    def parse_labels_json(cls, v):
        """Parse labels from JSON string or list."""
        if isinstance(v, str):
            return json.loads(v)
        return v


@router.get(
    "/admin/frameworks",
    response_model=List[FrameworkResponse],
)
async def list_frameworks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """GET /admin/frameworks - List all frameworks (T087)."""
    # Check admin role
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    # Get all frameworks
    query = select(AnalysisFramework).order_by(AnalysisFramework.name)
    result = await db.execute(query)
    frameworks = result.scalars().all()

    # Convert to response format with parsed labels
    return [
        FrameworkResponse(
            id=fw.id,
            name=fw.name,
            description=fw.description,
            labels=fw.labels,  # Uses property getter
        )
        for fw in frameworks
    ]


@router.post(
    "/admin/frameworks",
    response_model=FrameworkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_framework(
    framework_data: FrameworkCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """POST /admin/frameworks - Create new framework (T088)."""
    # Check admin role
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    # Create framework with labels as JSON
    framework = AnalysisFramework(
        name=framework_data.name,
        description=framework_data.description,
        labels_json=json.dumps(framework_data.labels),
    )

    db.add(framework)
    await db.commit()
    await db.refresh(framework)

    # Return with parsed labels
    return FrameworkResponse(
        id=framework.id,
        name=framework.name,
        description=framework.description,
        labels=framework.labels,  # Uses property getter
    )

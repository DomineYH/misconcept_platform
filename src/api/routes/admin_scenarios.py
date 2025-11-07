"""Admin scenario management routes (T077-T080)."""
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session
from src.models.analysis_framework import AnalysisFramework
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.user import User

router = APIRouter(tags=["Admin Scenarios"])
templates = Jinja2Templates(directory="src/templates")


# Pydantic schemas
class ScenarioCreate(BaseModel):
    """Schema for creating a scenario."""

    title: str = Field(..., min_length=3, max_length=200)
    prompt: str = Field(..., min_length=10, max_length=10000)
    student_profile: str = Field(..., min_length=3, max_length=5000)
    framework_id: int
    is_active: bool = Field(default=True)

    # Phase 2: Bot configuration overrides (all optional)
    chat_model: Optional[str] = Field(
        None,
        pattern=r"^gpt-(3\.5|4|4o|4o-mini)(-turbo)?$",
        description="Override StudentBot model (NULL = use global)",
    )
    chat_temperature: Optional[float] = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Override temperature 0.0-2.0 (NULL = use global)",
    )
    tutor_enabled: bool = Field(
        default=True, description="Enable/disable TutorBot for scenario"
    )
    tutor_intervention_threshold: Optional[int] = Field(
        None,
        ge=1,
        le=10,
        description="Override interventions per 10 questions (NULL = use "
        "global)",
    )

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        """Ensure title is not just whitespace."""
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

    @field_validator("prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        """Ensure prompt is not just whitespace."""
        if not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v.strip()


class ScenarioUpdate(BaseModel):
    """Schema for updating a scenario."""

    title: Optional[str] = Field(None, min_length=3, max_length=200)
    prompt: Optional[str] = Field(None, min_length=10, max_length=10000)
    student_profile: Optional[str] = Field(
        None, min_length=3, max_length=5000
    )
    framework_id: Optional[int] = None
    is_active: Optional[int] = Field(None, ge=0, le=1)

    # Phase 2: Bot configuration overrides (all optional)
    chat_model: Optional[str] = Field(
        None, pattern=r"^gpt-(3\.5|4|4o|4o-mini)(-turbo)?$"
    )
    chat_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    tutor_enabled: Optional[bool] = None
    tutor_intervention_threshold: Optional[int] = Field(None, ge=1, le=10)


class ScenarioResponse(BaseModel):
    """Schema for scenario response."""

    model_config = {"from_attributes": True}

    id: int
    title: str
    prompt: str
    student_profile: str
    framework_id: int
    is_active: int

    # Phase 2: Bot configuration overrides
    chat_model: Optional[str] = None
    chat_temperature: Optional[float] = None
    tutor_enabled: bool = True
    tutor_intervention_threshold: Optional[int] = None


@router.get("/admin/scenarios", response_class=HTMLResponse)
async def list_all_scenarios(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """GET /admin/scenarios - List all scenarios (T077)."""
    # Check admin role
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    query = (
        select(Scenario)
        .join(AnalysisFramework)
        .order_by(Scenario.id.desc())
    )
    result = await db.execute(query)
    scenarios = result.scalars().all()

    # Load frameworks for dropdown
    frameworks_query = select(AnalysisFramework).order_by(
        AnalysisFramework.name
    )
    frameworks_result = await db.execute(frameworks_query)
    frameworks = frameworks_result.scalars().all()

    return templates.TemplateResponse(
        "admin/scenarios.html",
        {
            "request": request,
            "user": user,
            "scenarios": scenarios,
            "frameworks": frameworks,
        },
    )


@router.post(
    "/admin/scenarios",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scenario(
    scenario_data: ScenarioCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """POST /admin/scenarios - Create new scenario (T078)."""
    # Check admin role
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    # Verify framework exists
    framework = await db.get(AnalysisFramework, scenario_data.framework_id)
    if not framework:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Framework not found",
        )

    # Create scenario with bot configuration overrides
    scenario = Scenario(
        title=scenario_data.title,
        prompt=scenario_data.prompt,
        student_profile=scenario_data.student_profile,
        framework_id=scenario_data.framework_id,
        is_active=1 if scenario_data.is_active else 0,
        # Phase 2: Bot configuration overrides
        chat_model=scenario_data.chat_model,
        chat_temperature=scenario_data.chat_temperature,
        tutor_enabled=1 if scenario_data.tutor_enabled else 0,
        tutor_intervention_threshold=(
            scenario_data.tutor_intervention_threshold
        ),
    )

    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)

    return scenario


@router.put(
    "/admin/scenarios/{scenario_id}", response_model=ScenarioResponse
)
async def update_scenario(
    scenario_id: int,
    scenario_data: ScenarioUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """PUT /admin/scenarios/{id} - Update scenario (T079, T080)."""
    # Check admin role
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    # Get scenario
    scenario = await db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )

    # Check for active sessions (T080)
    active_sessions_query = (
        select(func.count(Session.id))
        .where(Session.scenario_id == scenario_id)
        .where(Session.ended_at.is_(None))
    )
    active_sessions_count = await db.scalar(active_sessions_query)

    if active_sessions_count and active_sessions_count > 0:
        # Only allow toggling is_active for scenarios with sessions
        update_keys = set(
            scenario_data.dict(exclude_unset=True).keys()
        )
        if update_keys != {"is_active"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify scenario with active sessions. "
                "Only status toggle allowed.",
            )

    # Update fields
    if scenario_data.title is not None:
        scenario.title = scenario_data.title.strip()
    if scenario_data.prompt is not None:
        scenario.prompt = scenario_data.prompt.strip()
    if scenario_data.student_profile is not None:
        scenario.student_profile = scenario_data.student_profile.strip()
    if scenario_data.framework_id is not None:
        # Verify framework exists
        framework = await db.get(
            AnalysisFramework, scenario_data.framework_id
        )
        if not framework:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Framework not found",
            )
        scenario.framework_id = scenario_data.framework_id
    if scenario_data.is_active is not None:
        scenario.is_active = scenario_data.is_active

    # Phase 2: Update bot configuration overrides
    if scenario_data.chat_model is not None:
        scenario.chat_model = scenario_data.chat_model
    if scenario_data.chat_temperature is not None:
        scenario.chat_temperature = scenario_data.chat_temperature
    if scenario_data.tutor_enabled is not None:
        scenario.tutor_enabled = 1 if scenario_data.tutor_enabled else 0
    if scenario_data.tutor_intervention_threshold is not None:
        scenario.tutor_intervention_threshold = (
            scenario_data.tutor_intervention_threshold
        )

    await db.commit()
    await db.refresh(scenario)

    return scenario

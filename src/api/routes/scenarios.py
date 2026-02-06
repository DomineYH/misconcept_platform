"""Scenario browsing and selection routes."""
import logging

from fastapi import (
    APIRouter,
    Depends,
    Request,
    HTTPException,
    status,
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import get_db_session, get_current_user
from src.models import User, Scenario, Session
from src.models.scenario_group import ScenarioGroup

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Scenarios"])
templates = Jinja2Templates(directory="src/templates")


@router.get("/", response_class=HTMLResponse)
async def home():
    """Redirect home to scenarios list."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(
        url="/scenarios", status_code=303
    )


@router.get("/scenarios", response_class=HTMLResponse)
async def list_scenarios(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Display scenarios filtered by user's group."""
    # Base query: active, non-deleted
    query = (
        select(Scenario)
        .where(Scenario.is_active == 1)
        .where(Scenario.deleted_at.is_(None))
    )

    # Admin sees all scenarios
    if user.role != "admin":
        if user.group_id:
            # Filter by user's group via scenario_group
            query = query.where(
                Scenario.id.in_(
                    select(ScenarioGroup.scenario_id).where(
                        ScenarioGroup.group_id
                        == user.group_id
                    )
                )
            )
        else:
            # User without group sees no scenarios
            query = query.where(Scenario.id < 0)

    result = await db.execute(query)
    scenarios = result.scalars().all()

    return templates.TemplateResponse(
        "scenarios.html",
        {
            "request": request,
            "user": user,
            "scenarios": scenarios,
        },
    )


@router.get(
    "/scenarios/{scenario_id}",
    response_class=HTMLResponse,
)
async def get_scenario_detail(
    request: Request,
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Display scenario and dialogue interface."""
    # Load scenario with framework (exclude deleted)
    result = await db.execute(
        select(Scenario)
        .options(selectinload(Scenario.framework))
        .where(Scenario.id == scenario_id)
        .where(Scenario.deleted_at.is_(None))
    )
    scenario = result.scalar_one_or_none()

    if not scenario:
        raise HTTPException(
            status_code=404, detail="Scenario not found"
        )

    # Check if scenario is active (unless admin)
    if scenario.is_active != 1 and user.role != "admin":
        raise HTTPException(
            status_code=404, detail="Scenario not found"
        )

    # Group access check (admin bypasses)
    if user.role != "admin":
        if not user.group_id:
            raise HTTPException(
                status_code=403,
                detail="그룹이 배정되지 않았습니다.",
            )
        sg = await db.execute(
            select(ScenarioGroup).where(
                ScenarioGroup.scenario_id == scenario_id,
                ScenarioGroup.group_id == user.group_id,
            )
        )
        if not sg.scalar_one_or_none():
            raise HTTPException(
                status_code=403,
                detail="이 시나리오에 대한 접근 권한이 "
                "없습니다.",
            )

    # Auto-create session
    session = Session(
        scenario_id=scenario.id, teacher_id=user.id
    )
    db.add(session)

    try:
        await db.commit()
        await db.refresh(session)
        logger.info(
            f"Auto-created session {session.id} "
            f"for user {user.id} "
            f"on scenario {scenario.id}"
        )
    except SQLAlchemyError as e:
        logger.error(f"Failed to create session: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="대화 세션을 시작할 수 없습니다. "
            "잠시 후 다시 시도해주세요.",
        )

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "user": user,
            "scenario": scenario,
            "session_id": session.id,
            "messages": [],
        },
    )

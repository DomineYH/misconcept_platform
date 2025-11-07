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

from src.api.dependencies import get_db_session, get_current_user
from src.models import User, Scenario, Session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Scenarios"])
templates = Jinja2Templates(directory="src/templates")


@router.get("/", response_class=HTMLResponse)
async def home():
    """Redirect home to scenarios list."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/scenarios", status_code=303)


@router.get("/scenarios", response_class=HTMLResponse)
async def list_scenarios(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Display active scenarios list."""
    # Query active scenarios
    result = await db.execute(
        select(Scenario).where(Scenario.is_active == 1)
    )
    scenarios = result.scalars().all()

    return templates.TemplateResponse(
        "scenarios.html",
        {"request": request, "user": user, "scenarios": scenarios},
    )


@router.get("/scenarios/{scenario_id}", response_class=HTMLResponse)
async def get_scenario_detail(
    request: Request,
    scenario_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Display scenario and dialogue interface."""
    # Load scenario
    result = await db.execute(
        select(Scenario).where(Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()

    if not scenario:
        raise HTTPException(
            status_code=404, detail="Scenario not found"
        )

    # Check if scenario is active (unless user is admin)
    if scenario.is_active != 1 and user.role != "admin":
        raise HTTPException(
            status_code=404, detail="Scenario not found"
        )

    # Auto-create session for this scenario
    session = Session(scenario_id=scenario.id, teacher_id=user.id)
    db.add(session)

    try:
        await db.commit()
        await db.refresh(session)
        logger.info(
            f"Auto-created session {session.id} for user {user.id} "
            f"on scenario {scenario.id}"
        )
    except SQLAlchemyError as e:
        logger.error(f"Failed to create session: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="대화 세션을 시작할 수 없습니다. 잠시 후 다시 시도해주세요.",
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

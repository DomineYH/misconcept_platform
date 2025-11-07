"""Admin dashboard and router aggregation (T076)."""
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session
from src.models.user import User
from src.models.scenario import Scenario
from src.models.session import Session

# Import sub-routers
from src.api.routes.admin_scenarios import (
    router as scenarios_router,
)
from src.api.routes.admin_frameworks import (
    router as frameworks_router,
)
from src.api.routes.admin_sessions import (
    router as sessions_router,
)
from src.api.routes.admin_api_usage import (
    router as api_usage_router,
)

router = APIRouter(tags=["Admin"])
templates = Jinja2Templates(directory="src/templates")

# Include sub-routers
router.include_router(scenarios_router)
router.include_router(frameworks_router)
router.include_router(sessions_router)
router.include_router(api_usage_router)


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """GET /admin - Admin dashboard with aggregate statistics (T076)."""
    # Check admin role
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    # Count scenarios
    total_scenarios_query = select(func.count(Scenario.id))
    total_scenarios = await db.scalar(total_scenarios_query)

    active_scenarios_query = select(func.count(Scenario.id)).where(
        Scenario.is_active == 1
    )
    active_scenarios = await db.scalar(active_scenarios_query)

    # Count sessions
    total_sessions_query = select(func.count(Session.id))
    total_sessions = await db.scalar(total_sessions_query)

    # Calculate average session duration (in minutes)
    duration_query = select(
        func.avg(
            func.julianday(Session.ended_at)
            - func.julianday(Session.started_at)
        )
        * 24
        * 60
    ).where(Session.ended_at.isnot(None))
    avg_duration = await db.scalar(duration_query) or 0

    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "user": user,
            "total_scenarios": total_scenarios or 0,
            "active_scenarios": active_scenarios or 0,
            "total_sessions": total_sessions or 0,
            "avg_duration": round(avg_duration, 1),
        },
    )

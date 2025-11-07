"""Admin API usage tracking routes (Task 3.1.4)."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session
from src.models.api_usage import ApiUsageLog
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.user import User

router = APIRouter(tags=["Admin API Usage"])
templates = Jinja2Templates(directory="src/templates")


# ============================================================================
# Pydantic Schemas
# ============================================================================


class UsageLogItem(BaseModel):
    """Schema for a single API usage log entry."""

    model_config = {"from_attributes": True}

    id: int
    session_id: int
    scenario_name: str
    bot_type: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    timestamp: datetime


class UsageSummary(BaseModel):
    """Schema for aggregated usage statistics."""

    total_requests: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: float


class UsageListResponse(BaseModel):
    """Schema for API usage list response."""

    total_count: int
    usage_logs: List[UsageLogItem]
    summary: UsageSummary


# ============================================================================
# Helper Functions
# ============================================================================


def _check_admin_role(user: User) -> None:
    """Verify user has admin role.

    Args:
        user: Current user from dependency

    Raises:
        HTTPException: If user is not admin
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/admin/api-usage", response_model=UsageListResponse)
async def get_api_usage(
    start_date: Optional[str] = Query(
        None, description="Start date (ISO 8601: YYYY-MM-DD)"
    ),
    end_date: Optional[str] = Query(
        None, description="End date (ISO 8601: YYYY-MM-DD)"
    ),
    scenario_id: Optional[int] = Query(
        None, description="Filter by scenario ID"
    ),
    bot_type: Optional[str] = Query(
        None, description="Filter by bot type: 'student' or 'tutor'"
    ),
    model: Optional[str] = Query(
        None, description="Filter by model: 'gpt-4o', 'gpt-4o-mini', etc."
    ),
    limit: int = Query(
        100, ge=1, le=1000, description="Number of records per page"
    ),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """GET /admin/api-usage - Retrieve API usage logs with filtering.

    Query Parameters:
        start_date: Filter logs from this date onwards (ISO 8601)
        end_date: Filter logs up to this date (ISO 8601)
        scenario_id: Filter by specific scenario
        bot_type: Filter by bot type ('student' or 'tutor')
        model: Filter by OpenAI model name
        limit: Number of records per page (default: 100, max: 1000)
        offset: Number of records to skip (default: 0)

    Returns:
        UsageListResponse: Paginated usage logs with summary statistics

    Security:
        Admin role required

    Raises:
        HTTPException: 400 for invalid date format, 403 for non-admin users
    """
    # Check admin role
    _check_admin_role(user)

    # Build filter conditions
    filters = []

    # Date range filters
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            filters.append(ApiUsageLog.timestamp >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO 8601 (YYYY-MM-DD)",
            )

    if end_date:
        try:
            # Add 23:59:59 to include entire end_date
            end_dt = datetime.fromisoformat(end_date)
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            filters.append(ApiUsageLog.timestamp <= end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO 8601 (YYYY-MM-DD)",
            )

    # Scenario filter (requires join)
    if scenario_id:
        filters.append(Session.scenario_id == scenario_id)

    # Bot type filter
    if bot_type:
        filters.append(ApiUsageLog.bot_type == bot_type)

    # Model filter
    if model:
        filters.append(ApiUsageLog.model == model)

    # Count total records matching filters
    count_query = select(func.count(ApiUsageLog.id))
    if scenario_id:
        count_query = count_query.join(
            Session, ApiUsageLog.session_id == Session.id
        )
    if filters:
        count_query = count_query.where(and_(*filters))

    total_count_result = await db.execute(count_query)
    total_count = total_count_result.scalar() or 0

    # Fetch paginated data with joins
    data_query = (
        select(
            ApiUsageLog,
            Session.id.label("session_id_label"),
            Scenario.title.label("scenario_name"),
        )
        .join(Session, ApiUsageLog.session_id == Session.id)
        .join(Scenario, Session.scenario_id == Scenario.id)
    )

    if filters:
        data_query = data_query.where(and_(*filters))

    data_query = (
        data_query.order_by(ApiUsageLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(data_query)
    rows = result.all()

    # Transform results to response schema
    usage_logs = [
        UsageLogItem(
            id=row.ApiUsageLog.id,
            session_id=row.session_id_label,
            scenario_name=row.scenario_name,
            bot_type=row.ApiUsageLog.bot_type,
            model=row.ApiUsageLog.model,
            prompt_tokens=row.ApiUsageLog.prompt_tokens,
            completion_tokens=row.ApiUsageLog.completion_tokens,
            total_tokens=row.ApiUsageLog.total_tokens,
            estimated_cost_usd=row.ApiUsageLog.estimated_cost_usd,
            timestamp=row.ApiUsageLog.timestamp,
        )
        for row in rows
    ]

    # Calculate summary statistics
    summary_query = select(
        func.count(ApiUsageLog.id).label("total_requests"),
        func.coalesce(func.sum(ApiUsageLog.prompt_tokens), 0).label(
            "total_prompt_tokens"
        ),
        func.coalesce(func.sum(ApiUsageLog.completion_tokens), 0).label(
            "total_completion_tokens"
        ),
        func.coalesce(func.sum(ApiUsageLog.total_tokens), 0).label(
            "total_tokens"
        ),
        func.coalesce(func.sum(ApiUsageLog.estimated_cost_usd), 0.0).label(
            "total_cost_usd"
        ),
    )

    if scenario_id:
        summary_query = summary_query.join(
            Session, ApiUsageLog.session_id == Session.id
        )
    if filters:
        summary_query = summary_query.where(and_(*filters))

    summary_result = await db.execute(summary_query)
    summary_row = summary_result.first()

    summary = UsageSummary(
        total_requests=summary_row.total_requests or 0,
        total_prompt_tokens=summary_row.total_prompt_tokens or 0,
        total_completion_tokens=summary_row.total_completion_tokens or 0,
        total_tokens=summary_row.total_tokens or 0,
        total_cost_usd=round(summary_row.total_cost_usd or 0.0, 6),
    )

    return UsageListResponse(
        total_count=total_count,
        usage_logs=usage_logs,
        summary=summary,
    )


@router.get("/admin/api-usage-page", response_class=HTMLResponse)
async def api_usage_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """GET /admin/api-usage-page - Render API usage analytics page.

    Returns:
        HTMLResponse: API usage dashboard with filters

    Security:
        Admin role required

    Raises:
        HTTPException: 403 for non-admin users
    """
    # Check admin role
    _check_admin_role(user)

    # Fetch all scenarios for filter dropdown
    scenarios_query = select(Scenario).where(Scenario.is_active == 1)
    scenarios_result = await db.execute(scenarios_query)
    scenarios = scenarios_result.scalars().all()

    return templates.TemplateResponse(
        "admin/api_usage.html",
        {
            "request": request,
            "user": user,
            "scenarios": scenarios,
        },
    )

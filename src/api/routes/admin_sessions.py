"""Admin session management routes."""
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session
from src.models.user import User
from src.models.session import Session
from src.models.scenario import Scenario
from src.services.export import CSVExporter

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


@router.get("/admin/sessions-page", response_class=HTMLResponse)
async def sessions_page(
    request: Request,
    scenario_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List all sessions with optional filtering (HTML Page)."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    query = (
        select(Session)
        .options(joinedload(Session.scenario))
        .where(Session.deleted_at.is_(None))
        .order_by(desc(Session.started_at))
    )
    if scenario_id:
        query = query.where(Session.scenario_id == scenario_id)

    result = await db.execute(query)
    sessions = result.scalars().all()

    # Get scenarios for filter dropdown
    scenarios_result = await db.execute(
        select(Scenario).order_by(Scenario.title)
    )
    scenarios = scenarios_result.scalars().all()

    return templates.TemplateResponse(
        "admin/sessions.html",
        {
            "request": request,
            "user": user,
            "sessions": sessions,
            "scenarios": scenarios,
            "current_scenario_id": scenario_id,
        },
    )


@router.get("/admin/sessions", response_class=JSONResponse)
async def list_sessions_api(
    scenario_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    date_from: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, List[Dict[str, Any]]]:
    """List all sessions with optional filtering (API)."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    query = (
        select(Session)
        .options(joinedload(Session.scenario), joinedload(Session.teacher))
        .where(Session.deleted_at.is_(None))
        .order_by(desc(Session.started_at))
    )

    if scenario_id:
        query = query.where(Session.scenario_id == scenario_id)

    if teacher_id:
        query = query.where(Session.teacher_id == teacher_id)

    if date_from:
        try:
            # Handle 'Z' suffix or standard ISO format
            if date_from.endswith("Z"):
                date_from = date_from[:-1]
            dt = datetime.fromisoformat(date_from)
            query = query.where(Session.started_at >= dt)
        except ValueError:
            pass  # Ignore invalid date format

    result = await db.execute(query)
    sessions = result.scalars().all()

    return {
        "sessions": [
            {
                "id": s.id,
                "scenario_id": s.scenario_id,
                "scenario_title": s.scenario.title if s.scenario else "Unknown",
                "teacher_id": s.teacher_id,
                "teacher_nickname": s.teacher.nickname if s.teacher else "Unknown",
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "status": "ended" if s.ended_at else "active",
            }
            for s in sessions
        ]
    }


@router.get("/admin/sessions/export")
async def export_sessions(
    scenario_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Export filtered sessions to CSV."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    query = (
        select(Session.id)
        .where(Session.deleted_at.is_(None))
        .order_by(desc(Session.started_at))
    )
    if scenario_id:
        query = query.where(Session.scenario_id == scenario_id)

    result = await db.execute(query)
    session_ids = result.scalars().all()

    if not session_ids:
        return Response(content="No sessions found", media_type="text/plain")

    exporter = CSVExporter()
    csv_content = await exporter.export_multiple_sessions(list(session_ids), db)

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=sessions_export.csv"
        },
    )


@router.get("/admin/stats")
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get system statistics for dashboard charts."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    # Calculate statistics
    # Total teachers (unique teacher_id in sessions)
    total_teachers_query = select(
        func.count(func.distinct(Session.teacher_id))
    ).where(Session.deleted_at.is_(None))
    total_teachers = await db.scalar(total_teachers_query) or 0

    # Total sessions
    total_sessions_query = select(func.count(Session.id)).where(
        Session.deleted_at.is_(None)
    )
    total_sessions = await db.scalar(total_sessions_query) or 0

    # Active sessions (no ended_at)
    active_sessions_query = select(func.count(Session.id)).where(
        Session.ended_at.is_(None), Session.deleted_at.is_(None)
    )
    active_sessions = await db.scalar(active_sessions_query) or 0

    # Average session duration (minutes)
    duration_query = select(
        func.avg(
            func.julianday(Session.ended_at)
            - func.julianday(Session.started_at)
        )
        * 24
        * 60
    ).where(Session.ended_at.isnot(None), Session.deleted_at.is_(None))
    avg_duration = await db.scalar(duration_query) or 0

    return {
        "total_teachers": total_teachers,
        "total_sessions": total_sessions,
        "active_sessions": active_sessions,
        "avg_session_duration_minutes": round(avg_duration, 1),
        "avg_questions_per_session": 0,  # Placeholder
    }

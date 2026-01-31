"""Admin session management routes."""

from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
    Form,
)
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session
from src.models.session import Session
from src.models.user import User
from src.services.export import CSVExporter

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


@router.get("/admin/sessions-page", response_class=HTMLResponse)
async def sessions_page(
    request: Request,
    teacher_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status_filter: Optional[str] = None,
    page: int = 1,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    per_page = 10
    offset = (page - 1) * per_page

    base_query = select(Session).where(Session.deleted_at.is_(None))

    if teacher_id:
        base_query = base_query.where(Session.teacher_id == teacher_id)
    if status_filter == "completed":
        base_query = base_query.where(Session.ended_at.isnot(None))
    elif status_filter == "active":
        base_query = base_query.where(Session.ended_at.is_(None))
    if date_from:
        try:
            dt = datetime.fromisoformat(date_from.replace("Z", ""))
            base_query = base_query.where(Session.started_at >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to.replace("Z", ""))
            base_query = base_query.where(Session.started_at <= dt)
        except ValueError:
            pass

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total_count = count_result.scalar() or 0
    total_pages = (total_count + per_page - 1) // per_page

    query = (
        base_query.options(
            joinedload(Session.scenario), joinedload(Session.teacher)
        )
        .order_by(desc(Session.started_at))
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(query)
    sessions = result.scalars().all()

    teachers_result = await db.execute(
        select(User)
        .where(User.id.in_(select(Session.teacher_id).distinct()))
        .order_by(User.nickname)
    )
    teachers = teachers_result.scalars().all()

    return templates.TemplateResponse(
        "admin/sessions.html",
        {
            "request": request,
            "user": user,
            "sessions": sessions,
            "teachers": teachers,
            "current_teacher_id": teacher_id,
            "current_date_from": date_from or "",
            "current_date_to": date_to or "",
            "current_status": status_filter or "",
            "current_page": page,
            "total_pages": total_pages,
            "total_count": total_count,
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
                "teacher_nickname": s.teacher.nickname
                if s.teacher
                else "Unknown",
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
    teacher_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    query = (
        select(Session.id)
        .where(Session.deleted_at.is_(None))
        .where(Session.ended_at.isnot(None))
        .order_by(desc(Session.started_at))
    )

    if scenario_id:
        query = query.where(Session.scenario_id == scenario_id)
    if teacher_id:
        query = query.where(Session.teacher_id == teacher_id)
    if date_from:
        try:
            dt = datetime.fromisoformat(date_from.replace("Z", ""))
            query = query.where(Session.started_at >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to.replace("Z", ""))
            query = query.where(Session.started_at <= dt)
        except ValueError:
            pass

    result = await db.execute(query)
    session_ids = result.scalars().all()

    if not session_ids:
        return Response(content="No sessions found", media_type="text/plain")

    exporter = CSVExporter()
    csv_content = await exporter.export_multiple_sessions_admin(
        list(session_ids), db
    )

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=sessions_export.csv"
        },
    )


@router.post("/admin/sessions/export-selected")
async def export_selected_sessions(
    session_ids: List[int] = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    if not session_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No session_ids provided",
        )

    result = await db.execute(
        select(Session).where(Session.id.in_(session_ids))
    )
    sessions = result.scalars().all()

    for s in sessions:
        if s.ended_at is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Session {s.id} is still active. Only ended allowed.",
            )

    valid_ids = [s.id for s in sessions if s.deleted_at is None]
    if not valid_ids:
        return Response(content="No valid sessions", media_type="text/plain")

    exporter = CSVExporter()
    csv_content = await exporter.export_multiple_sessions_admin(valid_ids, db)

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=selected_sessions.csv"
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

    total_teachers_query = select(
        func.count(func.distinct(Session.teacher_id))
    ).where(Session.deleted_at.is_(None))
    total_teachers = await db.scalar(total_teachers_query) or 0

    total_sessions_query = select(func.count(Session.id)).where(
        Session.deleted_at.is_(None)
    )
    total_sessions = await db.scalar(total_sessions_query) or 0

    active_sessions_query = select(func.count(Session.id)).where(
        Session.ended_at.is_(None), Session.deleted_at.is_(None)
    )
    active_sessions = await db.scalar(active_sessions_query) or 0

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
        "avg_questions_per_session": 0,
    }


@router.get("/admin/user-conversations", response_class=HTMLResponse)
async def user_conversations_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List users who have conversations with session counts."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    subq_total = (
        select(
            Session.teacher_id,
            func.count(Session.id).label("session_count"),
            func.max(Session.started_at).label("last_session"),
        )
        .where(Session.deleted_at.is_(None))
        .group_by(Session.teacher_id)
        .subquery()
    )

    subq_ended = (
        select(
            Session.teacher_id,
            func.count(Session.id).label("ended_count"),
        )
        .where(Session.deleted_at.is_(None), Session.ended_at.isnot(None))
        .group_by(Session.teacher_id)
        .subquery()
    )

    query = (
        select(
            User,
            subq_total.c.session_count,
            subq_total.c.last_session,
            func.coalesce(subq_ended.c.ended_count, 0).label("ended_count"),
        )
        .join(subq_total, User.id == subq_total.c.teacher_id)
        .outerjoin(subq_ended, User.id == subq_ended.c.teacher_id)
        .order_by(desc(subq_total.c.session_count))
    )

    result = await db.execute(query)
    rows = result.all()

    users_data = [
        {
            "user": row[0],
            "session_count": row[1],
            "last_session": row[2],
            "ended_session_count": row[3],
        }
        for row in rows
    ]

    return templates.TemplateResponse(
        "admin/user_conversations.html",
        {"request": request, "user": user, "users": users_data},
    )


@router.get("/admin/user-conversations/{user_id}/export")
async def export_user_conversations(
    user_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Download all conversations for a specific user as CSV."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    target_user = await db.get(User, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    query = (
        select(Session.id)
        .where(
            Session.teacher_id == user_id,
            Session.deleted_at.is_(None),
            Session.ended_at.isnot(None),
        )
        .order_by(desc(Session.started_at))
    )
    result = await db.execute(query)
    session_ids = result.scalars().all()

    if not session_ids:
        return Response(
            content="No completed sessions found",
            media_type="text/plain",
        )

    exporter = CSVExporter()
    csv_content = await exporter.export_multiple_sessions_admin(
        list(session_ids), db
    )

    filename = f"user_{user_id}_conversations.csv"
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/admin/sessions/{session_id}/end", response_class=HTMLResponse)
async def end_session(
    request: Request,
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """End an active session (set ended_at)."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    query = (
        select(Session)
        .options(joinedload(Session.scenario), joinedload(Session.teacher))
        .where(Session.id == session_id)
    )
    result = await db.execute(query)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    if session.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already ended",
        )

    session.ended_at = datetime.utcnow()
    await db.commit()

    return templates.TemplateResponse(
        "partials/session_row.html",
        {"request": request, "session": session},
    )


@router.delete("/admin/sessions/{session_id}", response_class=HTMLResponse)
async def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Soft delete a session (set deleted_at)."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    if session.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already deleted",
        )

    session.mark_deleted()
    await db.commit()

    return Response(content="", status_code=200)


@router.get("/admin/sessions/{session_id}/detail", response_class=HTMLResponse)
async def session_detail(
    request: Request,
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get session detail for viewing in modal."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    query = (
        select(Session)
        .options(
            joinedload(Session.scenario),
            joinedload(Session.teacher),
        )
        .where(Session.id == session_id)
    )
    result = await db.execute(query)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    return templates.TemplateResponse(
        "partials/session_detail.html",
        {"request": request, "session": session},
    )


@router.get("/admin/sessions/{session_id}/download")
async def download_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    if session.ended_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot download active session",
        )

    exporter = CSVExporter()
    csv_content = await exporter.export_session_admin(session_id, db)

    filename = f"session_{session_id}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

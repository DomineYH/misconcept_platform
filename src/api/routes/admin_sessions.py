"""Admin session logs and statistics routes (T095-T097)."""
import csv
import io
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import get_current_user, get_db_session
from src.models.message import Message
from src.models.session import Session
from src.models.user import User

router = APIRouter(tags=["Admin Sessions"])


# Pydantic schemas
class SessionListItem(BaseModel):
    """Schema for session list item."""

    model_config = {"from_attributes": True}

    id: int
    scenario_id: int
    scenario_title: str
    teacher_id: int
    teacher_nickname: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    message_count: int


class SessionListResponse(BaseModel):
    """Schema for session list response."""

    sessions: List[SessionListItem]
    total: int


class StatsResponse(BaseModel):
    """Schema for aggregated statistics (T097)."""

    total_sessions: int
    total_teachers: int
    avg_session_duration_minutes: float
    avg_questions_per_session: float
    active_sessions: int


@router.get("/admin/sessions", response_model=SessionListResponse)
async def list_sessions(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    teacher_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """GET /admin/sessions - List sessions with filtering (T095)."""
    # Check admin role
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    # Build query with joins
    query = (
        select(Session)
        .options(
            selectinload(Session.scenario),
            selectinload(Session.teacher),
        )
        .order_by(Session.started_at.desc())
    )

    # Apply filters
    filters = []

    if date_from:
        try:
            date_from_dt = datetime.fromisoformat(date_from)
            filters.append(Session.started_at >= date_from_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_from format",
            )

    if date_to:
        try:
            date_to_dt = datetime.fromisoformat(date_to)
            filters.append(Session.started_at <= date_to_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_to format",
            )

    if teacher_id:
        filters.append(Session.teacher_id == teacher_id)

    if filters:
        query = query.where(and_(*filters))

    # Execute query
    result = await db.execute(query)
    sessions = result.scalars().all()

    # Get message counts for each session
    session_data = []
    for session in sessions:
        # Count messages for this session
        msg_count_query = select(func.count(Message.id)).where(
            Message.session_id == session.id
        )
        msg_count_result = await db.execute(msg_count_query)
        msg_count = msg_count_result.scalar() or 0

        session_data.append(
            SessionListItem(
                id=session.id,
                scenario_id=session.scenario_id,
                scenario_title=session.scenario.title,
                teacher_id=session.teacher_id,
                teacher_nickname=session.teacher.nickname,
                started_at=session.started_at,
                ended_at=session.ended_at,
                message_count=msg_count,
            )
        )

    return SessionListResponse(
        sessions=session_data, total=len(session_data)
    )


@router.get("/admin/sessions/export")
async def export_sessions_csv(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    teacher_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """GET /admin/sessions/export - Export sessions as CSV (T096)."""
    # Check admin role
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    # Build query with joins (same as list_sessions)
    query = (
        select(Session)
        .options(
            selectinload(Session.scenario),
            selectinload(Session.teacher),
            selectinload(Session.messages),
        )
        .order_by(Session.started_at.desc())
    )

    # Apply filters (same logic as list_sessions)
    filters = []

    if date_from:
        try:
            date_from_dt = datetime.fromisoformat(date_from)
            filters.append(Session.started_at >= date_from_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_from format",
            )

    if date_to:
        try:
            date_to_dt = datetime.fromisoformat(date_to)
            filters.append(Session.started_at <= date_to_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_to format",
            )

    if teacher_id:
        filters.append(Session.teacher_id == teacher_id)

    if filters:
        query = query.where(and_(*filters))

    # Execute query
    result = await db.execute(query)
    sessions = result.scalars().all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(
        [
            "session_id",
            "scenario_title",
            "teacher_nickname",
            "started_at",
            "ended_at",
            "duration_minutes",
            "message_count",
            "teacher_message_count",
        ]
    )

    # Write data rows
    for session in sessions:
        # Calculate duration
        duration_minutes = None
        if session.ended_at:
            duration_seconds = (
                session.ended_at - session.started_at
            ).total_seconds()
            duration_minutes = round(duration_seconds / 60, 2)

        # Count teacher messages
        teacher_msg_count = sum(
            1 for msg in session.messages if msg.role == "teacher"
        )

        writer.writerow(
            [
                session.id,
                session.scenario.title,
                session.teacher.nickname,
                session.started_at.isoformat(),
                (
                    session.ended_at.isoformat()
                    if session.ended_at
                    else "Active"
                ),
                duration_minutes if duration_minutes else "N/A",
                len(session.messages),
                teacher_msg_count,
            ]
        )

    # Generate filename with timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"session_export_{timestamp}.csv"

    # Return CSV response
    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/csv; charset=utf-8",
        },
    )


@router.get("/admin/stats", response_model=StatsResponse)
async def get_statistics(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """GET /admin/stats - Aggregated statistics (T097)."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    # Total sessions
    total_query = select(func.count(Session.id))
    total_result = await db.execute(total_query)
    total_sessions = total_result.scalar() or 0

    # Total unique teachers
    teachers_query = select(func.count(func.distinct(Session.teacher_id)))
    teachers_result = await db.execute(teachers_query)
    total_teachers = teachers_result.scalar() or 0

    # Active sessions
    active_query = select(func.count(Session.id)).where(
        Session.ended_at.is_(None)
    )
    active_result = await db.execute(active_query)
    active_sessions = active_result.scalar() or 0

    # Avg duration (ended sessions only)
    ended_sessions = await db.execute(
        select(Session).where(Session.ended_at.isnot(None))
    )
    sessions_list = ended_sessions.scalars().all()

    avg_duration = 0.0
    if sessions_list:
        durations = [
            (s.ended_at - s.started_at).total_seconds() / 60
            for s in sessions_list
        ]
        avg_duration = sum(durations) / len(durations)

    # Avg questions per session
    msg_query = select(func.count(Message.id)).where(
        Message.role == "teacher"
    )
    msg_result = await db.execute(msg_query)
    total_questions = msg_result.scalar() or 0
    avg_questions = (
        total_questions / total_sessions if total_sessions > 0 else 0.0
    )

    return StatsResponse(
        total_sessions=total_sessions,
        total_teachers=total_teachers,
        avg_session_duration_minutes=round(avg_duration, 2),
        avg_questions_per_session=round(avg_questions, 2),
        active_sessions=active_sessions,
    )

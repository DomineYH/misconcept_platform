"""Admin session action routes."""
import logging
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session, templates
from src.models import (
    AnalysisFramework,
    Message,
    QuestionAnalysis,
    SessionSummary,
)
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.user import User
from src.services.analysis_pipeline import analyze_session
from src.utils.analysis_helpers import parse_reasoning

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/admin/sessions/{session_id}/end",
    response_class=HTMLResponse,
)
async def end_session(
    request: Request,
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """End an active session (set ended_at)."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already ended",
        )

    session.ended_at = datetime.now(timezone.utc)
    await db.commit()

    # Trigger analysis
    try:
        scenario_result = await db.execute(
            select(Scenario).where(
                Scenario.id == session.scenario_id
            )
        )
        scenario = scenario_result.scalar_one_or_none()
        if scenario and scenario.framework_id:
            framework_result = await db.execute(
                select(AnalysisFramework).where(
                    AnalysisFramework.id
                    == scenario.framework_id
                )
            )
            framework = (
                framework_result.scalar_one_or_none()
            )
            if framework:
                await analyze_session(
                    session_id,
                    session,
                    scenario,
                    framework,
                    db,
                )
    except Exception as e:
        logger.warning(
            f"Analysis failed for session {session_id}: {e}"
        )

    # Reload with summary
    await db.refresh(session, ["summary"])

    return templates.TemplateResponse(
        "partials/session_row.html",
        {"request": request, "session": session},
    )


@router.delete(
    "/admin/sessions/{session_id}",
    response_class=HTMLResponse,
)
async def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Soft delete a session (set deleted_at)."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already deleted",
        )

    session.mark_deleted()
    await db.commit()

    return Response(content="", status_code=200)


@router.get(
    "/admin/sessions/{session_id}/detail",
    response_class=HTMLResponse,
)
async def session_detail(
    request: Request,
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get session detail for viewing in modal."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return templates.TemplateResponse(
        "partials/session_detail.html",
        {"request": request, "session": session},
    )


@router.get(
    "/admin/sessions/{session_id}/analysis_modal",
    response_class=HTMLResponse,
)
async def analysis_modal(
    request: Request,
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get session analysis for admin modal view."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    query = (
        select(Session)
        .options(joinedload(Session.scenario))
        .where(Session.id == session_id)
    )
    result = await db.execute(query)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if not session.ended_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Session must be ended before"
                " viewing analysis"
            ),
        )

    summary_result = await db.execute(
        select(SessionSummary).where(
            SessionSummary.session_id == session_id
        )
    )
    summary = summary_result.scalar_one_or_none()

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )

    messages_result = await db.execute(
        select(Message, QuestionAnalysis)
        .outerjoin(
            QuestionAnalysis,
            Message.id == QuestionAnalysis.message_id,
        )
        .where(Message.session_id == session_id)
        .where(Message.role == "teacher")
        .order_by(Message.created_at)
    )
    message_analyses = messages_result.all()

    questions = []
    for msg, analysis in message_analyses:
        reasoning = None
        if analysis and analysis.meta_json:
            reasoning = parse_reasoning(analysis.meta_json)
        questions.append(
            {
                "content": msg.content,
                "label": (
                    analysis.label
                    if analysis
                    else "Unclassified"
                ),
                "confidence": (
                    analysis.confidence
                    if analysis
                    else None
                ),
                "reasoning": reasoning,
            }
        )

    return templates.TemplateResponse(
        "partials/analysis_modal.html",
        {
            "request": request,
            "user": user,
            "session_id": session_id,
            "distribution": summary.distribution,
            "feedback": summary.feedback,
            "questions": questions,
            "session_ended_at": session.ended_at.isoformat(),
            "is_admin": True,
        },
    )

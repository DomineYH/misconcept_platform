"""Session analysis routes."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session
from src.api.routes.session_helpers import load_session, mark_session_ended
from src.config import config
from src.models import (
    AnalysisFramework,
    Message,
    QuestionAnalysis,
    Scenario,
    Session,
    SessionSummary,
    User,
)
from src.services.analysis_pipeline import (
    analyze_session,
    handle_analysis_failure,
    handle_duplicate_summary,
)
from src.services.export import CSVExporter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Sessions"])
templates = Jinja2Templates(directory="src/templates")
limiter = Limiter(key_func=get_remote_address, enabled=not config.TESTING)


@router.post("/sessions/{session_id}/end")
@limiter.limit("10/minute")
async def end_session(
    request: Request,
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """End session without running analysis.

    This endpoint only marks the session as ended. Use the /analyze
    endpoint to run the analysis separately.
    """
    session = await load_session(session_id, user, db)
    await mark_session_ended(session, db, force=True)

    return {
        "ended": True,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
    }


@router.post("/sessions/{session_id}/analyze")
@limiter.limit("5/minute")
async def analyze_session_endpoint(
    request: Request,
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Analyze questions and generate summary for an ended session."""
    session = await load_session(session_id, user, db)

    # Session must be ended before analysis
    if not session.ended_at:
        raise HTTPException(
            status_code=400,
            detail="Session must be ended before analysis",
        )

    # Check for existing summary
    existing_summary_result = await db.execute(
        select(SessionSummary).where(SessionSummary.session_id == session_id)
    )
    existing_summary = existing_summary_result.scalar_one_or_none()

    if existing_summary:
        return {
            "distribution": existing_summary.distribution,
            "feedback": existing_summary.feedback,
        }

    # Load scenario and framework
    scenario_result = await db.execute(
        select(Scenario).where(Scenario.id == session.scenario_id)
    )
    scenario = scenario_result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    framework_result = await db.execute(
        select(AnalysisFramework).where(
            AnalysisFramework.id == scenario.framework_id
        )
    )
    framework = framework_result.scalar_one_or_none()
    if not framework:
        raise HTTPException(status_code=404, detail="Framework not found")

    try:
        return await analyze_session(
            session_id, session, scenario, framework, db
        )
    except IntegrityError as e:
        return await handle_duplicate_summary(session_id, framework, db, e)
    except Exception as e:
        return await handle_analysis_failure(session_id, framework, db, e)


@router.get("/sessions/{session_id}/analysis")
async def get_analysis(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get session analysis report."""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if not session.ended_at:
        raise HTTPException(
            status_code=400,
            detail="Session must be ended before viewing analysis",
        )

    summary_result = await db.execute(
        select(SessionSummary).where(SessionSummary.session_id == session_id)
    )
    summary = summary_result.scalar_one_or_none()

    if not summary:
        raise HTTPException(status_code=404, detail="Analysis not found")

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
            try:
                reasoning = json.loads(analysis.meta_json)
            except json.JSONDecodeError:
                reasoning = {
                    "summary": analysis.meta_json,
                    "pedagogical": None,
                    "cognitive": None,
                    "contextual": None,
                }
        questions.append(
            {
                "content": msg.content,
                "label": analysis.label if analysis else "Unclassified",
                "confidence": analysis.confidence if analysis else None,
                "reasoning": reasoning,
                "created_at": msg.created_at.isoformat(),
            }
        )

    return {
        "distribution": summary.distribution,
        "feedback": summary.feedback,
        "questions": questions,
        "session_ended_at": session.ended_at.isoformat(),
    }


@router.get(
    "/sessions/{session_id}/analysis_page", response_class=HTMLResponse
)
async def get_analysis_page(
    request: Request,
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Render analysis HTML page."""
    analysis_data = await get_analysis(session_id, user, db)

    return templates.TemplateResponse(
        "analysis.html",
        {
            "request": request,
            "user": user,
            "session_id": session_id,
            "distribution": analysis_data["distribution"],
            "feedback": analysis_data["feedback"],
            "questions": analysis_data["questions"],
            "session_ended_at": analysis_data["session_ended_at"],
        },
    )


@router.get(
    "/sessions/{session_id}/analysis_modal", response_class=HTMLResponse
)
async def get_analysis_modal(
    request: Request,
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Render analysis modal content (HTMX partial)."""
    analysis_data = await get_analysis(session_id, user, db)

    return templates.TemplateResponse(
        "partials/analysis_modal.html",
        {
            "request": request,
            "user": user,
            "session_id": session_id,
            **analysis_data,
        },
    )


@router.get("/sessions/{session_id}/export.csv")
async def export_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Export session with analysis to CSV."""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    exporter = CSVExporter()
    try:
        csv_content = await exporter.export_session(session_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=session_{session_id}_analysis.csv"
            )
        },
    )

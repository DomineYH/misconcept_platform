"""Admin session action routes."""

import json
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
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.api.dependencies import get_admin_user, get_db_session, templates
from src.config import config
from src.models import (
    AnalysisFramework,
    Message,
    QuestionAnalysis,
    SessionFeedbackReport,
    SessionSummary,
)
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.user import User
from src.services.analysis_pipeline import analyze_session, run_llm_pipeline
from src.utils.analysis_helpers import parse_reasoning
from src.utils.session_feedback import derive_plain_feedback

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address, enabled=not config.TESTING)


@router.post(
    "/admin/sessions/{session_id}/end",
    response_class=HTMLResponse,
)
async def end_session(
    request: Request,
    session_id: int,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """End an active session (set ended_at)."""
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
    await db.flush()

    # Trigger analysis
    try:
        scenario_result = await db.execute(
            select(Scenario).where(Scenario.id == session.scenario_id)
        )
        scenario = scenario_result.scalar_one_or_none()
        if scenario and scenario.framework_id:
            framework_result = await db.execute(
                select(AnalysisFramework).where(
                    AnalysisFramework.id == scenario.framework_id
                )
            )
            framework = framework_result.scalar_one_or_none()
            if framework:
                await analyze_session(
                    session_id,
                    session,
                    scenario,
                    framework,
                    db,
                )
    except Exception as e:
        logger.warning(f"Analysis failed for session {session_id}: {e}")

    # Reload with summary
    await db.refresh(session, ["summary"])

    return templates.TemplateResponse(
        "partials/session_row.html",
        {"request": request, "session": session},
    )


@router.post(
    "/admin/sessions/{session_id}/delete",
    response_class=HTMLResponse,
)
async def delete_session(
    session_id: int,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Soft delete a session (set deleted_at)."""
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
    await db.flush()

    return Response(content="", status_code=200)


@router.get(
    "/admin/sessions/{session_id}/detail",
    response_class=HTMLResponse,
)
async def session_detail(
    request: Request,
    session_id: int,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get session detail for viewing in modal."""
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
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get session analysis for admin modal view."""
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
            detail=("Session must be ended before" " viewing analysis"),
        )

    summary_result = await db.execute(
        select(SessionSummary).where(SessionSummary.session_id == session_id)
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
                "label": (analysis.label if analysis else "Unclassified"),
                "confidence": (analysis.confidence if analysis else None),
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


@router.post("/admin/sessions/{session_id}/analyze_regenerate")
@limiter.limit("2/minute")
async def regenerate_analysis(
    request: Request,
    session_id: int,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Regenerate session analysis (admin-only).

    Runs full synthesis pipeline. On LLM failure, old data is preserved.
    On success, replaces old report and summary atomically.
    """
    query = (
        select(Session)
        .options(joinedload(Session.scenario))
        .where(Session.id == session_id)
    )
    result = await db.execute(query)
    session = result.unique().scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if not session.ended_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session must be ended before analysis",
        )

    scenario = session.scenario
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )

    framework_result = await db.execute(
        select(AnalysisFramework).where(
            AnalysisFramework.id == scenario.framework_id
        )
    )
    framework = framework_result.scalar_one_or_none()
    if not framework:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Framework not found",
        )

    # Load all messages
    all_messages_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    all_messages = all_messages_result.scalars().all()
    teacher_messages = [m for m in all_messages if m.role == "teacher"]

    # Run LLM pipeline (no DB writes) — synthesize FIRST
    try:
        (
            distribution,
            question_analyses,
            payload,
            synthesis_status,
            synth_model,
            synth_hash,
        ) = await run_llm_pipeline(
            session_id, all_messages, teacher_messages, scenario, framework
        )
    except Exception as e:
        logger.error(
            "Regeneration LLM failed for session %d: %s",
            session_id,
            e,
            exc_info=True,
        )
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis regeneration failed",
        )

    feedback = (
        derive_plain_feedback(payload)
        if synthesis_status != "failed"
        else (
            "분석에 실패했습니다. "
            "잠시 후 다시 시도하거나 관리자에게 문의하세요."
        )
    )

    # Delete old data
    msg_ids_subquery = select(Message.id).where(
        Message.session_id == session_id
    )
    await db.execute(
        sql_delete(QuestionAnalysis).where(
            QuestionAnalysis.message_id.in_(msg_ids_subquery)
        )
    )
    await db.execute(
        sql_delete(SessionFeedbackReport).where(
            SessionFeedbackReport.session_id == session_id
        )
    )
    await db.execute(
        sql_delete(SessionSummary).where(
            SessionSummary.session_id == session_id
        )
    )

    # Insert new data
    for qa in question_analyses:
        db.add(qa)

    db.add(
        SessionFeedbackReport(
            session_id=session_id,
            version=1,
            model=synth_model,
            prompt_hash=synth_hash,
            status=synthesis_status,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
    )

    db.add(
        SessionSummary(
            session_id=session_id,
            distribution_json=json.dumps(distribution),
            feedback=feedback,
        )
    )

    await db.commit()

    # Compute stats
    stats_result = await db.execute(
        select(Message.role, func.count())
        .where(Message.session_id == session_id)
        .group_by(Message.role)
    )
    role_counts = dict(stats_result.all())

    duration_seconds = None
    if session.ended_at and session.started_at:
        duration_seconds = int(
            (session.ended_at - session.started_at).total_seconds()
        )

    # Build questions response
    teacher_msg_map = {m.id: m for m in all_messages if m.role == "teacher"}
    qa_by_msg = {qa.message_id: qa for qa in question_analyses}
    questions = []
    for msg_id, msg in teacher_msg_map.items():
        qa = qa_by_msg.get(msg_id)
        reasoning = None
        if qa and qa.meta_json:
            reasoning = parse_reasoning(qa.meta_json)
        questions.append(
            {
                "content": msg.content,
                "label": qa.label if qa else "Unclassified",
                "confidence": qa.confidence if qa else None,
                "reasoning": reasoning,
                "created_at": msg.created_at.isoformat(),
            }
        )

    feedback_sections = {
        "brief_feedback": payload.get("brief_feedback"),
        "strengths": payload.get("strengths"),
        "improvements": payload.get("improvements"),
        "dialogue_coaching": payload.get("dialogue_coaching"),
    }

    return {
        "distribution": distribution,
        "feedback": feedback,
        "feedback_status": synthesis_status,
        "feedback_sections": feedback_sections,
        "stats": {
            "duration_seconds": duration_seconds,
            "teacher_question_count": role_counts.get("teacher", 0),
            "student_response_count": role_counts.get("student", 0),
            "tutor_intervention_count": session.tutor_intervention_count,
        },
        "questions": questions,
        "session_ended_at": session.ended_at.isoformat(),
    }

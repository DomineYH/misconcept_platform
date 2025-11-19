"""Session and message management routes."""

import logging
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session
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
from src.services.analyzer import Analyzer
from src.services.export import CSVExporter
from src.services.session_mgr import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Sessions"])
templates = Jinja2Templates(directory="src/templates")
limiter = Limiter(key_func=get_remote_address, enabled=not config.TESTING)


# Helper functions for session management
async def _load_session(
    session_id: int,
    user: User,
    db: AsyncSession,
) -> Session:
    """Load session and validate ownership.

    Args:
        session_id: Session ID to load
        user: Current user from auth
        db: Database session

    Returns:
        Session object

    Raises:
        HTTPException: 404 if not found or wrong owner, 403 if forbidden
    """
    result = await db.execute(
        select(Session).where(
            Session.id == session_id, Session.deleted_at.is_(None)
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return session


async def _mark_session_ended(
    session: Session,
    db: AsyncSession,
    *,
    force: bool = False,
) -> tuple[datetime, bool]:
    """Mark session as ended by setting ended_at timestamp.

    Args:
        session: Session to mark as ended
        db: Database session
        force: If True, allows idempotent behavior (no error if already ended)

    Returns:
        Tuple of (ended_at timestamp, was_already_ended boolean)

    Raises:
        HTTPException: 400 if already ended and force=False
    """
    if session.ended_at:
        if not force:
            raise HTTPException(status_code=400, detail="Session already ended")
        return session.ended_at, True

    session.ended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)

    return session.ended_at, False


class CreateSessionRequest(BaseModel):
    """Request schema for creating session."""

    scenario_id: int


class SessionResponse(BaseModel):
    """Response schema for session creation."""

    id: int
    scenario_id: int
    started_at: str


class CloseSessionResponse(BaseModel):
    """Response schema for session close operation."""

    status: str
    ended_at: str
    already_ended: bool


@router.post("/sessions", status_code=201)
async def create_session(
    data: CreateSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    """Start new dialogue session."""
    # Create session
    session = Session(scenario_id=data.scenario_id, teacher_id=user.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return SessionResponse(
        id=session.id,
        scenario_id=session.scenario_id,
        started_at=session.started_at.isoformat(),
    )


@router.post("/sessions/{session_id}/messages")
@limiter.limit("30/minute")
async def send_message(
    request: Request,
    session_id: int,
    content: str = Form(..., min_length=1, max_length=5000),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Send teacher message and get bot responses."""
    # Load and validate session
    session = await _load_session(session_id, user, db)

    # Check if session is already ended
    if session.ended_at:
        raise HTTPException(
            status_code=400,
            detail="Session already ended. Cannot send messages to ended sessions.",
        )

    # Validate content (Form already validates min_length=1)
    if not content or len(content) < 1:
        raise HTTPException(status_code=400, detail="Content cannot be empty")

    # Process message through SessionManager
    manager = SessionManager(db, session_id)
    new_messages = await manager.process_teacher_message(content)

    # Render messages as HTML for immediate HTMX display
    # (Previously returned JSON which caused 2-second delay)
    rendered_messages = []
    for message in new_messages:
        try:
            # Validate message has required attributes
            if not hasattr(message, "id") or message.id is None:
                logger.error(
                    f"Message missing 'id' attribute. "
                    f"role={getattr(message, 'role', None)}"
                )
                continue

            if not hasattr(message, "role") or not message.role:
                logger.error(f"Message {message.id} missing 'role' attribute")
                continue

            if not hasattr(message, "content"):
                logger.error(f"Message {message.id} missing 'content' attribute")
                continue

            # Render message HTML
            html = templates.get_template("partials/message.html").render(
                message=message, request=request
            )

            # Validate rendered HTML contains expected structure
            if not html or 'class="message' not in html:
                logger.error(
                    f"Rendered HTML invalid or empty for message {message.id}. "
                    f"HTML length: {len(html) if html else 0}"
                )
                continue

            rendered_messages.append(html)
            logger.debug(
                f"Successfully rendered message {message.id} ({message.role})"
            )

        except Exception as e:
            logger.error(
                f"Failed to render message {getattr(message, 'id', 'unknown')}: {e}",
                exc_info=True,
            )
            continue

    combined_html = "".join(rendered_messages)

    # Return 500 if no messages could be rendered
    if not combined_html:
        logger.error(
            f"No messages rendered for session {session_id}. "
            f"Total messages attempted: {len(new_messages)}"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to render bot responses. Check server logs.",
        )

    logger.info(
        f"Rendered {len(rendered_messages)}/{len(new_messages)} messages "
        f"for session {session_id}"
    )

    return Response(
        content=combined_html,
        media_type="text/html",
        status_code=200,
    )


@router.get("/sessions/{session_id}/messages/updates")
async def get_message_updates(
    request: Request,
    session_id: int,
    since: int | None = Query(None, description="Last message ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Get new messages since last message ID for HTMX polling."""
    # Validate session exists and belongs to user
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.teacher_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    # Build query for new messages
    query = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
        .limit(50)
    )

    # Filter by 'since' parameter if provided
    if since is not None:
        query = query.where(Message.id > since)

    # Execute query
    messages_result = await db.execute(query)
    messages = messages_result.scalars().all()

    # Return 204 if no new messages
    if not messages:
        return Response(status_code=204)

    # Render each message using partial template
    rendered_messages = []
    for message in messages:
        try:
            # Validate message attributes (same as send_message)
            if not hasattr(message, "id") or message.id is None:
                logger.error(
                    f"Polling: Message missing 'id'. "
                    f"role={getattr(message, 'role', None)}"
                )
                continue

            if not hasattr(message, "role") or not message.role:
                logger.error(f"Polling: Message {message.id} missing 'role'")
                continue

            if not hasattr(message, "content"):
                logger.error(f"Polling: Message {message.id} missing 'content'")
                continue

            # Render message HTML
            html = templates.get_template("partials/message.html").render(
                message=message, request=request
            )

            # Validate rendered HTML
            if not html or 'class="message' not in html:
                logger.error(
                    f"Polling: Invalid HTML for message {message.id}. "
                    f"Length: {len(html) if html else 0}"
                )
                continue

            rendered_messages.append(html)

        except Exception as e:
            logger.error(
                f"Polling: Failed to render message "
                f"{getattr(message, 'id', 'unknown')}: {e}",
                exc_info=True,
            )
            continue

    # Combine all rendered messages
    combined_html = "".join(rendered_messages)

    # Return 204 if all rendering failed
    if not combined_html:
        logger.warning(
            f"Polling: No messages rendered from {len(messages)} messages "
            f"for session {session_id}"
        )
        return Response(status_code=204)

    logger.debug(
        f"Polling: Rendered {len(rendered_messages)}/{len(messages)} messages "
        f"for session {session_id}"
    )

    return Response(
        content=combined_html,
        media_type="text/html",
        status_code=200,
    )


@router.post("/sessions/{session_id}/close")
@limiter.limit("30/minute")
async def close_session(
    request: Request,
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> CloseSessionResponse:
    """Close session without analysis (lightweight termination).

    This endpoint is idempotent - calling it multiple times will
    succeed without error. Used when user navigates away from chat
    without clicking "대화 종료" button.

    Returns:
        CloseSessionResponse with ended_at timestamp and already_ended flag
    """
    # Load and validate session
    session = await _load_session(session_id, user, db)

    # Mark session as ended (idempotent with force=True)
    ended_at, already_ended = await _mark_session_ended(
        session, db, force=True
    )

    return CloseSessionResponse(
        status="ended",
        ended_at=ended_at.isoformat(),
        already_ended=already_ended,
    )


@router.post("/sessions/{session_id}/end")
@limiter.limit("10/minute")
async def end_session(
    request: Request,
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """End session, analyze questions, and generate summary (T066)."""
    # Load and validate session
    session = await _load_session(session_id, user, db)

    # Mark session as ended (non-idempotent, raises error if already ended)
    await _mark_session_ended(session, db, force=False)

    # Load scenario and framework for analysis
    scenario_result = await db.execute(
        select(Scenario).where(Scenario.id == session.scenario_id)
    )
    scenario = scenario_result.scalar_one()

    framework_result = await db.execute(
        select(AnalysisFramework).where(
            AnalysisFramework.id == scenario.framework_id
        )
    )
    framework = framework_result.scalar_one()

    # Load all messages once (T111: fix N+1 query issue)
    all_messages_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    all_messages = all_messages_result.scalars().all()

    # Filter teacher messages
    teacher_messages = [m for m in all_messages if m.role == "teacher"]

    # Analyze each teacher message
    analyzer = Analyzer()
    distribution = {label: 0 for label in framework.labels}

    for idx, msg in enumerate(teacher_messages):
        try:
            # Build context from previous messages (no DB query)
            msg_idx = all_messages.index(msg)
            context_messages = all_messages[max(0, msg_idx - 3) : msg_idx]
            context = "\n".join(
                [f"{m.role}: {m.content}" for m in context_messages]
            )

            # Classify question with scenario context
            result = await analyzer.classify_question(
                question=msg.content,
                framework=framework,
                context=context,
                scenario_title=scenario.title,
                misconception_prompt=scenario.prompt,
                student_profile=scenario.student_profile or "Grade 5 student",
            )

            # Create QuestionAnalysis record
            analysis = QuestionAnalysis(
                message_id=msg.id,
                label=result["label"],
                confidence=result.get("confidence"),
                meta_json=result.get("reasoning"),
            )
            db.add(analysis)

            # Update distribution
            distribution[result["label"]] += 1

        except Exception as e:
            # Log error but continue processing
            print(f"Failed to analyze message {msg.id}: {e}")
            continue

    await db.commit()

    # Generate SessionSummary
    import json

    feedback = (
        f"Session analysis complete. Classified "
        f"{len(teacher_messages)} teacher questions."
    )

    summary = SessionSummary(
        session_id=session_id,
        distribution_json=json.dumps(distribution),
        feedback=feedback,
    )
    db.add(summary)
    await db.commit()

    return {"distribution": distribution, "feedback": feedback}


@router.get("/sessions/{session_id}/analysis")
async def get_analysis(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get session analysis report (T067)."""
    # Validate session
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Check if session ended
    if not session.ended_at:
        raise HTTPException(
            status_code=400,
            detail="Session must be ended before viewing analysis",
        )

    # Load session summary
    summary_result = await db.execute(
        select(SessionSummary).where(SessionSummary.session_id == session_id)
    )
    summary = summary_result.scalar_one_or_none()

    if not summary:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Load teacher messages with analyses
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

    # Format question list
    questions = []
    for msg, analysis in message_analyses:
        questions.append(
            {
                "content": msg.content,
                "label": analysis.label if analysis else "Unclassified",
                "confidence": (analysis.confidence if analysis else None),
                "created_at": msg.created_at.isoformat(),
            }
        )

    return {
        "distribution": summary.distribution,
        "feedback": summary.feedback,
        "questions": questions,
        "session_ended_at": session.ended_at.isoformat(),
    }


@router.get("/sessions/{session_id}/analysis_page", response_class=HTMLResponse)
async def get_analysis_page(
    request: Request,
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Render analysis HTML page (T069)."""
    # Get analysis data
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


@router.get("/sessions/{session_id}/export.csv")
async def export_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Export session with analysis to CSV (T068)."""
    # Validate session
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Generate CSV using CSVExporter
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
                f"attachment; " f"filename=session_{session_id}_analysis.csv"
            )
        },
    )

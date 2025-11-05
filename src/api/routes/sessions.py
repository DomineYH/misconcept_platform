"""Session and message management routes."""
from datetime import datetime
from fastapi import (
    APIRouter,
    Depends,
    Request,
    HTTPException,
    status,
)
from fastapi.responses import Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_current_user
from src.models import (
    User,
    Session,
    Message,
    Scenario,
    QuestionAnalysis,
    SessionSummary,
    AnalysisFramework,
)
from src.services.session_mgr import SessionManager
from src.services.analyzer import Analyzer
from src.services.export import CSVExporter

router = APIRouter(tags=["Sessions"])
templates = Jinja2Templates(directory="src/templates")


class CreateSessionRequest(BaseModel):
    """Request schema for creating session."""

    scenario_id: int


class SendMessageRequest(BaseModel):
    """Request schema for sending message."""

    content: str


class SessionResponse(BaseModel):
    """Response schema for session creation."""

    id: int
    scenario_id: int
    started_at: str


class MessageResponse(BaseModel):
    """Response schema for message."""

    id: int
    role: str
    content: str
    created_at: str


@router.post("/sessions", status_code=201)
async def create_session(
    data: CreateSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    """Start new dialogue session."""
    # Create session
    session = Session(
        scenario_id=data.scenario_id, teacher_id=user.id
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return SessionResponse(
        id=session.id,
        scenario_id=session.scenario_id,
        started_at=session.started_at.isoformat(),
    )


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    data: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Send teacher message and get bot responses."""
    # Validate session belongs to user
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=404, detail="Session not found"
        )

    if session.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Validate content
    if not data.content or len(data.content) < 1:
        raise HTTPException(
            status_code=400, detail="Content cannot be empty"
        )

    # Process message through SessionManager
    manager = SessionManager(db, session_id)
    new_messages = await manager.process_teacher_message(data.content)

    # Return new messages
    messages_data = [
        MessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at.isoformat(),
        )
        for msg in new_messages
    ]

    return {"messages": [msg.dict() for msg in messages_data]}


@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """End session, analyze questions, and generate summary (T066)."""
    # Validate session
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=404, detail="Session not found"
        )

    if session.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Check if already ended
    if session.ended_at:
        raise HTTPException(
            status_code=400, detail="Session already ended"
        )

    # Update Session.ended_at timestamp
    session.ended_at = datetime.utcnow()
    await db.commit()

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

    # Load all teacher messages from session
    messages_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .where(Message.role == "teacher")
        .order_by(Message.created_at)
    )
    teacher_messages = messages_result.scalars().all()

    # Analyze each teacher message
    analyzer = Analyzer()
    distribution = {label: 0 for label in framework.labels}

    for msg in teacher_messages:
        try:
            # Build context from previous messages
            context_result = await db.execute(
                select(Message)
                .where(Message.session_id == session_id)
                .where(Message.created_at < msg.created_at)
                .order_by(Message.created_at.desc())
                .limit(3)
            )
            context_messages = context_result.scalars().all()
            context = "\n".join(
                [f"{m.role}: {m.content}" for m in context_messages]
            )

            # Classify question
            result = await analyzer.classify_question(
                msg.content, framework, context
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
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=404, detail="Session not found"
        )

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
        select(SessionSummary).where(
            SessionSummary.session_id == session_id
        )
    )
    summary = summary_result.scalar_one_or_none()

    if not summary:
        raise HTTPException(
            status_code=404, detail="Analysis not found"
        )

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
        questions.append({
            "content": msg.content,
            "label": analysis.label if analysis else "Unclassified",
            "confidence": (
                analysis.confidence if analysis else None
            ),
            "created_at": msg.created_at.isoformat(),
        })

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
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=404, detail="Session not found"
        )

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
                f"attachment; "
                f"filename=session_{session_id}_analysis.csv"
            )
        },
    )

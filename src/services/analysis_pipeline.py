"""Session analysis pipeline service.

Handles the analysis of teacher messages in a session, including
greeting detection, question classification, and summary generation.
"""

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import (
    AnalysisFramework,
    Message,
    QuestionAnalysis,
    Scenario,
    Session,
    SessionSummary,
)
from src.services.analyzer import Analyzer

logger = logging.getLogger(__name__)

FALLBACK_FEEDBACK = (
    "분석에 실패했습니다. 잠시 후 다시 시도하거나 관리자에게 문의하세요."
)


async def analyze_session(
    session_id: int,
    session: Session,
    scenario: Scenario,
    framework: AnalysisFramework,
    db: AsyncSession,
) -> dict[str, Any]:
    """Perform session analysis and create summary.

    Args:
        session_id: Session ID
        session: Session object
        scenario: Scenario object
        framework: Analysis framework
        db: Database session

    Returns:
        Dict with distribution and feedback
    """
    all_messages_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    all_messages = all_messages_result.scalars().all()

    teacher_messages = [m for m in all_messages if m.role == "teacher"]
    analyzer = Analyzer()

    # Filter greeting messages
    if teacher_messages:
        teacher_messages = await _filter_greetings(
            session_id, teacher_messages, analyzer
        )

    # Analyze each teacher message
    distribution = {label: 0 for label in framework.labels}

    for msg in teacher_messages:
        try:
            msg_idx = all_messages.index(msg)
            context_messages = all_messages[max(0, msg_idx - 3) : msg_idx]
            context = "\n".join(
                [f"{m.role}: {m.content}" for m in context_messages]
            )

            result = await analyzer.classify_question(
                question=msg.content,
                framework=framework,
                context=context,
                scenario_title=scenario.title,
                misconception_prompt=scenario.prompt,
                student_profile=scenario.student_profile or "Grade 5 student",
            )

            reasoning = result.get("reasoning")
            reasoning_json = (
                json.dumps(reasoning, ensure_ascii=False)
                if isinstance(reasoning, dict)
                else reasoning
            )
            analysis = QuestionAnalysis(
                message_id=msg.id,
                label=result["label"],
                confidence=result.get("confidence"),
                meta_json=reasoning_json,
            )
            db.add(analysis)

            distribution[result["label"]] += 1

        except Exception as e:
            logger.warning(f"Failed to analyze message {msg.id}: {e}")
            continue

    await db.commit()

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


async def _filter_greetings(
    session_id: int,
    teacher_messages: list[Message],
    analyzer: Analyzer,
) -> list[Message]:
    """Filter greeting messages from analysis."""
    greeting_results = await analyzer.detect_greetings(
        [m.content for m in teacher_messages]
    )

    filtered_messages = []
    for msg, result in zip(teacher_messages, greeting_results):
        if not result.get("is_greeting", False):
            filtered_messages.append(msg)
        else:
            logger.info(
                f"Filtered greeting message {msg.id}: "
                f"{result.get('reason', 'greeting')}"
            )

    filtered_count = len(teacher_messages) - len(filtered_messages)
    if filtered_count > 0:
        logger.info(
            f"Session {session_id}: Filtered {filtered_count} "
            f"greeting messages from analysis"
        )

    return filtered_messages


async def handle_duplicate_summary(
    session_id: int,
    framework: AnalysisFramework,
    db: AsyncSession,
    error: IntegrityError,
) -> dict[str, Any]:
    """Handle duplicate summary insert (concurrent requests)."""
    await db.rollback()
    logger.warning(
        f"Session {session_id}: duplicate summary insert detected: {error}"
    )
    summary_result = await db.execute(
        select(SessionSummary).where(SessionSummary.session_id == session_id)
    )
    summary = summary_result.scalar_one_or_none()
    if summary:
        return {
            "distribution": summary.distribution,
            "feedback": summary.feedback,
        }

    return await create_fallback_summary(session_id, framework, db)


async def handle_analysis_failure(
    session_id: int,
    framework: AnalysisFramework,
    db: AsyncSession,
    error: Exception,
) -> dict[str, Any]:
    """Handle analysis pipeline failure with fallback."""
    await db.rollback()
    logger.error(
        f"Session {session_id}: analysis pipeline failed: {error}",
        exc_info=True,
    )

    return await create_fallback_summary(session_id, framework, db)


async def create_fallback_summary(
    session_id: int,
    framework: AnalysisFramework,
    db: AsyncSession,
) -> dict[str, Any]:
    """Create fallback summary when analysis fails."""
    fallback_distribution = {label: 0 for label in framework.labels}

    try:
        summary = SessionSummary(
            session_id=session_id,
            distribution_json=json.dumps(fallback_distribution),
            feedback=FALLBACK_FEEDBACK,
        )
        db.add(summary)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        summary_result = await db.execute(
            select(SessionSummary).where(
                SessionSummary.session_id == session_id
            )
        )
        summary = summary_result.scalar_one_or_none()
        if summary:
            return {
                "distribution": summary.distribution,
                "feedback": summary.feedback,
            }

    return {
        "distribution": fallback_distribution,
        "feedback": FALLBACK_FEEDBACK,
        "error": "analysis_failed",
    }

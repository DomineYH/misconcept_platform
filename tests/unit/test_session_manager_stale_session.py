import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count
from typing import Literal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AnalysisFramework, ApiUsageLog, Message, Scenario
from src.models import Session as DialogueSession
from src.services.session_lifecycle import (
    StaleSessionError,
    ensure_session_writable,
)
from src.services.session_mgr import SessionManager
from src.services.session_usage import log_api_usage


@dataclass(frozen=True, slots=True)
class ScenarioStub:
    prompt: str = "Student thinks the moon makes its own light."
    student_profile: str = "Grade 5 student"
    title: str = "Moon Phases"


StaleAction = Callable[[AsyncSession, int], Awaitable[None]]
_SESSION_SEED_COUNTER = count(1)


async def _seed_dialogue_session(db: AsyncSession) -> int:
    framework = AnalysisFramework(
        name=f"Lifecycle Guard {next(_SESSION_SEED_COUNTER)}",
        description="For stale session regression tests",
        labels_json=json.dumps(["Pressing", "Linking"]),
    )
    db.add(framework)
    await db.flush()

    scenario = Scenario(
        title="Moon Phases",
        prompt="Student thinks the moon makes its own light.",
        student_profile="Grade 5 student",
        framework_id=framework.id,
    )
    db.add(scenario)
    await db.flush()

    session = DialogueSession(scenario_id=scenario.id)
    db.add(session)
    await db.commit()
    return session.id


async def _assert_foreign_keys_enabled(db: AsyncSession) -> None:
    result = await db.execute(text("PRAGMA foreign_keys"))
    assert result.scalar_one() == 1


async def _delete_session(db: AsyncSession, session_id: int) -> None:
    await db.execute(
        delete(DialogueSession).where(DialogueSession.id == session_id)
    )
    await db.commit()


async def _soft_delete_session(db: AsyncSession, session_id: int) -> None:
    session = await db.get(DialogueSession, session_id)
    assert session is not None
    session.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def _end_session(db: AsyncSession, session_id: int) -> None:
    session = await db.get(DialogueSession, session_id)
    assert session is not None
    session.ended_at = datetime.now(timezone.utc)
    await db.commit()


def _manager_with_stale_after_teacher_commit(
    db: AsyncSession,
    session_id: int,
    stale_action: StaleAction,
) -> SessionManager:
    manager = SessionManager(db_session=db, session_id=session_id)
    manager.scenario = ScenarioStub()

    async def generate_response(
        teacher_content: str,
        history: list[dict[str, str]],
    ) -> tuple[str, dict[str, int]]:
        assert teacher_content == "Why does the moon shine?"
        assert history == []
        await stale_action(db, session_id)
        return (
            "Because the moon is a light source.",
            {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        )

    student_bot = AsyncMock()
    student_bot.model = "gpt-5"
    student_bot.generate_response = AsyncMock(side_effect=generate_response)
    manager.student_bot = student_bot

    analyzer = AsyncMock()
    analyzer.analyze_student_response = AsyncMock(
        return_value={"maintains_misconception": True}
    )
    manager.misconception_analyzer = analyzer

    tutor_bot = AsyncMock()
    tutor_bot.model = "gpt-5.2"
    tutor_bot.intervention_count = 7
    tutor_bot.question_count = 11
    tutor_bot.generate_feedback = AsyncMock(
        return_value=(
            "Ask the student to compare reflected light.",
            {
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30,
            },
        )
    )
    manager.tutor_bot = tutor_bot
    return manager


def _assert_stale_session_error(
    exc: StaleSessionError,
    session_id: int,
) -> None:
    assert str(session_id) in str(exc)


async def _count_messages(db: AsyncSession, session_id: int) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Message)
        .where(Message.session_id == session_id)
    )
    return result.scalar_one()


async def _count_usage_logs(db: AsyncSession, session_id: int) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(ApiUsageLog)
        .where(ApiUsageLog.session_id == session_id)
    )
    return result.scalar_one()


async def _message_roles(db: AsyncSession, session_id: int) -> list[str]:
    result = await db.execute(
        select(Message.role)
        .where(Message.session_id == session_id)
        .order_by(Message.id)
    )
    return list(result.scalars())


async def test_process_teacher_message_stale_after_session_delete(
    db_session: AsyncSession,
) -> None:
    session_id = await _seed_dialogue_session(db_session)
    await _assert_foreign_keys_enabled(db_session)
    manager = _manager_with_stale_after_teacher_commit(
        db_session,
        session_id,
        _delete_session,
    )

    with pytest.raises(StaleSessionError) as exc_info:
        await manager.process_teacher_message("Why does the moon shine?")

    await db_session.rollback()
    _assert_stale_session_error(exc_info.value, session_id)
    assert await _count_messages(db_session, session_id) == 0
    assert await _count_usage_logs(db_session, session_id) == 0


@pytest.mark.parametrize(
    ("stale_action", "reason"),
    [
        (_soft_delete_session, "deleted"),
        (_end_session, "ended"),
    ],
)
async def test_process_teacher_message_rejects_stale_before_student_flush(
    db_session: AsyncSession,
    stale_action: StaleAction,
    reason: Literal["deleted", "ended"],
) -> None:
    session_id = await _seed_dialogue_session(db_session)
    manager = _manager_with_stale_after_teacher_commit(
        db_session,
        session_id,
        stale_action,
    )

    with pytest.raises(StaleSessionError) as exc_info:
        await manager.process_teacher_message("Why does the moon shine?")

    await db_session.rollback()
    _assert_stale_session_error(exc_info.value, session_id)
    assert reason in str(exc_info.value)
    assert await _message_roles(db_session, session_id) == ["teacher"]
    assert await _count_usage_logs(db_session, session_id) == 0

    session = await db_session.get(DialogueSession, session_id)
    assert session is not None
    assert session.tutor_intervention_count == 0
    assert session.tutor_question_count == 0


async def test_ensure_session_writable_rejects_deleted_or_ended_sessions(
    db_session: AsyncSession,
) -> None:
    deleted_session_id = await _seed_dialogue_session(db_session)
    await _soft_delete_session(db_session, deleted_session_id)

    with pytest.raises(StaleSessionError) as deleted_error:
        await ensure_session_writable(db_session, deleted_session_id)
    _assert_stale_session_error(deleted_error.value, deleted_session_id)
    assert "deleted" in str(deleted_error.value)

    ended_session_id = await _seed_dialogue_session(db_session)
    await _end_session(db_session, ended_session_id)

    with pytest.raises(StaleSessionError) as ended_error:
        await ensure_session_writable(db_session, ended_session_id)
    _assert_stale_session_error(ended_error.value, ended_session_id)
    assert "ended" in str(ended_error.value)


async def test_initialize_raises_stale_session_when_session_missing(
    db_session: AsyncSession,
) -> None:
    missing_session_id = 999_999
    manager = SessionManager(
        db_session=db_session,
        session_id=missing_session_id,
    )

    with pytest.raises(StaleSessionError) as exc_info:
        await manager.initialize()

    _assert_stale_session_error(exc_info.value, missing_session_id)
    assert "missing" in str(exc_info.value)


async def test_log_api_usage_re_raises_stale_session_error(
    db_session: AsyncSession,
) -> None:
    session_id = await _seed_dialogue_session(db_session)
    await _soft_delete_session(db_session, session_id)

    with pytest.raises(StaleSessionError) as exc_info:
        await log_api_usage(
            db=db_session,
            session_id=session_id,
            bot_type="student",
            model="gpt-5",
            usage_dict={
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        )

    _assert_stale_session_error(exc_info.value, session_id)
    assert "deleted" in str(exc_info.value)
    assert await _count_usage_logs(db_session, session_id) == 0

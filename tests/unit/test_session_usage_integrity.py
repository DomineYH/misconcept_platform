import json
import logging
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AnalysisFramework, ApiUsageLog, Scenario
from src.models import Session as DialogueSession
from src.services import session_usage
from src.services.session_lifecycle import (
    StaleSessionError,
    ensure_session_writable,
)
from src.services.session_usage import log_api_usage


async def _seed_dialogue_session(db: AsyncSession) -> int:
    framework = AnalysisFramework(
        name="Usage Integrity",
        description="For API usage integrity regression tests",
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


async def _count_usage_logs(db: AsyncSession, session_id: int) -> int:
    result = await db.execute(
        select(func.count(ApiUsageLog.id)).where(
            ApiUsageLog.session_id == session_id
        )
    )
    return result.scalar_one()


async def test_log_api_usage_re_raises_unrelated_integrity_error(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = await _seed_dialogue_session(db_session)

    async def fail_with_unrelated_integrity_error(
        db: AsyncSession,
        session_id: int,
    ) -> None:
        session = await ensure_session_writable(db, session_id)
        assert session.id == session_id
        raise IntegrityError(
            "INSERT api_usage_logs",
            {},
            RuntimeError("unrelated integrity failure"),
        )

    monkeypatch.setattr(
        session_usage,
        "flush_with_stale_session_check",
        fail_with_unrelated_integrity_error,
    )

    with pytest.raises(IntegrityError, match="unrelated integrity failure"):
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

    await db_session.rollback()
    assert await _count_usage_logs(db_session, session_id) == 0


async def test_log_api_usage_re_raises_stale_session_error(
    db_session: AsyncSession,
) -> None:
    session_id = await _seed_dialogue_session(db_session)
    session = await db_session.get(DialogueSession, session_id)
    assert session is not None
    session.deleted_at = datetime.now(timezone.utc)
    await db_session.commit()

    with pytest.raises(StaleSessionError, match="deleted"):
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

    assert await _count_usage_logs(db_session, session_id) == 0


async def test_log_api_usage_warns_and_returns_when_usage_missing(
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="src.services.session_usage"):
        await log_api_usage(
            db=db_session,
            session_id=999_999,
            bot_type="tutor",
            model="gpt-5",
            usage_dict=None,
        )

    assert "No usage info for tutor bot (model: gpt-5)" in caplog.text

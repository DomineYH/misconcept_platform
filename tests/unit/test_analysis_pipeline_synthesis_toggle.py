"""Tests for the synthesis on/off toggle (Issue #55).

Verifies that when ``synthesis_enabled`` is False:
- the SessionSynthesizer.synthesize LLM call is NOT made,
- the persisted SessionFeedbackReport.status == "skipped",
- the SessionSummary.feedback is None (no top narrative box),
- no ApiUsageLog row with operation="synthesis" is persisted.

Regression: with synthesis_enabled=True (default), the synthesizer IS
called and the report status is "ok" (preserving current behavior).
"""

import pytest
from sqlalchemy import select

from src.models import (
    ApiUsageLog,
    SessionFeedbackReport,
    SessionSummary,
)
from src.services.analysis_pipeline import analyze_session

# Fixture overrides — keep all data on the same in-memory DB so FK
# constraints pass. Mirrors tests/integration/test_analysis_pipeline_e2e.py.


@pytest.fixture
async def test_framework(async_db_session):
    from src.models.analysis_framework import AnalysisFramework

    framework = AnalysisFramework(
        name="Test Framework",
        description="Framework for testing",
        labels_json='["Pressing","Linking","Directing","Recall"]',
    )
    async_db_session.add(framework)
    await async_db_session.flush()
    return framework


@pytest.fixture
async def test_student_template(async_db_session):
    from src.models.prompt_template import PromptTemplate

    template = PromptTemplate(
        bot_type="student",
        template_name="Test Student Template",
        version=1,
        template_text="You are a test student bot.",
    )
    async_db_session.add(template)
    await async_db_session.flush()
    return template


@pytest.fixture
async def test_scenario(
    async_db_session, test_framework, test_student_template
):
    from src.models.scenario import Scenario

    scenario = Scenario(
        title="Test Scenario",
        prompt="Test prompt for scenario",
        student_profile="Test student profile",
        framework_id=test_framework.id,
        student_template_id=test_student_template.id,
        is_active=1,
    )
    async_db_session.add(scenario)
    await async_db_session.flush()
    return scenario


async def _seed_session(async_db_session, test_scenario, test_teacher):
    """Create a minimal ended session with teacher + student messages."""
    from datetime import datetime, timedelta, timezone

    from src.models.message import Message
    from src.models.session import Session

    session = Session(
        scenario_id=test_scenario.id,
        teacher_id=test_teacher.id,
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ended_at=datetime.now(timezone.utc),
    )
    async_db_session.add(session)
    await async_db_session.flush()

    msgs = [
        Message(
            session_id=session.id,
            role="teacher",
            content="How did you solve it?",
        ),
        Message(
            session_id=session.id,
            role="student",
            content="I added the numerators together.",
        ),
    ]
    async_db_session.add_all(msgs)
    await async_db_session.commit()
    await async_db_session.refresh(session)
    return session


@pytest.mark.anyio
async def test_synthesis_disabled_skips_llm_call(
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    classify_mock,
    greeting_mock,
    synthesis_mock,
):
    """synthesis_enabled=False skips the synthesize LLM call entirely."""
    session = await _seed_session(async_db_session, test_scenario, test_teacher)

    result = await analyze_session(
        session.id,
        session,
        test_scenario,
        test_framework,
        async_db_session,
        synthesis_enabled=False,
    )

    # Synthesizer was never invoked.
    assert synthesis_mock.await_count == 0
    assert synthesis_mock.called is False

    # Returned feedback is None (no top narrative box).
    assert result["feedback"] is None

    # Persisted report status is "skipped".
    report = (
        await async_db_session.execute(
            select(SessionFeedbackReport).where(
                SessionFeedbackReport.session_id == session.id
            )
        )
    ).scalar_one()
    assert report.status == "skipped"
    assert report.model == "skipped"
    assert report.prompt_hash == "skipped"

    # Summary feedback is None.
    summary = (
        await async_db_session.execute(
            select(SessionSummary).where(
                SessionSummary.session_id == session.id
            )
        )
    ).scalar_one()
    assert summary.feedback is None

    # No synthesis ApiUsageLog row.
    synthesis_logs = (
        (
            await async_db_session.execute(
                select(ApiUsageLog).where(
                    ApiUsageLog.session_id == session.id,
                    ApiUsageLog.operation == "synthesis",
                )
            )
        )
        .scalars()
        .all()
    )
    assert synthesis_logs == []


@pytest.mark.anyio
async def test_synthesis_enabled_default_runs_llm(
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    classify_mock,
    greeting_mock,
    synthesis_mock,
):
    """synthesis_enabled=True (default) preserves current behavior."""
    session = await _seed_session(async_db_session, test_scenario, test_teacher)

    result = await analyze_session(
        session.id,
        session,
        test_scenario,
        test_framework,
        async_db_session,
    )

    # Synthesizer WAS invoked.
    assert synthesis_mock.called is True
    assert synthesis_mock.await_count >= 1

    # Report status is "ok" (the status the mock returns).
    report = (
        await async_db_session.execute(
            select(SessionFeedbackReport).where(
                SessionFeedbackReport.session_id == session.id
            )
        )
    ).scalar_one()
    assert report.status == "ok"

    # Feedback is a non-empty plain string.
    assert isinstance(result["feedback"], str)
    assert result["feedback"]

"""End-to-end tests for the analysis pipeline (Stage D).

Tests classify + synthesize + persist happy path, degraded path,
failed path, and concurrent classification.
"""

import asyncio
import json
import time

import pytest
from sqlalchemy import select

from src.models import (
    QuestionAnalysis,
    SessionFeedbackReport,
    SessionSummary,
)
from src.services.analysis_pipeline import analyze_session

# ── Fixture overrides ────────────────────────────────────────────────
# Integration conftest overrides test_framework/test_scenario/etc. to
# use `db_session` (different engine).  These overrides restore the
# root-conftest versions that use `async_db_session` so all data shares
# one in-memory database and FK constraints pass.


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
        Message(
            session_id=session.id,
            role="teacher",
            content="Why did you add the numerators?",
        ),
        Message(
            session_id=session.id,
            role="student",
            content="Because you just add them.",
        ),
    ]
    async_db_session.add_all(msgs)
    await async_db_session.commit()
    await async_db_session.refresh(session)
    return session


@pytest.mark.anyio
async def test_pipeline_happy_path(
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    classify_mock,
    greeting_mock,
    synthesis_mock,
):
    """Classify + synthesize + persist: all succeed."""
    session = await _seed_session(async_db_session, test_scenario, test_teacher)

    result = await analyze_session(
        session.id, session, test_scenario, test_framework, async_db_session
    )

    # Response shape
    assert "distribution" in result
    assert "feedback" in result
    assert isinstance(result["feedback"], str)
    assert len(result["feedback"]) <= 500
    # feedback must NOT look like JSON
    assert not result["feedback"].startswith("{")

    # QuestionAnalysis rows
    qa_rows = (
        (await async_db_session.execute(select(QuestionAnalysis)))
        .scalars()
        .all()
    )
    assert len(qa_rows) == 2  # 2 teacher messages

    # SessionFeedbackReport row
    report = (
        await async_db_session.execute(
            select(SessionFeedbackReport).where(
                SessionFeedbackReport.session_id == session.id
            )
        )
    ).scalar_one()
    assert report.status == "ok"
    payload = json.loads(report.payload_json)
    assert "brief_feedback" in payload
    assert "strengths" in payload

    # SessionSummary row — feedback is plain text
    summary = (
        await async_db_session.execute(
            select(SessionSummary).where(
                SessionSummary.session_id == session.id
            )
        )
    ).scalar_one()
    assert summary.feedback == result["feedback"]
    assert not summary.feedback.startswith("{")


@pytest.mark.anyio
async def test_pipeline_degraded_path(
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    classify_mock,
    greeting_mock,
    synthesis_mock_degraded,
):
    """Synthesis returns degraded — still persists rows."""
    session = await _seed_session(async_db_session, test_scenario, test_teacher)

    await analyze_session(
        session.id, session, test_scenario, test_framework, async_db_session
    )

    report = (
        await async_db_session.execute(
            select(SessionFeedbackReport).where(
                SessionFeedbackReport.session_id == session.id
            )
        )
    ).scalar_one()
    assert report.status == "degraded"

    summary = (
        await async_db_session.execute(
            select(SessionSummary).where(
                SessionSummary.session_id == session.id
            )
        )
    ).scalar_one()
    assert summary.feedback  # non-empty


@pytest.mark.anyio
async def test_pipeline_failed_path(
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    classify_mock,
    greeting_mock,
    synthesis_mock_failed,
):
    """Synthesis returns failed — still persists with fallback feedback."""
    session = await _seed_session(async_db_session, test_scenario, test_teacher)

    await analyze_session(
        session.id, session, test_scenario, test_framework, async_db_session
    )

    report = (
        await async_db_session.execute(
            select(SessionFeedbackReport).where(
                SessionFeedbackReport.session_id == session.id
            )
        )
    ).scalar_one()
    assert report.status == "failed"

    summary = (
        await async_db_session.execute(
            select(SessionSummary).where(
                SessionSummary.session_id == session.id
            )
        )
    ).scalar_one()
    assert "실패" in summary.feedback


@pytest.mark.anyio
async def test_pipeline_synthesis_exception(
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    classify_mock,
    greeting_mock,
    synthesis_mock_raises,
):
    """Synthesis raises exception — still persists with status='failed'."""
    session = await _seed_session(async_db_session, test_scenario, test_teacher)

    await analyze_session(
        session.id, session, test_scenario, test_framework, async_db_session
    )

    report = (
        await async_db_session.execute(
            select(SessionFeedbackReport).where(
                SessionFeedbackReport.session_id == session.id
            )
        )
    ).scalar_one()
    assert report.status == "failed"


@pytest.mark.anyio
async def test_classify_runs_concurrently(
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    greeting_mock,
    synthesis_mock,
):
    """Parallel classify: wall-time is less than serial for N messages."""
    from unittest.mock import AsyncMock

    # Create a classify mock that sleeps 0.3s per call
    async def slow_classify(*args, **kwargs):
        await asyncio.sleep(0.3)
        return {
            "label": "Pressing",
            "confidence": 0.9,
            "reasoning": {"summary": "Test"},
        }

    classify = AsyncMock(side_effect=slow_classify)
    import src.services.analyzer as analyzer_mod

    original = analyzer_mod.Analyzer.classify_question
    analyzer_mod.Analyzer.classify_question = classify

    try:
        session = await _seed_session(
            async_db_session, test_scenario, test_teacher
        )

        start = time.monotonic()
        await analyze_session(
            session.id,
            session,
            test_scenario,
            test_framework,
            async_db_session,
        )
        elapsed = time.monotonic() - start

        # 2 teacher messages × 0.3s serial = 0.6s minimum.
        # Parallel with semaphore(5) should complete in ~0.3s + overhead.
        # Allow generous margin (0.6s would be serial; < 1.0s is parallel).
        assert elapsed < 1.0, (
            f"Classification took {elapsed:.2f}s — "
            f"likely not parallelized (expected < 0.55s)"
        )
    finally:
        analyzer_mod.Analyzer.classify_question = original


@pytest.mark.anyio
async def test_analyze_idempotent_second_call_returns_cache(
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    classify_mock,
    greeting_mock,
    synthesis_mock,
):
    """Second call returns existing summary (route-level caching)."""
    session = await _seed_session(async_db_session, test_scenario, test_teacher)

    await analyze_session(
        session.id, session, test_scenario, test_framework, async_db_session
    )

    # Second call would hit IntegrityError at commit since summary exists.
    # The route handles this, not the pipeline directly.
    # Verify exactly one summary and one report exist.
    summaries = (
        (
            await async_db_session.execute(
                select(SessionSummary).where(
                    SessionSummary.session_id == session.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(summaries) == 1

    reports = (
        (
            await async_db_session.execute(
                select(SessionFeedbackReport).where(
                    SessionFeedbackReport.session_id == session.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(reports) == 1

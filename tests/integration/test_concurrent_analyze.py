"""Sequential /analyze idempotency tests (Stage D).

Tests that two sequential /analyze calls produce exactly one
SessionFeedbackReport and one SessionSummary — the second call
returns cached data from the first.
"""

import pytest
from sqlalchemy import select

from src.models import (
    SessionFeedbackReport,
    SessionSummary,
)

# ── Fixture overrides (same as test_analysis_pipeline_e2e) ───────────


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


async def _seed_ended_session(async_db_session, test_scenario, test_teacher):
    """Create an ended session with messages for testing."""
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
            content="What is photosynthesis?",
        ),
        Message(
            session_id=session.id,
            role="student",
            content="Plants make food from sunlight.",
        ),
    ]
    async_db_session.add_all(msgs)
    await async_db_session.commit()
    await async_db_session.refresh(session)
    return session


@pytest.mark.anyio
async def test_second_analyze_returns_cached(
    authenticated_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
    classify_mock,
    greeting_mock,
    synthesis_mock,
):
    """Two sequential POST /analyze: both 200, exactly 1 report + summary.

    The second call returns the cached summary from the first.
    True concurrency is not tested here because the test client
    shares a single async_db_session between requests — concurrent
    commits on the same SQLAlchemy session corrupt transaction state.
    """
    session = await _seed_ended_session(
        async_db_session, test_scenario, test_teacher
    )

    url = f"/sessions/{session.id}/analyze"

    # First call — runs the full pipeline
    r1 = await authenticated_async_client.post(url)
    assert r1.status_code == 200, f"First call: {r1.status_code} {r1.text}"

    # Second call — returns cached summary
    r2 = await authenticated_async_client.post(url)
    assert r2.status_code == 200, f"Second call: {r2.status_code} {r2.text}"

    # Both return the same feedback
    assert r1.json()["feedback"] == r2.json()["feedback"]

    # Exactly one SessionFeedbackReport
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
    assert len(reports) == 1, f"Expected 1 report, got {len(reports)}"

    # Exactly one SessionSummary
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
    assert len(summaries) == 1, f"Expected 1 summary, got {len(summaries)}"

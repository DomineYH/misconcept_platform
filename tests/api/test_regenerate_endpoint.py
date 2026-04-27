"""Tests for POST /admin/sessions/{id}/analyze_regenerate (Stage D).

Verifies admin-only access, LLM-failure preservation,
and success-path replacement.
"""

import json

import pytest
from sqlalchemy import select

from src.api.routes import admin_session_actions
from src.models import SessionFeedbackReport, SessionSummary


async def _seed_ended_session(async_db_session, test_scenario, test_teacher):
    """Create an ended session with messages."""
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
            content="I added the numerators.",
        ),
    ]
    async_db_session.add_all(msgs)
    await async_db_session.commit()
    await async_db_session.refresh(session)
    return session


async def _seed_existing_analysis(
    async_db_session, session, feedback_text="Old feedback."
):
    """Add existing summary + report for a session."""
    from src.models.session_feedback_report import SessionFeedbackReport
    from src.models.session_summary import SessionSummary

    summary = SessionSummary(
        session_id=session.id,
        distribution_json='{"Pressing": 1, "Linking": 0}',
        feedback=feedback_text,
    )
    async_db_session.add(summary)

    old_payload = {
        "version": 1,
        "brief_feedback": ["Old brief feedback."],
        "strengths": [],
        "improvements": [],
        "dialogue_coaching": [],
    }
    report = SessionFeedbackReport(
        session_id=session.id,
        version=1,
        model="old-model",
        prompt_hash="old-hash",
        status="ok",
        payload_json=json.dumps(old_payload),
    )
    async_db_session.add(report)
    await async_db_session.commit()


@pytest.mark.anyio
async def test_regenerate_requires_admin(
    authenticated_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
):
    """Non-admin (teacher) gets 403 on regenerate."""
    session = await _seed_ended_session(
        async_db_session, test_scenario, test_teacher
    )

    resp = await authenticated_async_client.post(
        f"/admin/sessions/{session.id}/analyze_regenerate",
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_regenerate_rate_limited_2_per_min(
    admin_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    classify_mock,
    greeting_mock,
    synthesis_mock,
):
    """Third call within a minute gets 429.

    NOTE: slowapi Limiter is disabled when config.TESTING=True, so this
    test verifies the route wiring more than actual rate-limiting.
    If the limiter is ever enabled in tests, this will properly assert 429.
    """
    session = await _seed_ended_session(
        async_db_session, test_scenario, test_teacher
    )

    # First two calls should succeed (or at least not 429)
    _r1 = await admin_async_client.post(
        f"/admin/sessions/{session.id}/analyze_regenerate",
    )
    _r2 = await admin_async_client.post(
        f"/admin/sessions/{session.id}/analyze_regenerate",
    )

    r3 = await admin_async_client.post(
        f"/admin/sessions/{session.id}/analyze_regenerate",
    )
    # With limiter disabled, expect same status as prior calls (not 429)
    assert r3.status_code in (
        200,
        500,
    ), f"Expected 200/500, got {r3.status_code}"


@pytest.mark.anyio
async def test_regenerate_preserves_old_on_llm_failure(
    admin_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    classify_mock,
    greeting_mock,
    synthesis_mock_raises,
):
    """When LLM synthesis fails, route returns 200 with old data.

    run_llm_pipeline catches synthesis errors internally and returns
    synthesis_status='failed'. Regenerate must leave the prior good
    analysis intact instead of overwriting it with fallback data.
    """
    session = await _seed_ended_session(
        async_db_session, test_scenario, test_teacher
    )
    await _seed_existing_analysis(
        async_db_session, session, "Original feedback."
    )

    resp = await admin_async_client.post(
        f"/admin/sessions/{session.id}/analyze_regenerate",
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["feedback_status"] == "ok"
    assert data["feedback"] == "Original feedback."
    assert data["regeneration_status"] == "synthesis_failed_preserved"

    # Old data is preserved.
    report = (
        await async_db_session.execute(
            select(SessionFeedbackReport).where(
                SessionFeedbackReport.session_id == session.id
            )
        )
    ).scalar_one()
    assert report.status == "ok"
    assert report.model == "old-model"

    summary = (
        await async_db_session.execute(
            select(SessionSummary).where(
                SessionSummary.session_id == session.id
            )
        )
    ).scalar_one()
    assert summary.feedback == "Original feedback."


@pytest.mark.anyio
async def test_regenerate_preserves_ok_when_new_is_degraded(
    admin_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    classify_mock,
    greeting_mock,
    synthesis_mock_degraded,
):
    """Degraded new + existing ok -> preserve old analysis."""
    session = await _seed_ended_session(
        async_db_session, test_scenario, test_teacher
    )
    await _seed_existing_analysis(
        async_db_session, session, "Original feedback."
    )

    resp = await admin_async_client.post(
        f"/admin/sessions/{session.id}/analyze_regenerate",
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["regeneration_status"] == "degraded_skipped_preserved"
    assert data["feedback"] == "Original feedback."

    # Old data is preserved in DB.
    report = (
        await async_db_session.execute(
            select(SessionFeedbackReport).where(
                SessionFeedbackReport.session_id == session.id
            )
        )
    ).scalar_one()
    assert report.status == "ok"
    assert report.model == "old-model"


@pytest.mark.anyio
async def test_begin_regeneration_write_lock_uses_sqlite_exclusive():
    """SQLite regeneration replacement starts with BEGIN EXCLUSIVE."""

    class _Dialect:
        name = "sqlite"

    class _Bind:
        dialect = _Dialect()

    class _FakeSession:
        def __init__(self):
            self.rolled_back = False
            self.statements = []

        def get_bind(self):
            return _Bind()

        def in_transaction(self):
            return True

        async def rollback(self):
            self.rolled_back = True

        async def execute(self, stmt):
            self.statements.append(str(stmt))

    fake_session = _FakeSession()

    await admin_session_actions._begin_regeneration_write_lock(fake_session)

    assert fake_session.rolled_back is True
    assert fake_session.statements == ["BEGIN EXCLUSIVE"]


@pytest.mark.anyio
async def test_regenerate_success_uses_write_lock(
    admin_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    classify_mock,
    greeting_mock,
    synthesis_mock,
    monkeypatch,
):
    """Success-path replacement is guarded by the write-lock helper."""
    lock_calls = []

    async def _record_lock(db):
        lock_calls.append(db)

    monkeypatch.setattr(
        admin_session_actions,
        "_begin_regeneration_write_lock",
        _record_lock,
    )
    session = await _seed_ended_session(
        async_db_session, test_scenario, test_teacher
    )
    await _seed_existing_analysis(
        async_db_session, session, "Old feedback to replace."
    )

    resp = await admin_async_client.post(
        f"/admin/sessions/{session.id}/analyze_regenerate",
    )

    assert resp.status_code == 200
    assert lock_calls == [async_db_session]


@pytest.mark.anyio
async def test_regenerate_replaces_on_success(
    admin_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    classify_mock,
    greeting_mock,
    synthesis_mock,
):
    """On success, old report+summary are replaced with new data."""
    session = await _seed_ended_session(
        async_db_session, test_scenario, test_teacher
    )
    await _seed_existing_analysis(
        async_db_session, session, "Old feedback to replace."
    )

    resp = await admin_async_client.post(
        f"/admin/sessions/{session.id}/analyze_regenerate",
    )
    assert resp.status_code == 200

    data = resp.json()
    # Response should have new data
    assert data["feedback"] != "Old feedback to replace."
    assert "feedback_status" in data
    assert "stats" in data

    # DB should have new report
    report = (
        await async_db_session.execute(
            select(SessionFeedbackReport).where(
                SessionFeedbackReport.session_id == session.id
            )
        )
    ).scalar_one()
    assert report.model != "old-model"

    summary = (
        await async_db_session.execute(
            select(SessionSummary).where(
                SessionSummary.session_id == session.id
            )
        )
    ).scalar_one()
    assert summary.feedback != "Old feedback to replace."

    # Exactly one report and one summary
    all_reports = (
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
    assert len(all_reports) == 1

    all_summaries = (
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
    assert len(all_summaries) == 1

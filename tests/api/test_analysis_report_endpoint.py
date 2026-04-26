"""Tests for GET /sessions/{id}/analysis response shape (Stage D).

Verifies feedback_sections, feedback_status, stats, and legacy
session handling.
"""

import json

import pytest


async def _seed_session_with_report(
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    payload=None,
    report_status="ok",
):
    """Create an ended session with summary + feedback report."""
    from datetime import datetime, timedelta, timezone

    from src.models.message import Message
    from src.models.session import Session
    from src.models.session_feedback_report import SessionFeedbackReport
    from src.models.session_summary import SessionSummary

    session = Session(
        scenario_id=test_scenario.id,
        teacher_id=test_teacher.id,
        started_at=datetime.now(timezone.utc)
        - timedelta(minutes=5, seconds=12),
        ended_at=datetime.now(timezone.utc),
        tutor_intervention_count=2,
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
        Message(
            session_id=session.id,
            role="tutor",
            content="Try asking about the denominator.",
        ),
        Message(
            session_id=session.id,
            role="tutor",
            content="Good follow-up question.",
        ),
    ]
    async_db_session.add_all(msgs)
    await async_db_session.flush()

    summary = SessionSummary(
        session_id=session.id,
        distribution_json=(
            '{"Pressing": 1, "Linking": 0, "Directing": 0, "Recall": 0}'
        ),
        feedback="학생 풀이 과정을 물어본 것은 좋은 출발이었어요!",
    )
    async_db_session.add(summary)

    if payload is None:
        payload = {
            "version": 1,
            "brief_feedback": [
                "학생 풀이 과정을 물어본 것은 좋은 출발이었어요!",
                "핵심 단서를 더 깊이 탐색했다면 좋았을 거예요.",
            ],
            "strengths": [
                {
                    "message_id": msgs[0].id,
                    "quote": "How did you solve it?",
                    "reason": "Good exploratory question.",
                }
            ],
            "improvements": [],
            "dialogue_coaching": [],
        }

    report = SessionFeedbackReport(
        session_id=session.id,
        version=1,
        model="test-model",
        prompt_hash="abc123",
        status=report_status,
        payload_json=json.dumps(payload, ensure_ascii=False),
    )
    async_db_session.add(report)

    await async_db_session.commit()
    await async_db_session.refresh(session)
    return session


@pytest.mark.anyio
async def test_get_analysis_includes_feedback_sections(
    authenticated_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
):
    """GET response includes feedback_sections dict."""
    session = await _seed_session_with_report(
        async_db_session, test_scenario, test_teacher, test_framework
    )

    resp = await authenticated_async_client.get(
        f"/sessions/{session.id}/analysis"
    )
    assert resp.status_code == 200

    data = resp.json()
    assert "feedback_sections" in data
    assert data["feedback_sections"] is not None
    assert "brief_feedback" in data["feedback_sections"]
    assert "strengths" in data["feedback_sections"]


@pytest.mark.anyio
async def test_get_analysis_includes_stats(
    authenticated_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
):
    """GET response includes stats block with all 4 fields."""
    session = await _seed_session_with_report(
        async_db_session, test_scenario, test_teacher, test_framework
    )

    resp = await authenticated_async_client.get(
        f"/sessions/{session.id}/analysis"
    )
    assert resp.status_code == 200

    data = resp.json()
    assert "stats" in data
    stats = data["stats"]
    assert "duration_seconds" in stats
    assert "teacher_question_count" in stats
    assert "student_response_count" in stats
    assert "tutor_intervention_count" in stats
    assert stats["teacher_question_count"] == 1
    assert stats["student_response_count"] == 1
    assert stats["tutor_intervention_count"] == 2


@pytest.mark.anyio
async def test_get_analysis_feedback_status_ok(
    authenticated_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
):
    """GET response feedback_status is 'ok' when report status='ok'."""
    session = await _seed_session_with_report(
        async_db_session,
        test_scenario,
        test_teacher,
        test_framework,
        report_status="ok",
    )

    resp = await authenticated_async_client.get(
        f"/sessions/{session.id}/analysis"
    )
    assert resp.status_code == 200
    assert resp.json()["feedback_status"] == "ok"


@pytest.mark.anyio
async def test_get_analysis_feedback_status_degraded(
    authenticated_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
):
    """GET response feedback_status is 'degraded' when report says so."""
    session = await _seed_session_with_report(
        async_db_session,
        test_scenario,
        test_teacher,
        test_framework,
        report_status="degraded",
    )

    resp = await authenticated_async_client.get(
        f"/sessions/{session.id}/analysis"
    )
    assert resp.status_code == 200
    assert resp.json()["feedback_status"] == "degraded"


@pytest.mark.anyio
async def test_legacy_session_returns_null_feedback_sections(
    authenticated_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
):
    """Legacy session (no feedback report) returns feedback_sections=null."""
    from datetime import datetime, timedelta, timezone

    from src.models.message import Message
    from src.models.session import Session
    from src.models.session_summary import SessionSummary

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
            content="Legacy question?",
        ),
    ]
    async_db_session.add_all(msgs)

    summary = SessionSummary(
        session_id=session.id,
        distribution_json='{"Pressing": 1}',
        feedback="Good questioning technique.",
    )
    async_db_session.add(summary)
    # No SessionFeedbackReport — this is a legacy session
    await async_db_session.commit()
    await async_db_session.refresh(session)

    resp = await authenticated_async_client.get(
        f"/sessions/{session.id}/analysis"
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["feedback_sections"] is None
    assert data["feedback_status"] == "legacy"


@pytest.mark.anyio
async def test_no_summary_returns_404_unchanged(
    authenticated_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
):
    """No summary → 404 unchanged."""
    from datetime import datetime, timedelta, timezone

    from src.models.session import Session

    session = Session(
        scenario_id=test_scenario.id,
        teacher_id=test_teacher.id,
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ended_at=datetime.now(timezone.utc),
    )
    async_db_session.add(session)
    await async_db_session.commit()
    await async_db_session.refresh(session)

    resp = await authenticated_async_client.get(
        f"/sessions/{session.id}/analysis"
    )
    assert resp.status_code == 404

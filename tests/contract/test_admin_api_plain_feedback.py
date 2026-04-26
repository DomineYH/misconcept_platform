"""Contract test: analysis endpoint returns plain-text feedback.

Ensures the feedback field in the API response is a string ≤500
chars, not a dict or JSON blob.
"""

import json

import pytest


async def _seed_with_report(
    async_db_session, test_scenario, test_teacher, test_framework
):
    """Seed an ended session with summary + feedback report."""
    from datetime import datetime, timedelta, timezone

    from src.models.message import Message
    from src.models.session import Session
    from src.models.session_feedback_report import (
        SessionFeedbackReport,
    )
    from src.models.session_summary import SessionSummary

    session = Session(
        scenario_id=test_scenario.id,
        teacher_id=test_teacher.id,
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ended_at=datetime.now(timezone.utc),
        tutor_intervention_count=1,
    )
    async_db_session.add(session)
    await async_db_session.flush()

    msgs = [
        Message(
            session_id=session.id,
            role="teacher",
            content="Why did you add the numerators?",
        ),
        Message(
            session_id=session.id,
            role="student",
            content="Because you just add them?",
        ),
    ]
    async_db_session.add_all(msgs)
    await async_db_session.flush()

    payload = {
        "version": 1,
        "brief_feedback": [
            "학생의 오개념을 정면으로 다루지 못했어요.",
        ],
        "strengths": [],
        "improvements": [],
        "dialogue_coaching": [],
    }
    report = SessionFeedbackReport(
        session_id=session.id,
        model="test-model",
        prompt_hash="abc123",
        status="ok",
        payload_json=json.dumps(payload),
    )
    async_db_session.add(report)
    await async_db_session.flush()

    summary = SessionSummary(
        session_id=session.id,
        feedback="학생의 오개념을 정면으로 다루지 못했어요.",
        distribution='{"Pressing":1,"Linking":0,' '"Directing":0,"Recall":0}',
    )
    async_db_session.add(summary)
    await async_db_session.flush()

    return session


@pytest.mark.anyio
async def test_analysis_feedback_is_plain_string(
    async_db_session,
    test_scenario,
    test_teacher,
    test_framework,
    authenticated_async_client,
):
    """GET /sessions/{id}/analysis feedback must be plain text."""
    session = await _seed_with_report(
        async_db_session,
        test_scenario,
        test_teacher,
        test_framework,
    )
    resp = await authenticated_async_client.get(
        f"/sessions/{session.id}/analysis"
    )
    assert resp.status_code == 200
    data = resp.json()
    fb = data.get("feedback")
    assert isinstance(
        fb, str
    ), f"feedback should be str, got {type(fb).__name__}"
    assert len(fb) <= 500, f"feedback too long: {len(fb)} chars"
    assert not fb.startswith("{"), f"feedback looks like JSON dict: {fb[:60]}"
    assert not fb.startswith("["), f"feedback looks like JSON list: {fb[:60]}"

"""Admin analysis modal context parity tests."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.models import Message, Session, SessionFeedbackReport, SessionSummary


@pytest.mark.anyio
async def test_admin_analysis_modal_renders_new_context(
    admin_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
):
    """Admin modal gets feedback status, sections, and stats context."""
    session = Session(
        scenario_id=test_scenario.id,
        teacher_id=test_teacher.id,
        started_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        ended_at=datetime.now(timezone.utc),
        tutor_intervention_count=7,
    )
    async_db_session.add(session)
    await async_db_session.flush()

    async_db_session.add_all(
        [
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
    )
    async_db_session.add(
        SessionSummary(
            session_id=session.id,
            distribution_json='{"Pressing": 1, "Linking": 0}',
            feedback="Legacy one-line fallback should not be primary.",
        )
    )
    async_db_session.add(
        SessionFeedbackReport(
            session_id=session.id,
            version=1,
            model="test-model",
            prompt_hash="test-hash",
            status="degraded",
            payload_json=json.dumps(
                {
                    "version": 1,
                    "brief_feedback": ["Admin brief feedback."],
                    "strengths": [],
                    "improvements": [],
                    "dialogue_coaching": [],
                },
                ensure_ascii=False,
            ),
        )
    )
    await async_db_session.commit()

    resp = await admin_async_client.get(
        f"/admin/sessions/{session.id}/analysis_modal"
    )

    assert resp.status_code == 200
    html = resp.text
    assert "Admin brief feedback." in html
    assert "일부 피드백 항목이 생성되지 않았어요" in html
    assert "analysis-stat-grid" in html
    assert "선생님 질문" in html
    assert "학생 응답" in html
    assert "멘토 개입 7회" in html

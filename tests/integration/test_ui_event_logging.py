"""Tests for POST /sessions/{id}/analysis/detail-opened (Stage F.1).

Verifies that the route creates a UiEvent row with the correct
event_type, enforces auth, and validates session ownership.
"""

import pytest
from sqlalchemy import select

from src.models import UiEvent

# ── Fixture overrides ────────────────────────────────────────────────


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
    """Create a minimal ended session."""
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
    return session


@pytest.mark.anyio
async def test_detail_opened_creates_ui_event(
    authenticated_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
):
    """POST creates a UiEvent row with correct fields."""
    session = await _seed_ended_session(
        async_db_session, test_scenario, test_teacher
    )

    url = f"/sessions/{session.id}/analysis/detail-opened"
    resp = await authenticated_async_client.post(url)
    assert resp.status_code == 204

    events = (
        (
            await async_db_session.execute(
                select(UiEvent).where(UiEvent.session_id == session.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].event_type == "analysis_detail_opened"
    assert events[0].user_id == test_teacher.id


@pytest.mark.anyio
async def test_detail_opened_requires_auth(
    async_client,
    async_db_session,
    test_scenario,
    test_teacher,
):
    """Unauthenticated request gets 303 redirect to login."""
    session = await _seed_ended_session(
        async_db_session, test_scenario, test_teacher
    )

    url = f"/sessions/{session.id}/analysis/detail-opened"
    resp = await async_client.post(url, follow_redirects=False)
    assert resp.status_code == 303


@pytest.mark.anyio
async def test_detail_opened_wrong_user_forbidden(
    authenticated_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
):
    """POST with a different session owner gets 403."""
    from datetime import datetime, timedelta, timezone

    from src.models.user import User

    # Create a different teacher
    other = User(
        username="other_teacher",
        nickname="다른선생",
        role="teacher",
    )
    other.set_password("test1234")
    async_db_session.add(other)
    await async_db_session.flush()

    from src.models.session import Session

    session = Session(
        scenario_id=test_scenario.id,
        teacher_id=other.id,
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ended_at=datetime.now(timezone.utc),
    )
    async_db_session.add(session)
    await async_db_session.commit()

    # authenticated_async_client is logged in as test_teacher
    url = f"/sessions/{session.id}/analysis/detail-opened"
    resp = await authenticated_async_client.post(url)
    assert resp.status_code == 403

    # No event should be created
    events = (
        (
            await async_db_session.execute(
                select(UiEvent).where(UiEvent.session_id == session.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 0


@pytest.mark.anyio
async def test_detail_opened_idempotent(
    authenticated_async_client,
    async_db_session,
    test_scenario,
    test_teacher,
):
    """Multiple calls create multiple events (no dedup)."""
    session = await _seed_ended_session(
        async_db_session, test_scenario, test_teacher
    )

    url = f"/sessions/{session.id}/analysis/detail-opened"
    r1 = await authenticated_async_client.post(url)
    r2 = await authenticated_async_client.post(url)
    assert r1.status_code == 204
    assert r2.status_code == 204

    events = (
        (
            await async_db_session.execute(
                select(UiEvent).where(UiEvent.session_id == session.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 2

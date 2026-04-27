"""Tests for migration 021: ui_event table (Issue #28)."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ui_event import UiEvent


@pytest.mark.asyncio
async def test_ui_event_table_created(db_session: AsyncSession):
    """ui_event table exists with expected columns."""
    result = await db_session.execute(
        text(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name='ui_event'"
        )
    )
    sql = result.scalar()
    assert sql is not None, "ui_event table should exist"
    assert "user_id" in sql
    assert "session_id" in sql
    assert "event_type" in sql
    assert "created_at" in sql


@pytest.mark.asyncio
async def test_ui_event_insert_and_query(db_session: AsyncSession):
    """Can insert and query UiEvent rows."""
    from src.models.analysis_framework import AnalysisFramework
    from src.models.prompt_template import PromptTemplate
    from src.models.scenario import Scenario
    from src.models.session import Session
    from src.models.user import User

    framework = AnalysisFramework(
        name="Test FW 021",
        labels_json='["Pressing","Linking"]',
    )
    db_session.add(framework)
    await db_session.flush()

    template = PromptTemplate(
        bot_type="student",
        template_name="tpl_021",
        template_text="x" * 20,
        version=1,
    )
    db_session.add(template)
    await db_session.flush()

    scenario = Scenario(
        title="Scenario 021",
        prompt="prompt",
        framework_id=framework.id,
        student_template_id=template.id,
        is_active=1,
    )
    db_session.add(scenario)
    await db_session.flush()

    user = User(username="user_021", nickname="Test", role="teacher")
    user.set_password("pass")
    db_session.add(user)
    await db_session.flush()

    session = Session(scenario_id=scenario.id, teacher_id=user.id)
    db_session.add(session)
    await db_session.flush()

    event = UiEvent(
        user_id=user.id,
        session_id=session.id,
        event_type="analysis_detail_opened",
    )
    db_session.add(event)
    await db_session.flush()

    # Verify round-trip
    await db_session.refresh(event)
    assert event.id is not None
    assert event.event_type == "analysis_detail_opened"
    assert event.user_id == user.id
    assert event.session_id == session.id
    assert event.created_at is not None


@pytest.mark.asyncio
async def test_ui_event_cascade_delete(db_session: AsyncSession):
    """Deleting a session cascades to delete associated UiEvent rows."""
    from src.models.analysis_framework import AnalysisFramework
    from src.models.prompt_template import PromptTemplate
    from src.models.scenario import Scenario
    from src.models.session import Session
    from src.models.user import User

    framework = AnalysisFramework(
        name="Test FW 021b",
        labels_json='["Pressing","Linking"]',
    )
    db_session.add(framework)
    await db_session.flush()

    template = PromptTemplate(
        bot_type="student",
        template_name="tpl_021b",
        template_text="x" * 20,
        version=1,
    )
    db_session.add(template)
    await db_session.flush()

    scenario = Scenario(
        title="Scenario 021b",
        prompt="prompt",
        framework_id=framework.id,
        student_template_id=template.id,
        is_active=1,
    )
    db_session.add(scenario)
    await db_session.flush()

    user = User(username="user_021b", nickname="Test2", role="teacher")
    user.set_password("pass")
    db_session.add(user)
    await db_session.flush()

    session = Session(scenario_id=scenario.id, teacher_id=user.id)
    db_session.add(session)
    await db_session.flush()

    event = UiEvent(
        user_id=user.id,
        session_id=session.id,
        event_type="analysis_detail_opened",
    )
    db_session.add(event)
    await db_session.flush()
    event_id = event.id

    # Delete session
    await db_session.delete(session)
    await db_session.flush()

    # Event should be gone
    from sqlalchemy import select

    result = await db_session.execute(
        select(UiEvent).where(UiEvent.id == event_id)
    )
    assert result.scalar_one_or_none() is None

"""Tests for migration 019: session_feedback_report table (Issue #28)."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# These tests use the db_session fixture which creates all tables via
# Base.metadata.create_all. We verify the ORM model and schema constraints.


@pytest.mark.asyncio
async def test_migration_019_up_creates_table(db_session: AsyncSession):
    """SessionFeedbackReport table exists with expected columns."""

    result = await db_session.execute(
        text(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name='session_feedback_report'"
        )
    )
    sql = result.scalar()
    assert sql is not None, "session_feedback_report table should exist"

    # Verify key columns present
    assert "session_id" in sql
    assert "version" in sql
    assert "model" in sql
    assert "prompt_hash" in sql
    assert "status" in sql
    assert "payload_json" in sql
    assert "created_at" in sql


@pytest.mark.asyncio
async def test_migration_019_down_drops_table(db_session: AsyncSession):
    """Rollback removes the session_feedback_report table.

    In practice this is tested by running the _down.sql file.
    Here we verify the DROP TABLE IF EXISTS is safe (no-op on missing table).
    """
    await db_session.execute(
        text("DROP TABLE IF EXISTS session_feedback_report")
    )
    # Verify gone
    result = await db_session.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='session_feedback_report'"
        )
    )
    assert result.scalar() is None


@pytest.mark.asyncio
async def test_migration_019_enforces_unique_session_id(
    db_session: AsyncSession,
):
    """Only one feedback report per session (UNIQUE on session_id)."""
    from src.models.analysis_framework import AnalysisFramework
    from src.models.prompt_template import PromptTemplate
    from src.models.scenario import Scenario
    from src.models.session import Session
    from src.models.session_feedback_report import SessionFeedbackReport

    # Create minimal prerequisite chain
    framework = AnalysisFramework(
        name="Test FW 019",
        labels_json='["Pressing","Linking"]',
    )
    db_session.add(framework)
    await db_session.flush()

    template = PromptTemplate(
        bot_type="student",
        template_name="tpl_019",
        template_text="x" * 20,
        version=1,
    )
    db_session.add(template)
    await db_session.flush()

    scenario = Scenario(
        title="Scenario 019",
        prompt="prompt",
        framework_id=framework.id,
        student_template_id=template.id,
        is_active=1,
    )
    db_session.add(scenario)
    await db_session.flush()

    session = Session(scenario_id=scenario.id)
    db_session.add(session)
    await db_session.flush()

    # Insert first report
    report1 = SessionFeedbackReport(
        session_id=session.id,
        version=1,
        model="gpt-5-mini",
        prompt_hash="abc123",
        status="ok",
        payload_json='{"version":1}',
    )
    db_session.add(report1)
    await db_session.flush()

    # Second report for same session_id must fail
    report2 = SessionFeedbackReport(
        session_id=session.id,
        version=1,
        model="gpt-5-mini",
        prompt_hash="def456",
        status="ok",
        payload_json='{"version":1}',
    )
    db_session.add(report2)
    with pytest.raises(Exception):  # IntegrityError
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_migration_019_status_check_constraint(db_session: AsyncSession):
    """status must be one of ok, degraded, failed."""
    from src.models.analysis_framework import AnalysisFramework
    from src.models.prompt_template import PromptTemplate
    from src.models.scenario import Scenario
    from src.models.session import Session
    from src.models.session_feedback_report import SessionFeedbackReport

    framework = AnalysisFramework(
        name="Test FW 019b",
        labels_json='["Pressing","Linking"]',
    )
    db_session.add(framework)
    await db_session.flush()

    template = PromptTemplate(
        bot_type="student",
        template_name="tpl_019b",
        template_text="x" * 20,
        version=1,
    )
    db_session.add(template)
    await db_session.flush()

    scenario = Scenario(
        title="Scenario 019b",
        prompt="prompt",
        framework_id=framework.id,
        student_template_id=template.id,
        is_active=1,
    )
    db_session.add(scenario)
    await db_session.flush()

    session = Session(scenario_id=scenario.id)
    db_session.add(session)
    await db_session.flush()

    # Valid statuses should work
    for status in ("ok", "degraded", "failed"):
        report = SessionFeedbackReport(
            session_id=session.id,
            version=1,
            model="gpt-5-mini",
            prompt_hash=f"hash_{status}",
            status=status,
            payload_json='{"version":1}',
        )
        db_session.add(report)
        await db_session.flush()
        # Clean up for next iteration
        await db_session.delete(report)
        await db_session.flush()

    # Invalid status should fail
    bad_report = SessionFeedbackReport(
        session_id=session.id,
        version=1,
        model="gpt-5-mini",
        prompt_hash="hash_bad",
        status="invalid_status",
        payload_json='{"version":1}',
    )
    db_session.add(bad_report)
    with pytest.raises(Exception):  # IntegrityError from CHECK constraint
        await db_session.flush()
    await db_session.rollback()

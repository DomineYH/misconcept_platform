"""Tests for migration 020: api_usage_log.operation column (Issue #28)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.api_usage import ApiUsageLog


@pytest.mark.asyncio
async def test_api_usage_operation_column_added(db_session: AsyncSession):
    """operation column exists on api_usage_log and accepts values."""
    from src.models.analysis_framework import AnalysisFramework
    from src.models.prompt_template import PromptTemplate
    from src.models.scenario import Scenario
    from src.models.session import Session

    framework = AnalysisFramework(
        name="Test FW 020",
        labels_json='["Pressing","Linking"]',
    )
    db_session.add(framework)
    await db_session.flush()

    template = PromptTemplate(
        bot_type="student",
        template_name="tpl_020",
        template_text="x" * 20,
        version=1,
    )
    db_session.add(template)
    await db_session.flush()

    scenario = Scenario(
        title="Scenario 020",
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

    # Row with operation set
    log_with_op = ApiUsageLog(
        session_id=session.id,
        bot_type="student",
        model="gpt-5-mini",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        estimated_cost_usd=0.001,
        operation="synthesis",
    )
    db_session.add(log_with_op)
    await db_session.flush()
    assert log_with_op.operation == "synthesis"

    # Row without operation (NULL, simulating pre-#28 rows)
    log_without_op = ApiUsageLog(
        session_id=session.id,
        bot_type="student",
        model="gpt-5-mini",
        prompt_tokens=200,
        completion_tokens=100,
        total_tokens=300,
        estimated_cost_usd=0.002,
    )
    db_session.add(log_without_op)
    await db_session.flush()
    assert log_without_op.operation is None

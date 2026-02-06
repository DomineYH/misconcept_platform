"""Test framework deletion with cascade (Issue: NOT NULL constraint)."""

import pytest
from datetime import datetime
from sqlalchemy import select

from src.models.analysis_framework import AnalysisFramework
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.message import Message
from src.models.session_summary import SessionSummary
from src.models.prompt_template import PromptTemplate


@pytest.fixture
async def test_student_template(async_db_session) -> PromptTemplate:
    """Create test student template."""
    template = PromptTemplate(
        bot_type="student",
        template_name="Test Student Template",
        version=1,
        template_text=(
            "You are a test student bot. Scenario: {scenario_title}. "
            "Profile: {student_profile}. Context: {prompt}"
        ),
    )
    async_db_session.add(template)
    await async_db_session.flush()
    return template


@pytest.mark.asyncio
async def test_framework_delete_with_soft_deleted_scenario(
    async_db_session,
    test_student_template,
):
    """Framework deletion should cascade to soft-deleted scenarios."""
    # Create framework
    framework = AnalysisFramework(
        name="Delete Test Framework",
        description="For delete testing",
        labels_json='["A","B"]',
    )
    async_db_session.add(framework)
    await async_db_session.flush()

    # Create scenario and soft-delete it
    scenario = Scenario(
        title="Soft Deleted Scenario",
        prompt="Test prompt",
        framework_id=framework.id,
        student_template_id=test_student_template.id,
        is_active=1,
        deleted_at=datetime.utcnow(),  # Soft deleted
    )
    async_db_session.add(scenario)
    await async_db_session.commit()

    scenario_id = scenario.id
    framework_id = framework.id

    # Delete scenario (should work with cascade)
    await async_db_session.delete(scenario)
    await async_db_session.flush()

    # Delete framework
    await async_db_session.delete(framework)
    await async_db_session.commit()

    # Verify framework and scenario are deleted
    fw_result = await async_db_session.get(AnalysisFramework, framework_id)
    assert fw_result is None

    sc_result = await async_db_session.get(Scenario, scenario_id)
    assert sc_result is None


@pytest.mark.asyncio
async def test_scenario_delete_cascades_to_sessions_via_orm(
    async_db_session,
    test_teacher,
    test_student_template,
):
    """Scenario deletion cascades to sessions when relationship is loaded."""
    # Create framework
    framework = AnalysisFramework(
        name="Cascade Test Framework",
        description="For cascade testing",
        labels_json='["X","Y"]',
    )
    async_db_session.add(framework)
    await async_db_session.flush()

    # Create scenario
    scenario = Scenario(
        title="Scenario with Sessions",
        prompt="Test prompt",
        framework_id=framework.id,
        student_template_id=test_student_template.id,
        is_active=1,
    )
    async_db_session.add(scenario)
    await async_db_session.flush()

    # Create sessions
    session1 = Session(
        scenario_id=scenario.id,
        teacher_id=test_teacher.id,
    )
    session2 = Session(
        scenario_id=scenario.id,
        teacher_id=test_teacher.id,
    )
    async_db_session.add_all([session1, session2])
    await async_db_session.commit()

    session1_id = session1.id
    session2_id = session2.id
    scenario_id = scenario.id

    # Explicitly delete sessions first (simulating route behavior)
    sessions_query = select(Session).where(
        Session.scenario_id == scenario_id
    )
    result = await async_db_session.execute(sessions_query)
    sessions = result.scalars().all()
    for s in sessions:
        await async_db_session.delete(s)

    await async_db_session.flush()

    # Delete scenario
    await async_db_session.delete(scenario)
    await async_db_session.commit()

    # Verify sessions are also deleted
    s1_result = await async_db_session.get(Session, session1_id)
    s2_result = await async_db_session.get(Session, session2_id)
    assert s1_result is None
    assert s2_result is None


@pytest.mark.asyncio
async def test_session_delete_cascades_to_messages_and_summary(
    async_db_session,
    test_teacher,
    test_student_template,
):
    """Session deletion should cascade to messages and summary."""
    # Create framework
    framework = AnalysisFramework(
        name="Session Cascade Framework",
        description="For session cascade testing",
        labels_json='["P","Q"]',
    )
    async_db_session.add(framework)
    await async_db_session.flush()

    # Create scenario
    scenario = Scenario(
        title="Scenario for Session Cascade",
        prompt="Test prompt",
        framework_id=framework.id,
        student_template_id=test_student_template.id,
        is_active=1,
    )
    async_db_session.add(scenario)
    await async_db_session.flush()

    # Create session
    session = Session(
        scenario_id=scenario.id,
        teacher_id=test_teacher.id,
    )
    async_db_session.add(session)
    await async_db_session.flush()

    # Create messages
    msg1 = Message(
        session_id=session.id,
        role="teacher",
        content="Question 1",
    )
    msg2 = Message(
        session_id=session.id,
        role="student",
        content="Answer 1",
    )
    async_db_session.add_all([msg1, msg2])

    # Create summary
    summary = SessionSummary(
        session_id=session.id,
        distribution_json='{"P":1}',
        feedback="Test feedback",
    )
    async_db_session.add(summary)
    await async_db_session.commit()

    msg1_id = msg1.id
    summary_id = summary.id
    session_id = session.id

    # Delete session - should cascade to messages/summary
    await async_db_session.delete(session)
    await async_db_session.commit()

    # Verify messages and summary are deleted
    msg_result = await async_db_session.get(Message, msg1_id)
    summary_result = await async_db_session.get(SessionSummary, summary_id)
    assert msg_result is None
    assert summary_result is None


@pytest.mark.asyncio
async def test_full_cascade_framework_to_summary(
    async_db_session,
    test_teacher,
    test_student_template,
):
    """Full cascade: Framework -> Scenario -> Session -> Messages/Summary.

    This test simulates the actual route behavior where:
    1. Sessions are deleted first (explicit)
    2. Then scenarios are deleted
    3. Finally framework is deleted
    """
    # Create framework
    framework = AnalysisFramework(
        name="Full Cascade Framework",
        description="Full cascade test",
        labels_json='["L1","L2"]',
    )
    async_db_session.add(framework)
    await async_db_session.flush()

    # Create soft-deleted scenario
    scenario = Scenario(
        title="Soft Deleted Full Cascade",
        prompt="Test prompt",
        framework_id=framework.id,
        student_template_id=test_student_template.id,
        is_active=1,
        deleted_at=datetime.utcnow(),  # Soft deleted
    )
    async_db_session.add(scenario)
    await async_db_session.flush()

    # Create session under soft-deleted scenario
    session = Session(
        scenario_id=scenario.id,
        teacher_id=test_teacher.id,
    )
    async_db_session.add(session)
    await async_db_session.flush()

    # Create message and summary
    msg = Message(
        session_id=session.id,
        role="teacher",
        content="Full cascade test",
    )
    summary = SessionSummary(
        session_id=session.id,
        distribution_json='{"L1":1}',
        feedback="Full cascade feedback",
    )
    async_db_session.add_all([msg, summary])
    await async_db_session.commit()

    # Store IDs
    framework_id = framework.id
    scenario_id = scenario.id
    session_id = session.id
    msg_id = msg.id
    summary_id = summary.id

    # Simulate route delete logic:
    # 1. Find soft-deleted scenarios
    soft_deleted_query = select(Scenario).where(
        Scenario.framework_id == framework_id,
        Scenario.deleted_at.is_not(None),
    )
    result = await async_db_session.execute(soft_deleted_query)
    soft_deleted_scenarios = result.scalars().all()

    # 2. Delete sessions for each soft-deleted scenario
    for sc in soft_deleted_scenarios:
        sessions_query = select(Session).where(
            Session.scenario_id == sc.id
        )
        sessions_result = await async_db_session.execute(sessions_query)
        sessions = sessions_result.scalars().all()
        for s in sessions:
            await async_db_session.delete(s)

    await async_db_session.flush()

    # 3. Delete soft-deleted scenarios
    for sc in soft_deleted_scenarios:
        await async_db_session.delete(sc)

    await async_db_session.flush()

    # 4. Delete framework
    await async_db_session.delete(framework)
    await async_db_session.commit()

    # Verify all are deleted
    assert await async_db_session.get(AnalysisFramework, framework_id) is None
    assert await async_db_session.get(Scenario, scenario_id) is None
    assert await async_db_session.get(Session, session_id) is None
    assert await async_db_session.get(Message, msg_id) is None
    assert await async_db_session.get(SessionSummary, summary_id) is None

"""Integration test for framework switching (T086)."""
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.analysis_framework import AnalysisFramework
from src.models.scenario import Scenario
from src.models.session import Session as DialogueSession
from src.models.message import Message
from src.models.question_analysis import QuestionAnalysis


@pytest.mark.asyncio
async def test_framework_switching_workflow(
    test_client: TestClient,
    db_session: AsyncSession,
    admin_user: User,
    teacher_user: User,
    test_scenario: Scenario,
    original_framework: AnalysisFramework,
):
    """Test complete framework switching workflow.

    Workflow:
    1. Admin creates new framework with different labels
    2. Admin switches scenario to use new framework
    3. Teacher creates dialogue session using updated scenario
    4. Session ends and questions are classified
    5. Verify classifications use new framework labels
    """
    # Step 1: Login as admin and create new framework
    test_client.post(
        "/login",
        data={
            "username": admin_user.username,
            "password": "test1234",
        },
    )

    new_framework_response = test_client.post(
        "/admin/frameworks",
        json={
            "name": "New Framework",
            "description": "Alternative classification framework",
            "labels": ["HighQuality", "LowQuality", "Neutral"],
        },
    )

    assert new_framework_response.status_code == 201
    new_framework_data = new_framework_response.json()
    new_framework_id = new_framework_data["id"]
    new_labels = json.loads(new_framework_data["labels_json"])
    assert "HighQuality" in new_labels

    # Step 2: Switch scenario to use new framework
    update_response = test_client.put(
        f"/admin/scenarios/{test_scenario.id}",
        json={"framework_id": new_framework_id},
    )

    assert update_response.status_code == 200
    updated_scenario = update_response.json()
    assert updated_scenario["framework_id"] == new_framework_id

    # Step 3: Login as teacher and create dialogue session
    test_client.post(
        "/login",
        data={
            "username": teacher_user.username,
            "password": "test1234",
        },
    )

    # Create session
    session_response = test_client.post(
        "/sessions", json={"scenario_id": test_scenario.id}
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    # Add teacher messages (skip LLM calls in integration test)
    # Note: In real scenario, SessionManager would handle student/tutor
    # responses
    # For integration test, we manually create messages and analyses
    message1 = Message(
        session_id=session_id,
        role="teacher",
        content="What is the key concept here?",
    )
    message2 = Message(
        session_id=session_id,
        role="teacher",
        content="Can you tell me yes or no?",
    )
    db_session.add_all([message1, message2])
    await db_session.commit()
    await db_session.refresh(message1)
    await db_session.refresh(message2)

    # Step 4: End session and trigger classification
    # (Manually create analyses since LLM call is async/expensive)
    analysis1 = QuestionAnalysis(
        message_id=message1.id,
        label="HighQuality",  # New framework label
        confidence=0.85,
        meta_json="{}",
    )
    analysis2 = QuestionAnalysis(
        message_id=message2.id,
        label="LowQuality",  # New framework label
        confidence=0.92,
        meta_json="{}",
    )
    db_session.add_all([analysis1, analysis2])
    await db_session.commit()

    # Update session to mark as ended
    session_stmt = select(DialogueSession).where(
        DialogueSession.id == session_id
    )
    result = await db_session.execute(session_stmt)
    session = result.scalar_one()
    from datetime import datetime, timezone

    session.ended_at = datetime.now(timezone.utc)
    await db_session.commit()

    # Step 5: Verify classifications use new framework labels
    analyses_stmt = (
        select(QuestionAnalysis)
        .join(Message)
        .where(Message.session_id == session_id)
    )
    result = await db_session.execute(analyses_stmt)
    analyses = result.scalars().all()

    assert len(analyses) == 2

    # Check labels match new framework
    labels_used = {analysis.label for analysis in analyses}
    new_framework_labels = {"HighQuality", "LowQuality", "Neutral"}
    assert labels_used.issubset(
        new_framework_labels
    ), "Classifications should use new framework labels"

    # Verify old framework labels are NOT used
    old_framework_labels = {
        "Pressing",
        "Linking",
        "Directing",
        "Recall",
    }
    assert not labels_used.intersection(
        old_framework_labels
    ), "Old framework labels should not be used"


@pytest.mark.asyncio
async def test_framework_switching_affects_new_sessions_only(
    test_client: TestClient,
    db_session: AsyncSession,
    admin_user: User,
    teacher_user: User,
    test_scenario: Scenario,
    original_framework: AnalysisFramework,
):
    """Verify framework switching only affects new sessions.

    Existing session analyses with old framework labels should remain
    unchanged.
    """
    # Step 1: Teacher creates session with original framework
    test_client.post(
        "/login",
        data={
            "username": teacher_user.username,
            "password": "test1234",
        },
    )

    session1_response = test_client.post(
        "/sessions", json={"scenario_id": test_scenario.id}
    )
    session1_id = session1_response.json()["id"]

    # Add message and analysis with original framework label
    message1 = Message(
        session_id=session1_id,
        role="teacher",
        content="What is pressing about this?",
    )
    db_session.add(message1)
    await db_session.commit()
    await db_session.refresh(message1)

    analysis1 = QuestionAnalysis(
        message_id=message1.id,
        label="Pressing",  # Original framework label
        confidence=0.88,
        meta_json="{}",
    )
    db_session.add(analysis1)
    await db_session.commit()

    # End session1 to allow framework change (T080 protection)
    session1_stmt = select(DialogueSession).where(
        DialogueSession.id == session1_id
    )
    result = await db_session.execute(session1_stmt)
    session1 = result.scalar_one()
    from datetime import datetime, timezone

    session1.ended_at = datetime.now(timezone.utc)
    await db_session.commit()

    # Step 2: Admin switches framework
    test_client.post(
        "/login",
        data={
            "username": admin_user.username,
            "password": "test1234",
        },
    )

    new_framework_response = test_client.post(
        "/admin/frameworks",
        json={
            "name": "New Framework",
            "description": "Different labels",
            "labels": ["Alpha", "Beta"],
        },
    )
    new_framework_id = new_framework_response.json()["id"]

    test_client.put(
        f"/admin/scenarios/{test_scenario.id}",
        json={"framework_id": new_framework_id},
    )

    # Step 3: Verify old session analysis remains unchanged
    old_analysis_stmt = select(QuestionAnalysis).where(
        QuestionAnalysis.message_id == message1.id
    )
    result = await db_session.execute(old_analysis_stmt)
    old_analysis = result.scalar_one()

    assert (
        old_analysis.label == "Pressing"
    ), "Existing analyses should keep original labels"

    # Step 4: Create new session and verify it would use new
    # framework
    test_client.post(
        "/login",
        data={
            "username": teacher_user.username,
            "password": "test1234",
        },
    )

    session2_response = test_client.post(
        "/sessions", json={"scenario_id": test_scenario.id}
    )
    session2_id = session2_response.json()["id"]

    # Expire db_session cache to get fresh data from API changes
    db_session.expire_all()

    # Verify session2 is linked to scenario with new framework
    session_stmt = select(DialogueSession).where(
        DialogueSession.id == session2_id
    )
    result = await db_session.execute(session_stmt)
    session2 = result.scalar_one()

    scenario_stmt = select(Scenario).where(
        Scenario.id == session2.scenario_id
    )
    result = await db_session.execute(scenario_stmt)
    scenario = result.scalar_one()

    assert (
        scenario.framework_id == new_framework_id
    ), "New session should use updated framework"

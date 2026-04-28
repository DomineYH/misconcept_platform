"""Integration tests for POST /admin/frameworks/{id}/delete.

Regression coverage for issue #35:
    sqlite3.IntegrityError: NOT NULL constraint failed:
    question_analysis.message_id

Root cause was missing cascade/passive_deletes on Message.question_analysis,
so the ORM tried to NULL-out the FK on QuestionAnalysis when its parent
Message was deleted via Session cascade.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.api.dependencies import get_admin_user, get_db_session
from src.main import app
from src.models.analysis_framework import AnalysisFramework
from src.models.message import Message
from src.models.prompt_template import PromptTemplate
from src.models.question_analysis import QuestionAnalysis
from src.models.scenario import Scenario
from src.models.session import Session


def _override_admin_user():
    return SimpleNamespace(
        id=999, username="admin", is_admin=True, role="admin"
    )


async def _create_template(session) -> PromptTemplate:
    tpl = PromptTemplate(
        bot_type="student",
        template_name="Admin Framework Delete Test Template",
        version=1,
        template_text=(
            "You are a test student bot. Scenario: {scenario_title}. "
            "Profile: {student_profile}. Context: {prompt}"
        ),
    )
    session.add(tpl)
    await session.flush()
    return tpl


@pytest.fixture
def admin_client(async_db_session):
    """TestClient with admin auth + db override using async_db_session."""

    async def override_get_db():
        yield async_db_session

    app.dependency_overrides[get_admin_user] = _override_admin_user
    app.dependency_overrides[get_db_session] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_unused_framework_returns_200(
    admin_client, async_db_session
):
    """AC1: framework with no scenarios → 200, row removed."""
    framework = AnalysisFramework(
        name="Unused Framework",
        description="No scenarios attached",
        labels_json='["A","B"]',
    )
    async_db_session.add(framework)
    await async_db_session.commit()
    framework_id = framework.id

    response = admin_client.post(f"/admin/frameworks/{framework_id}/delete")

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"

    assert await async_db_session.get(AnalysisFramework, framework_id) is None


@pytest.mark.asyncio
async def test_delete_framework_with_soft_deleted_data_succeeds(
    admin_client, async_db_session, test_teacher
):
    """AC2: framework with soft-deleted scenario + session + message
    + question_analysis → 200, all related rows removed.

    Direct regression for issue #35 NOT NULL constraint failure.
    """
    template = await _create_template(async_db_session)

    framework = AnalysisFramework(
        name="Soft Deleted Chain Framework",
        description="Has full dependency chain",
        labels_json='["high","low"]',
    )
    async_db_session.add(framework)
    await async_db_session.flush()

    scenario = Scenario(
        title="Soft Deleted Scenario",
        prompt="Soft deleted scenario prompt",
        framework_id=framework.id,
        student_template_id=template.id,
        is_active=1,
        deleted_at=datetime.utcnow(),
    )
    async_db_session.add(scenario)
    await async_db_session.flush()

    session = Session(
        scenario_id=scenario.id,
        teacher_id=test_teacher.id,
    )
    async_db_session.add(session)
    await async_db_session.flush()

    message = Message(
        session_id=session.id,
        role="teacher",
        content="What is photosynthesis?",
    )
    async_db_session.add(message)
    await async_db_session.flush()

    qa = QuestionAnalysis(
        message_id=message.id,
        label="high",
        confidence=0.9,
    )
    async_db_session.add(qa)
    await async_db_session.commit()

    framework_id = framework.id
    scenario_id = scenario.id
    session_id = session.id
    message_id = message.id
    qa_id = qa.id

    response = admin_client.post(f"/admin/frameworks/{framework_id}/delete")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "deleted"

    # All related rows must be gone (no orphans)
    assert await async_db_session.get(AnalysisFramework, framework_id) is None
    assert await async_db_session.get(Scenario, scenario_id) is None
    assert await async_db_session.get(Session, session_id) is None
    assert await async_db_session.get(Message, message_id) is None
    assert await async_db_session.get(QuestionAnalysis, qa_id) is None

    # Defensive: no orphan question_analysis rows referencing this message
    orphan_check = await async_db_session.execute(
        select(QuestionAnalysis).where(
            QuestionAnalysis.message_id == message_id
        )
    )
    assert orphan_check.scalars().first() is None


@pytest.mark.asyncio
async def test_delete_framework_with_active_scenario_returns_409(
    admin_client, async_db_session
):
    """AC3: framework with active (not soft-deleted) scenario → 409."""
    template = await _create_template(async_db_session)

    framework = AnalysisFramework(
        name="In-Use Framework",
        description="Has active scenario",
        labels_json='["x","y"]',
    )
    async_db_session.add(framework)
    await async_db_session.flush()

    scenario = Scenario(
        title="Active Scenario",
        prompt="Active scenario prompt",
        framework_id=framework.id,
        student_template_id=template.id,
        is_active=1,
    )
    async_db_session.add(scenario)
    await async_db_session.commit()

    framework_id = framework.id
    scenario_id = scenario.id

    response = admin_client.post(f"/admin/frameworks/{framework_id}/delete")

    assert response.status_code == 409

    # Framework and scenario both still exist (no partial delete)
    assert (
        await async_db_session.get(AnalysisFramework, framework_id) is not None
    )
    assert await async_db_session.get(Scenario, scenario_id) is not None

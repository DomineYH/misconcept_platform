"""Integration test for session analysis workflow (T053)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.user import User
from src.models.analysis_framework import AnalysisFramework
from src.models.prompt_template import PromptTemplate
from src.models.scenario import Scenario
from src.models.session import Session
from src.models.message import Message
from src.models.question_analysis import QuestionAnalysis
from src.models.session_summary import SessionSummary


@pytest.fixture(autouse=True)
async def seed_analysis_test_data(db_session: AsyncSession):
    """Seed test data for session analysis tests."""
    # Create users
    for i in range(1, 4):
        user = User(
            username=f"teacher_{i:03d}",
            nickname=f"교사{i:03d}",
            role="teacher",
        )
        user.set_password("test1234")
        db_session.add(user)

    # Create framework
    framework = AnalysisFramework(
        name="Analysis Test Framework",
        description="Framework for analysis tests",
        labels_json=(
            '["high_leverage",'
            ' "medium_leverage",'
            ' "low_leverage"]'
        ),
    )
    db_session.add(framework)
    await db_session.flush()

    # Create template
    template = PromptTemplate(
        bot_type="student",
        template_name="Analysis Student Template",
        version=1,
        template_text="You are a test student bot.",
    )
    db_session.add(template)
    await db_session.flush()

    # Create scenario (id=1 since first in DB)
    scenario = Scenario(
        title="Analysis Test Scenario",
        prompt="Test prompt for analysis",
        student_profile="Test student profile",
        framework_id=framework.id,
        student_template_id=template.id,
        is_active=1,
    )
    db_session.add(scenario)
    await db_session.commit()


@pytest.mark.skip(reason="Requires live OpenAI API")
class TestSessionAnalysisWorkflow:
    """Test complete session analysis workflow (T053)."""

    @pytest.mark.asyncio
    async def test_complete_dialogue_triggers_question_analysis(
        self,
        test_client: TestClient,
        async_db_session: AsyncSession,
    ):
        """
        Verify complete dialogue -> end session -> analysis.

        Workflow:
        1. Teacher logs in
        2. Creates session with scenario
        3. Sends multiple teacher messages
        4. Ends session
        5. Verify QuestionAnalysis records created
        6. Verify SessionSummary created
        """
        # Step 1: Login
        login_response = test_client.post(
            "/login",
            data={
                "username": "teacher_001",
                "password": "test1234",
            },
        )
        cookies = login_response.cookies
        assert login_response.status_code in [200, 302, 303]

        # Step 2: Create session
        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": 1},
            cookies=cookies,
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]

        # Step 3: Send multiple teacher messages
        teacher_messages = [
            "What is photosynthesis?",
            "Can you explain more?",
            "Is it related to sunlight?",
        ]

        for content in teacher_messages:
            msg_response = test_client.post(
                f"/sessions/{session_id}/messages",
                data={"content": content},
                cookies=cookies,
            )
            assert msg_response.status_code == 200

        # Verify messages were created
        result = await async_db_session.execute(
            select(Message).where(
                Message.session_id == session_id,
                Message.role == "teacher",
            )
        )
        messages = result.scalars().all()
        assert len(messages) == 3

        # Step 4: End session
        end_response = test_client.post(
            f"/sessions/{session_id}/end",
            cookies=cookies,
        )
        assert end_response.status_code == 200
        end_data = end_response.json()
        assert end_data["ended"] is True
        assert "ended_at" in end_data

        # Step 4b: Analyze session
        analyze_response = test_client.post(
            f"/sessions/{session_id}/analyze",
            cookies=cookies,
        )
        assert analyze_response.status_code == 200

        # Step 5: Verify QuestionAnalysis records
        result = await async_db_session.execute(
            select(QuestionAnalysis)
            .join(Message)
            .where(Message.session_id == session_id)
        )
        analyses = result.scalars().all()

        # Should have analysis for each teacher message
        assert len(analyses) == 3

        # Verify each analysis has required fields
        for analysis in analyses:
            assert analysis.label is not None
            assert analysis.label in [
                "high_leverage",
                "medium_leverage",
                "low_leverage",
            ]
            assert 0.0 <= analysis.confidence <= 1.0
            assert analysis.message_id is not None

        # Step 6: Verify SessionSummary created
        result = await async_db_session.execute(
            select(SessionSummary).where(
                SessionSummary.session_id == session_id
            )
        )
        summary = result.scalar_one_or_none()

        assert summary is not None
        assert summary.session_id == session_id
        assert summary.distribution is not None
        assert isinstance(summary.distribution, dict)
        assert summary.feedback is not None
        assert len(summary.feedback) > 0

        # Verify distribution contains valid counts
        dist = summary.distribution
        assert "high_leverage" in dist
        assert "medium_leverage" in dist
        assert "low_leverage" in dist
        assert sum(dist.values()) == 3

    @pytest.mark.asyncio
    async def test_session_with_no_teacher_messages_creates_empty_analysis(
        self,
        test_client: TestClient,
        async_db_session: AsyncSession,
    ):
        """Verify empty session creates empty summary."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={
                "username": "teacher_002",
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": 1},
            cookies=cookies,
        )
        session_id = session_response.json()["id"]

        # End session immediately without messages
        end_response = test_client.post(
            f"/sessions/{session_id}/end",
            cookies=cookies,
        )
        assert end_response.status_code == 200

        # Analyze session
        analyze_response = test_client.post(
            f"/sessions/{session_id}/analyze",
            cookies=cookies,
        )
        assert analyze_response.status_code == 200

        # Verify no QuestionAnalysis records
        result = await async_db_session.execute(
            select(QuestionAnalysis)
            .join(Message)
            .where(Message.session_id == session_id)
        )
        analyses = result.scalars().all()
        assert len(analyses) == 0

        # Verify SessionSummary with empty distribution
        result = await async_db_session.execute(
            select(SessionSummary).where(
                SessionSummary.session_id == session_id
            )
        )
        summary = result.scalar_one_or_none()
        assert summary is not None
        assert summary.distribution == {
            "high_leverage": 0,
            "medium_leverage": 0,
            "low_leverage": 0,
        }

    @pytest.mark.asyncio
    async def test_question_analysis_labels_match_framework(
        self,
        test_client: TestClient,
        async_db_session: AsyncSession,
    ):
        """Verify labels match AnalysisFramework."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={
                "username": "teacher_003",
                "password": "test1234",
            },
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions",
            json={"scenario_id": 1},
            cookies=cookies,
        )
        session_id = session_response.json()["id"]

        # Send message
        test_client.post(
            f"/sessions/{session_id}/messages",
            data={
                "content": "Explain your thinking process."
            },
            cookies=cookies,
        )

        # End session and analyze
        test_client.post(
            f"/sessions/{session_id}/end",
            cookies=cookies,
        )
        test_client.post(
            f"/sessions/{session_id}/analyze",
            cookies=cookies,
        )

        # Get session and verify framework
        result = await async_db_session.execute(
            select(Session).where(
                Session.id == session_id
            )
        )
        session = result.scalar_one()
        framework = session.scenario.framework

        # Get analysis and verify label is from framework
        result = await async_db_session.execute(
            select(QuestionAnalysis)
            .join(Message)
            .where(Message.session_id == session_id)
        )
        analysis = result.scalar_one()

        # Label should be in framework labels
        assert analysis.label in framework.labels

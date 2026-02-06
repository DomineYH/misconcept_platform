"""Unit tests for database models (T027-T030)."""
import pytest
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import (
    User,
    AnalysisFramework,
    Scenario,
    Session,
    Message,
    QuestionAnalysis,
    SessionSummary,
)


class TestUserModel:
    """Test User model creation and constraints (T027)."""

    async def test_create_user_minimal(self, db_session: AsyncSession):
        """Test creating user with minimal required fields."""
        user = User(student_uid="student_001", nickname="김교사")

        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.id is not None
        assert user.student_uid == "student_001"
        assert user.nickname == "김교사"
        assert user.role == "teacher"  # Default
        assert isinstance(user.created_at, datetime)

    async def test_user_unique_constraint(self, db_session: AsyncSession):
        """Test unique constraint on (student_uid, nickname)."""
        user1 = User(student_uid="student_002", nickname="박교사")
        db_session.add(user1)
        await db_session.commit()

        # Try to create duplicate
        user2 = User(student_uid="student_002", nickname="박교사")
        db_session.add(user2)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()
        await db_session.rollback()

    async def test_user_role_constraint(self, db_session: AsyncSession):
        """Test role check constraint."""
        user = User(
            student_uid="student_003", nickname="정교사", role="invalid"
        )
        db_session.add(user)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()
        await db_session.rollback()


class TestAnalysisFrameworkModel:
    """Test AnalysisFramework model (T028)."""

    async def test_create_framework_with_labels(
        self, db_session: AsyncSession
    ):
        """Test framework creation with JSON labels."""
        labels = ["Pressing", "Linking", "Directing", "Recall"]
        framework = AnalysisFramework(
            name="High/Low Leverage",
            description="Question taxonomy for leverage",
            labels_json=json.dumps(labels),
        )

        db_session.add(framework)
        await db_session.commit()
        await db_session.refresh(framework)

        assert framework.id is not None
        assert framework.name == "High/Low Leverage"
        assert framework.labels == labels
        assert len(framework.labels) == 4

    async def test_framework_labels_property(
        self, db_session: AsyncSession
    ):
        """Test labels property getter/setter."""
        framework = AnalysisFramework(
            name="Test Framework", labels_json='["A", "B", "C"]'
        )

        db_session.add(framework)
        await db_session.commit()

        # Test getter
        assert framework.labels == ["A", "B", "C"]

        # Test setter
        framework.labels = ["X", "Y"]
        assert framework.labels_json == '["X", "Y"]'

    async def test_framework_invalid_json(self, db_session: AsyncSession):
        """Test validation rejects invalid JSON at creation time."""
        # AnalysisFramework validates labels_json on creation
        with pytest.raises(Exception):  # json.JSONDecodeError
            AnalysisFramework(
                name="Invalid", labels_json="not valid json"
            )


class TestScenarioModel:
    """Test Scenario model (T028)."""

    async def test_create_scenario_with_framework(
        self, db_session: AsyncSession
    ):
        """Test scenario creation with framework relationship."""
        # Create framework first
        framework = AnalysisFramework(
            name="Test Framework", labels_json='["A", "B"]'
        )
        db_session.add(framework)
        await db_session.commit()

        # Create scenario
        from src.models.prompt_template import PromptTemplate


        template = PromptTemplate(
            bot_type="student",
            template_name="Test Template",
            version=1,
            template_text="Test prompt",
        )
        db_session.add(template)
        await db_session.commit()

        scenario = Scenario(
            title="Fraction Addition",
            prompt="Student struggles with adding fractions",
            framework_id=framework.id,
            student_template_id=template.id,
        )

        db_session.add(scenario)
        await db_session.commit()
        await db_session.refresh(scenario)

        assert scenario.id is not None
        assert scenario.title == "Fraction Addition"
        assert scenario.is_active == 1
        assert scenario.framework_id == framework.id

    async def test_scenario_active_constraint(
        self, db_session: AsyncSession
    ):
        """Test is_active check constraint."""
        framework = AnalysisFramework(
            name="F1", labels_json='["A", "B"]'
        )
        db_session.add(framework)
        await db_session.commit()

        from src.models.prompt_template import PromptTemplate


        template = PromptTemplate(
            bot_type="student",
            template_name="Test Template",
            version=1,
            template_text="Test prompt",
        )
        db_session.add(template)
        await db_session.commit()

        scenario = Scenario(
            title="Test",
            prompt="Prompt",
            framework_id=framework.id,
            student_template_id=template.id,
            is_active=2,  # Invalid
        )

        db_session.add(scenario)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()
        await db_session.rollback()


class TestSessionAndMessageModels:
    """Test Session and Message models (T029, T030)."""

    async def test_create_session(self, db_session: AsyncSession):
        """Test session creation with relationships."""
        # Setup: framework, user, scenario
        framework = AnalysisFramework(
            name="F2", labels_json='["A", "B"]'
        )
        user = User(student_uid="s001", nickname="김교사")
        db_session.add_all([framework, user])
        await db_session.commit()

        from src.models.prompt_template import PromptTemplate


        template = PromptTemplate(
            bot_type="student",
            template_name="Test Template",
            version=1,
            template_text="Test prompt",
        )
        db_session.add(template)
        await db_session.commit()

        scenario = Scenario(
            title="Test", prompt="P", framework_id=framework.id,
            student_template_id=template.id,
        )
        db_session.add(scenario)
        await db_session.commit()

        # Create session
        session = Session(scenario_id=scenario.id, teacher_id=user.id)

        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        assert session.id is not None
        assert session.is_active is True
        assert session.ended_at is None

    async def test_session_with_messages(self, db_session: AsyncSession):
        """Test session with multiple messages."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        # Setup
        framework = AnalysisFramework(
            name="F3", labels_json='["A", "B"]'
        )
        user = User(student_uid="s002", nickname="박교사")
        db_session.add_all([framework, user])
        await db_session.commit()

        from src.models.prompt_template import PromptTemplate


        template = PromptTemplate(
            bot_type="student",
            template_name="Test Template",
            version=1,
            template_text="Test prompt",
        )
        db_session.add(template)
        await db_session.commit()

        scenario = Scenario(
            title="T2", prompt="P2", framework_id=framework.id,
            student_template_id=template.id,
        )
        db_session.add(scenario)
        await db_session.commit()

        session = Session(scenario_id=scenario.id, teacher_id=user.id)
        db_session.add(session)
        await db_session.commit()

        # Add messages
        msg1 = Message(
            session_id=session.id, role="teacher", content="What is 2+2?"
        )
        msg2 = Message(
            session_id=session.id, role="student", content="It's 4!"
        )

        db_session.add_all([msg1, msg2])
        await db_session.commit()

        # Query with eager loading to verify messages
        result = await db_session.execute(
            select(Session)
            .options(selectinload(Session.messages))
            .where(Session.id == session.id)
        )
        loaded_session = result.scalar_one()

        assert len(loaded_session.messages) == 2
        assert loaded_session.messages[0].role == "teacher"
        assert loaded_session.messages[1].role == "student"

    async def test_message_cascade_delete(self, db_session: AsyncSession):
        """Test messages are deleted when session is deleted."""
        # Setup
        framework = AnalysisFramework(
            name="F4", labels_json='["A", "B"]'
        )
        user = User(student_uid="s003", nickname="정교사")
        db_session.add_all([framework, user])
        await db_session.commit()

        from src.models.prompt_template import PromptTemplate


        template = PromptTemplate(
            bot_type="student",
            template_name="Test Template",
            version=1,
            template_text="Test prompt",
        )
        db_session.add(template)
        await db_session.commit()

        scenario = Scenario(
            title="T3", prompt="P3", framework_id=framework.id,
            student_template_id=template.id,
        )
        db_session.add(scenario)
        await db_session.commit()

        session = Session(scenario_id=scenario.id, teacher_id=user.id)
        db_session.add(session)
        await db_session.commit()

        message = Message(
            session_id=session.id, role="teacher", content="Test"
        )
        db_session.add(message)
        await db_session.commit()

        message_id = message.id

        # Delete session
        await db_session.delete(session)
        await db_session.commit()

        # Verify message was also deleted
        from sqlalchemy import select

        result = await db_session.execute(
            select(Message).where(Message.id == message_id)
        )
        assert result.scalar_one_or_none() is None


class TestQuestionAnalysisModel:
    """Test QuestionAnalysis model (T057)."""

    async def test_create_question_analysis(self, db_session: AsyncSession):
        """Test creating QuestionAnalysis for teacher message."""
        # Setup: framework, user, scenario, session, message
        framework = AnalysisFramework(
            name="F5", labels_json='["high_leverage", "low_leverage"]'
        )
        user = User(student_uid="s004", nickname="최교사")
        db_session.add_all([framework, user])
        await db_session.commit()

        from src.models.prompt_template import PromptTemplate


        template = PromptTemplate(
            bot_type="student",
            template_name="Test Template",
            version=1,
            template_text="Test prompt",
        )
        db_session.add(template)
        await db_session.commit()

        scenario = Scenario(
            title="T4", prompt="P4", framework_id=framework.id,
            student_template_id=template.id,
        )
        db_session.add(scenario)
        await db_session.commit()

        session = Session(scenario_id=scenario.id, teacher_id=user.id)
        db_session.add(session)
        await db_session.commit()

        message = Message(
            session_id=session.id, role="teacher", content="What is X?"
        )
        db_session.add(message)
        await db_session.commit()

        # Create QuestionAnalysis
        analysis = QuestionAnalysis(
            message_id=message.id,
            label="high_leverage",
            confidence=0.85,
            meta_json='{"evidence": "Open question"}',
        )
        db_session.add(analysis)
        await db_session.commit()
        await db_session.refresh(analysis)

        assert analysis.id is not None
        assert analysis.message_id == message.id
        assert analysis.label == "high_leverage"
        assert analysis.confidence == 0.85
        assert "evidence" in analysis.meta_json

    async def test_confidence_range_constraint(
        self, db_session: AsyncSession
    ):
        """Test confidence must be between 0.0 and 1.0."""
        # Setup
        framework = AnalysisFramework(
            name="F6", labels_json='["A", "B"]'
        )
        user = User(student_uid="s005", nickname="강교사")
        db_session.add_all([framework, user])
        await db_session.commit()

        from src.models.prompt_template import PromptTemplate


        template = PromptTemplate(
            bot_type="student",
            template_name="Test Template",
            version=1,
            template_text="Test prompt",
        )
        db_session.add(template)
        await db_session.commit()

        scenario = Scenario(
            title="T5", prompt="P5", framework_id=framework.id,
            student_template_id=template.id,
        )
        db_session.add(scenario)
        await db_session.commit()

        session = Session(scenario_id=scenario.id, teacher_id=user.id)
        db_session.add(session)
        await db_session.commit()

        message = Message(
            session_id=session.id, role="teacher", content="Q?"
        )
        db_session.add(message)
        await db_session.commit()

        # Try invalid confidence (>1.0)
        analysis = QuestionAnalysis(
            message_id=message.id, label="A", confidence=1.5
        )
        db_session.add(analysis)

        with pytest.raises(Exception):  # CheckConstraint
            await db_session.commit()
        await db_session.rollback()

    async def test_question_analysis_direct_delete(
        self, db_session: AsyncSession
    ):
        """Test QuestionAnalysis can be directly deleted."""
        from sqlalchemy import select, delete

        # Setup
        framework = AnalysisFramework(
            name="F7", labels_json='["B", "C"]'
        )
        user = User(student_uid="s006", nickname="윤교사")
        db_session.add_all([framework, user])
        await db_session.commit()

        from src.models.prompt_template import PromptTemplate


        template = PromptTemplate(
            bot_type="student",
            template_name="Test Template",
            version=1,
            template_text="Test prompt",
        )
        db_session.add(template)
        await db_session.commit()

        scenario = Scenario(
            title="T6", prompt="P6", framework_id=framework.id,
            student_template_id=template.id,
        )
        db_session.add(scenario)
        await db_session.commit()

        session = Session(scenario_id=scenario.id, teacher_id=user.id)
        db_session.add(session)
        await db_session.commit()

        message = Message(
            session_id=session.id, role="teacher", content="Q2?"
        )
        db_session.add(message)
        await db_session.commit()

        message_id = message.id

        analysis = QuestionAnalysis(
            message_id=message_id, label="B", confidence=0.9
        )
        db_session.add(analysis)
        await db_session.commit()

        analysis_id = analysis.id

        # Delete analysis directly
        await db_session.execute(
            delete(QuestionAnalysis).where(QuestionAnalysis.id == analysis_id)
        )
        await db_session.commit()

        # Verify analysis was deleted
        result = await db_session.execute(
            select(QuestionAnalysis).where(
                QuestionAnalysis.id == analysis_id
            )
        )
        assert result.scalar_one_or_none() is None

        # Verify message still exists
        result = await db_session.execute(
            select(Message).where(Message.id == message_id)
        )
        assert result.scalar_one_or_none() is not None


class TestSessionSummaryModel:
    """Test SessionSummary model (T058)."""

    async def test_create_session_summary(self, db_session: AsyncSession):
        """Test creating SessionSummary with distribution."""
        from sqlalchemy import select

        # Setup
        framework = AnalysisFramework(
            name="F8", labels_json='["C", "D"]'
        )
        user = User(student_uid="s007", nickname="이교사")
        db_session.add_all([framework, user])
        await db_session.commit()

        from src.models.prompt_template import PromptTemplate


        template = PromptTemplate(
            bot_type="student",
            template_name="Test Template",
            version=1,
            template_text="Test prompt",
        )
        db_session.add(template)
        await db_session.commit()

        scenario = Scenario(
            title="T7", prompt="P7", framework_id=framework.id,
            student_template_id=template.id,
        )
        db_session.add(scenario)
        await db_session.commit()

        session = Session(scenario_id=scenario.id, teacher_id=user.id)
        db_session.add(session)
        await db_session.commit()

        # Create summary
        distribution = {
            "high_leverage": 3,
            "medium_leverage": 2,
            "low_leverage": 1,
        }
        summary = SessionSummary(
            session_id=session.id,
            distribution_json=json.dumps(distribution),
            feedback="Good balance of questions.",
        )
        db_session.add(summary)
        await db_session.commit()

        # Re-fetch to verify
        result = await db_session.execute(
            select(SessionSummary).where(SessionSummary.id == summary.id)
        )
        loaded_summary = result.scalar_one()

        assert loaded_summary.id is not None
        assert loaded_summary.session_id == session.id
        assert loaded_summary.distribution == distribution
        assert "Good balance" in loaded_summary.feedback

    async def test_distribution_property(self, db_session: AsyncSession):
        """Test distribution property getter/setter."""
        from sqlalchemy import select

        # Setup
        framework = AnalysisFramework(
            name="F9", labels_json='["D", "E"]'
        )
        user = User(student_uid="s008", nickname="조교사")
        db_session.add_all([framework, user])
        await db_session.commit()

        from src.models.prompt_template import PromptTemplate


        template = PromptTemplate(
            bot_type="student",
            template_name="Test Template",
            version=1,
            template_text="Test prompt",
        )
        db_session.add(template)
        await db_session.commit()

        scenario = Scenario(
            title="T8", prompt="P8", framework_id=framework.id,
            student_template_id=template.id,
        )
        db_session.add(scenario)
        await db_session.commit()

        session = Session(scenario_id=scenario.id, teacher_id=user.id)
        db_session.add(session)
        await db_session.commit()

        # Create summary
        summary = SessionSummary(
            session_id=session.id,
            distribution_json='{"A": 1, "B": 2}',
        )
        db_session.add(summary)
        await db_session.commit()

        summary_id = summary.id

        # Test getter
        assert summary.distribution == {"A": 1, "B": 2}

        # Test setter
        summary.distribution = {"X": 5, "Y": 3}
        await db_session.commit()

        # Re-fetch to verify
        result = await db_session.execute(
            select(SessionSummary).where(SessionSummary.id == summary_id)
        )
        loaded_summary = result.scalar_one()
        assert loaded_summary.distribution == {"X": 5, "Y": 3}

    async def test_unique_session_id_constraint(
        self, db_session: AsyncSession
    ):
        """Test one summary per session constraint."""
        # Setup
        framework = AnalysisFramework(
            name="F10", labels_json='["E", "F"]'
        )
        user = User(student_uid="s009", nickname="한교사")
        db_session.add_all([framework, user])
        await db_session.commit()

        from src.models.prompt_template import PromptTemplate


        template = PromptTemplate(
            bot_type="student",
            template_name="Test Template",
            version=1,
            template_text="Test prompt",
        )
        db_session.add(template)
        await db_session.commit()

        scenario = Scenario(
            title="T9", prompt="P9", framework_id=framework.id,
            student_template_id=template.id,
        )
        db_session.add(scenario)
        await db_session.commit()

        session = Session(scenario_id=scenario.id, teacher_id=user.id)
        db_session.add(session)
        await db_session.commit()

        # Create first summary
        summary1 = SessionSummary(
            session_id=session.id, distribution_json='{"A": 1}'
        )
        db_session.add(summary1)
        await db_session.commit()

        # Try to create duplicate summary
        summary2 = SessionSummary(
            session_id=session.id, distribution_json='{"B": 2}'
        )
        db_session.add(summary2)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()
        await db_session.rollback()

"""Unit tests for SessionManager service.

Tests dialogue orchestration with mocked bots and database.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

from src.services.session_mgr import SessionManager


def _mock_scenario(
    chat_model=None,
    tutor_template_id=None,
    tutor_intervention_threshold=None,
    student_template_id=1,
):
    """Create mock Scenario with configurable overrides.

    Args:
        chat_model: Override chat model (None = use global)
        tutor_template_id: Tutor template ID (None = disabled)
        tutor_intervention_threshold: Override threshold
        student_template_id: Student template ID

    Returns:
        Mock Scenario object
    """
    scenario = Mock()
    scenario.id = 1
    scenario.title = "Moon Phases"
    scenario.prompt = "Moon is a light source"
    scenario.student_profile = "Grade 5 student"
    scenario.chat_model = chat_model
    scenario.tutor_template_id = tutor_template_id
    scenario.tutor_intervention_threshold = tutor_intervention_threshold
    scenario.student_template_id = student_template_id
    # tutor_enabled is a property based on tutor_template_id
    type(scenario).tutor_enabled = PropertyMock(
        return_value=tutor_template_id is not None
    )
    return scenario


def _mock_session(session_id=1, scenario_id=1):
    """Create mock Session object."""
    session = Mock()
    session.id = session_id
    session.scenario_id = scenario_id
    session.ended_at = None
    session.deleted_at = None
    session.tutor_intervention_count = 0
    session.tutor_question_count = 0
    return session


def _mock_db_session():
    """Create AsyncSession-like mock with sync add()."""
    db = AsyncMock()
    db.add = Mock()
    return db


def _mock_scalar_result(value):
    """Create result mock that supports scalar_one and scalar_one_or_none."""
    result = Mock()
    result.scalar_one.return_value = value
    result.scalar_one_or_none.return_value = value
    return result


class TestLoadBotConfig:
    """Tests for SessionManager._load_bot_config method."""

    def _make_manager(self):
        """Create SessionManager with mocked db."""
        return SessionManager(db_session=_mock_db_session(), session_id=1)

    @patch("src.services.session_mgr.config")
    def test_uses_scenario_chat_model_override(self, mock_config):
        """Should prefer scenario chat_model over config."""
        mock_config.CHAT_MODEL = "gpt-5"
        mock_config.STUDENT_REASONING = "medium"
        mock_config.STUDENT_MAX_TOKENS = 750
        mock_config.ANALYSIS_MODEL = "gpt-5.2"
        mock_config.TUTOR_REASONING = "low"
        mock_config.TUTOR_MAX_TOKENS = 1125
        mock_config.TUTOR_INTERVENTION_THRESHOLD = 3

        mgr = self._make_manager()
        scenario = _mock_scenario(chat_model="gpt-4-turbo")
        result = mgr._load_bot_config(scenario)

        assert result["student_model"] == "gpt-4-turbo"

    @patch("src.services.session_mgr.config")
    def test_falls_back_to_config_chat_model(self, mock_config):
        """Should use config CHAT_MODEL when scenario has no override."""
        mock_config.CHAT_MODEL = "gpt-5"
        mock_config.STUDENT_REASONING = "medium"
        mock_config.STUDENT_MAX_TOKENS = 750
        mock_config.ANALYSIS_MODEL = "gpt-5.2"
        mock_config.TUTOR_REASONING = "low"
        mock_config.TUTOR_MAX_TOKENS = 1125
        mock_config.TUTOR_INTERVENTION_THRESHOLD = 3

        mgr = self._make_manager()
        scenario = _mock_scenario(chat_model=None)
        result = mgr._load_bot_config(scenario)

        assert result["student_model"] == "gpt-5"

    @patch("src.services.session_mgr.config")
    def test_tutor_enabled_from_scenario(self, mock_config):
        """Should reflect scenario tutor_enabled property."""
        mock_config.CHAT_MODEL = "gpt-5"
        mock_config.STUDENT_REASONING = "medium"
        mock_config.STUDENT_MAX_TOKENS = 750
        mock_config.ANALYSIS_MODEL = "gpt-5.2"
        mock_config.TUTOR_REASONING = "low"
        mock_config.TUTOR_MAX_TOKENS = 1125
        mock_config.TUTOR_INTERVENTION_THRESHOLD = 3

        mgr = self._make_manager()

        # Tutor enabled (template assigned)
        scenario_on = _mock_scenario(tutor_template_id=2)
        result = mgr._load_bot_config(scenario_on)
        assert result["tutor_enabled"] is True

        # Tutor disabled (no template)
        scenario_off = _mock_scenario(tutor_template_id=None)
        result = mgr._load_bot_config(scenario_off)
        assert result["tutor_enabled"] is False

    @patch("src.services.session_mgr.config")
    def test_scenario_intervention_threshold_override(self, mock_config):
        """Should use scenario threshold when set."""
        mock_config.CHAT_MODEL = "gpt-5"
        mock_config.STUDENT_REASONING = "medium"
        mock_config.STUDENT_MAX_TOKENS = 750
        mock_config.ANALYSIS_MODEL = "gpt-5.2"
        mock_config.TUTOR_REASONING = "low"
        mock_config.TUTOR_MAX_TOKENS = 1125
        mock_config.TUTOR_INTERVENTION_THRESHOLD = 3

        mgr = self._make_manager()
        scenario = _mock_scenario(tutor_intervention_threshold=5)
        result = mgr._load_bot_config(scenario)

        assert result["tutor_intervention_threshold"] == 5

    @patch("src.services.session_mgr.config")
    def test_no_legacy_model_fallbacks(self, mock_config):
        """Should not fall back to legacy models."""
        mock_config.CHAT_MODEL = "gpt-5"
        mock_config.STUDENT_REASONING = "medium"
        mock_config.STUDENT_MAX_TOKENS = 750
        mock_config.ANALYSIS_MODEL = "gpt-5.2"
        mock_config.TUTOR_REASONING = "low"
        mock_config.TUTOR_MAX_TOKENS = 1125
        mock_config.TUTOR_INTERVENTION_THRESHOLD = 3

        mgr = self._make_manager()
        scenario = _mock_scenario(chat_model=None)
        result = mgr._load_bot_config(scenario)

        assert result["student_model"] == "gpt-5"
        assert result["tutor_model"] == "gpt-5.2"
        assert "gpt-4-turbo" not in str(result.values())
        assert "gpt-3.5-turbo" not in str(result.values())

    @patch("src.services.session_mgr.config")
    def test_config_fallback_for_all_fields(self, mock_config):
        """Should load all config defaults correctly."""
        mock_config.CHAT_MODEL = "gpt-5"
        mock_config.STUDENT_REASONING = "high"
        mock_config.STUDENT_MAX_TOKENS = 500
        mock_config.ANALYSIS_MODEL = "gpt-5.2"
        mock_config.TUTOR_REASONING = "low"
        mock_config.TUTOR_MAX_TOKENS = 1000
        mock_config.TUTOR_INTERVENTION_THRESHOLD = 4

        mgr = self._make_manager()
        scenario = _mock_scenario()
        result = mgr._load_bot_config(scenario)

        assert result["student_model"] == "gpt-5"
        assert result["student_reasoning"] == "high"
        assert result["student_max_tokens"] == 500
        assert result["tutor_model"] == "gpt-5.2"
        assert result["tutor_reasoning"] == "low"
        assert result["tutor_max_tokens"] == 1000
        assert result["tutor_intervention_threshold"] == 4


class TestSessionManagerProcessTeacherMessage:
    """Tests for SessionManager.process_teacher_message method."""

    def _setup_manager(
        self,
        tutor_enabled=False,
        tutor_template_id=None,
    ):
        """Create SessionManager with initialized mocked bots.

        Returns:
            Tuple of (manager, mock_student_bot, mock_tutor_bot,
                      mock_analyzer)
        """
        db = _mock_db_session()
        mock_sess = _mock_session()
        mock_result = _mock_scalar_result(mock_sess)
        db.execute = AsyncMock(return_value=mock_result)

        mgr = SessionManager(db_session=db, session_id=1)
        mgr.scenario = _mock_scenario(tutor_template_id=tutor_template_id)

        # Mock StudentBot
        mock_student = AsyncMock()
        mock_student.generate_response = AsyncMock(
            return_value=(
                "Student says hello",
                {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            )
        )
        mock_student.model = "gpt-5"
        mgr.student_bot = mock_student

        # Mock MisconceptionAnalyzer
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze_student_response = AsyncMock(
            return_value={
                "maintains_misconception": True,
                "misconception_strength": 0.8,
                "evidence": "Test evidence",
            }
        )
        mgr.misconception_analyzer = mock_analyzer

        # Mock TutorBot (only if enabled)
        mock_tutor = None
        if tutor_enabled:
            mock_tutor = AsyncMock()
            mock_tutor.generate_feedback = AsyncMock(
                return_value=(
                    "Tutor feedback here",
                    {
                        "prompt_tokens": 200,
                        "completion_tokens": 100,
                        "total_tokens": 300,
                    },
                )
            )
            mock_tutor.model = "gpt-5.2"
            mock_tutor.intervention_count = 0
            mock_tutor.question_count = 0
            mgr.tutor_bot = mock_tutor
        else:
            mgr.tutor_bot = None

        return mgr, mock_student, mock_tutor, mock_analyzer

    async def test_saves_teacher_message_and_returns_student(self):
        """Should save teacher msg and return student response."""
        mgr, mock_student, _, _ = self._setup_manager()

        # Mock conversation history
        mgr._get_conversation_history = AsyncMock(return_value=[])
        mgr._log_api_usage = AsyncMock()

        messages = await mgr.process_teacher_message("What is the moon?")

        # Should have teacher + student messages
        assert len(messages) == 2
        assert messages[0].role == "teacher"
        assert messages[0].content == "What is the moon?"
        assert messages[1].role == "student"
        assert messages[1].content == "Student says hello"

    async def test_calls_student_bot_with_history(self):
        """Should pass conversation history to StudentBot."""
        mgr, mock_student, _, _ = self._setup_manager()

        history = [
            {"role": "teacher", "content": "Q1"},
            {"role": "student", "content": "A1"},
        ]
        mgr._get_conversation_history = AsyncMock(return_value=history)
        mgr._log_api_usage = AsyncMock()

        await mgr.process_teacher_message("Q2")

        mock_student.generate_response.assert_called_once_with("Q2", history)

    async def test_calls_misconception_analyzer(self):
        """Should analyze student response for misconceptions."""
        mgr, _, _, mock_analyzer = self._setup_manager()
        mgr._get_conversation_history = AsyncMock(return_value=[])
        mgr._log_api_usage = AsyncMock()

        await mgr.process_teacher_message("Test question")

        mock_analyzer.analyze_student_response.assert_called_once_with(
            student_message="Student says hello",
            scenario_prompt="Moon is a light source",
            student_profile="Grade 5 student",
            scenario_title="Moon Phases",
        )

    async def test_stores_misconception_metadata_on_student_msg(self):
        """Should store analysis as JSON metadata on student msg."""
        mgr, _, _, _ = self._setup_manager()
        mgr._get_conversation_history = AsyncMock(return_value=[])
        mgr._log_api_usage = AsyncMock()

        messages = await mgr.process_teacher_message("Q?")

        student_msg = messages[1]
        assert student_msg.analysis_metadata is not None
        metadata = json.loads(student_msg.analysis_metadata)
        assert metadata["maintains_misconception"] is True
        assert metadata["misconception_strength"] == 0.8

    async def test_tutor_feedback_included_when_enabled(self):
        """Should include tutor message when TutorBot is active."""
        mgr, _, mock_tutor, _ = self._setup_manager(
            tutor_enabled=True, tutor_template_id=2
        )
        mgr._get_conversation_history = AsyncMock(return_value=[])
        mgr._log_api_usage = AsyncMock()

        messages = await mgr.process_teacher_message("Q?")

        # teacher + student + tutor
        assert len(messages) == 3
        assert messages[2].role == "tutor"
        assert messages[2].content == "Tutor feedback here"

    async def test_no_tutor_message_when_disabled(self):
        """Should not include tutor message when TutorBot is off."""
        mgr, _, _, _ = self._setup_manager(tutor_enabled=False)
        mgr._get_conversation_history = AsyncMock(return_value=[])
        mgr._log_api_usage = AsyncMock()

        messages = await mgr.process_teacher_message("Q?")

        # teacher + student only
        assert len(messages) == 2

    async def test_no_tutor_message_when_feedback_is_none(self):
        """Should skip tutor msg when generate_feedback returns None."""
        mgr, _, mock_tutor, _ = self._setup_manager(
            tutor_enabled=True, tutor_template_id=2
        )
        mock_tutor.generate_feedback = AsyncMock(return_value=(None, None))
        mgr._get_conversation_history = AsyncMock(return_value=[])
        mgr._log_api_usage = AsyncMock()

        messages = await mgr.process_teacher_message("Q?")

        # teacher + student only (tutor chose not to intervene)
        assert len(messages) == 2

    async def test_graceful_handling_when_analyzer_fails(self):
        """Should continue when MisconceptionAnalyzer raises."""
        mgr, _, _, mock_analyzer = self._setup_manager()
        mock_analyzer.analyze_student_response = AsyncMock(
            side_effect=RuntimeError("Analysis failed")
        )
        mgr._get_conversation_history = AsyncMock(return_value=[])
        mgr._log_api_usage = AsyncMock()

        # Should NOT raise
        messages = await mgr.process_teacher_message("Q?")

        # Still returns teacher + student
        assert len(messages) == 2
        # Student message should have no metadata
        assert messages[1].analysis_metadata is None

    async def test_graceful_handling_when_tutor_fails(self):
        """Should continue when TutorBot raises exception."""
        mgr, _, mock_tutor, _ = self._setup_manager(
            tutor_enabled=True, tutor_template_id=2
        )
        mock_tutor.generate_feedback = AsyncMock(
            side_effect=RuntimeError("Tutor API error")
        )
        mgr._get_conversation_history = AsyncMock(return_value=[])
        mgr._log_api_usage = AsyncMock()

        # Should NOT raise
        messages = await mgr.process_teacher_message("Q?")

        # teacher + student only (tutor failed gracefully)
        assert len(messages) == 2

    async def test_parallel_execution_of_analyzer_and_tutor(self):
        """Should run analyzer and tutor in parallel via gather."""
        mgr, _, mock_tutor, mock_analyzer = self._setup_manager(
            tutor_enabled=True, tutor_template_id=2
        )
        mgr._get_conversation_history = AsyncMock(return_value=[])
        mgr._log_api_usage = AsyncMock()

        with patch(
            "src.services.session_mgr.asyncio.gather",
            new_callable=AsyncMock,
        ) as mock_gather:
            # Simulate gather returning both results
            mock_gather.return_value = [
                {
                    "maintains_misconception": True,
                    "misconception_strength": 0.7,
                },
                (
                    "Tutor says improve",
                    {
                        "prompt_tokens": 50,
                        "completion_tokens": 25,
                        "total_tokens": 75,
                    },
                ),
            ]

            await mgr.process_teacher_message("Q?")

        # gather should be called with return_exceptions=True
        mock_gather.assert_called_once()
        call_kwargs = mock_gather.call_args
        assert call_kwargs.kwargs.get("return_exceptions") is True

    async def test_logs_student_api_usage(self):
        """Should log StudentBot API usage after response."""
        mgr, _, _, _ = self._setup_manager()
        mgr._get_conversation_history = AsyncMock(return_value=[])
        mgr._log_api_usage = AsyncMock()

        await mgr.process_teacher_message("Q?")

        # At least one call for student bot
        mgr._log_api_usage.assert_any_call(
            bot_type="student",
            model="gpt-5",
            usage_dict={
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        )

    async def test_logs_tutor_api_usage_when_intervening(self):
        """Should log TutorBot usage when intervention happens."""
        mgr, _, mock_tutor, _ = self._setup_manager(
            tutor_enabled=True, tutor_template_id=2
        )
        mgr._get_conversation_history = AsyncMock(return_value=[])
        mgr._log_api_usage = AsyncMock()

        await mgr.process_teacher_message("Q?")

        # Should log both student and tutor
        calls = mgr._log_api_usage.call_args_list
        bot_types = [c.kwargs["bot_type"] for c in calls]
        assert "student" in bot_types
        assert "tutor" in bot_types

    async def test_auto_initializes_when_student_bot_none(self):
        """Should call initialize() if student_bot not set."""
        db = _mock_db_session()
        mgr = SessionManager(db_session=db, session_id=1)
        db.execute = AsyncMock(
            return_value=_mock_scalar_result(_mock_session())
        )

        # student_bot is None initially
        assert mgr.student_bot is None

        # Mock initialize to set up bots
        async def mock_init():
            mgr.student_bot = AsyncMock()
            mgr.student_bot.generate_response = AsyncMock(
                return_value=("Response", None)
            )
            mgr.student_bot.model = "gpt-5"
            mgr.misconception_analyzer = AsyncMock()
            mgr.misconception_analyzer.analyze_student_response = AsyncMock(
                return_value=None
            )
            mgr.tutor_bot = None
            mgr.scenario = _mock_scenario()

        mgr.initialize = AsyncMock(side_effect=mock_init)
        mgr._get_conversation_history = AsyncMock(return_value=[])
        mgr._log_api_usage = AsyncMock()

        await mgr.process_teacher_message("Q?")

        mgr.initialize.assert_called_once()

    async def test_commits_teacher_message_early(self):
        """Teacher 메시지 저장 후 조기 commit이 호출되어야 한다."""
        mgr, _, _, _ = self._setup_manager()
        mgr._get_conversation_history = AsyncMock(return_value=[])
        mgr._log_api_usage = AsyncMock()

        await mgr.process_teacher_message("Q?")

        mgr.db.commit.assert_called_once()


class TestGetConversationHistory:
    """Tests for SessionManager._get_conversation_history."""

    async def test_context_window_limits_messages(self):
        """Should return only last CONTEXT_WINDOW_TURNS."""
        db = _mock_db_session()
        mgr = SessionManager(db_session=db, session_id=1)
        mgr.CONTEXT_WINDOW_TURNS = 20

        mock_messages = []
        for i in range(30):
            msg = Mock()
            msg.role = "teacher" if i % 2 == 0 else "student"
            msg.content = f"Message {i}"
            mock_messages.append(msg)

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_messages
        db.execute = AsyncMock(return_value=mock_result)

        history = await mgr._get_conversation_history()

        assert len(history) == 20
        assert history[0]["content"] == "Message 10"
        assert history[-1]["content"] == "Message 29"

    async def test_returns_all_when_under_limit(self):
        """Should return all messages when under limit."""
        db = _mock_db_session()
        mgr = SessionManager(db_session=db, session_id=1)
        mgr.CONTEXT_WINDOW_TURNS = 20

        mock_messages = []
        for i in range(5):
            msg = Mock()
            msg.role = "teacher"
            msg.content = f"Message {i}"
            mock_messages.append(msg)

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_messages
        db.execute = AsyncMock(return_value=mock_result)

        history = await mgr._get_conversation_history()

        assert len(history) == 5


class TestSessionManagerEndSession:
    """Tests for SessionManager.end_session method."""

    async def test_marks_session_as_ended(self):
        """Should set ended_at timestamp on session."""
        db = _mock_db_session()
        mgr = SessionManager(db_session=db, session_id=1)

        mock_session = _mock_session()
        mock_session.ended_at = None

        # Mock query to return the session
        mock_result = Mock()
        mock_result.scalar_one.return_value = mock_session
        db.execute = AsyncMock(return_value=mock_result)

        await mgr.end_session()

        assert mock_session.ended_at is not None
        db.commit.assert_not_called()

    async def test_ended_at_is_utc(self):
        """Should use UTC timezone for ended_at."""
        db = _mock_db_session()
        mgr = SessionManager(db_session=db, session_id=1)

        mock_session = _mock_session()
        mock_session.ended_at = None

        mock_result = Mock()
        mock_result.scalar_one.return_value = mock_session
        db.execute = AsyncMock(return_value=mock_result)

        before = datetime.now(timezone.utc)
        await mgr.end_session()
        after = datetime.now(timezone.utc)

        assert mock_session.ended_at >= before
        assert mock_session.ended_at <= after


class TestSessionManagerLogApiUsage:
    """Tests for SessionManager._log_api_usage method."""

    async def test_logs_usage_with_correct_data(self):
        """Should create ApiUsageLog with correct fields."""
        db = _mock_db_session()
        mgr = SessionManager(db_session=db, session_id=42)
        db.execute = AsyncMock(
            return_value=_mock_scalar_result(_mock_session(session_id=42))
        )

        usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }

        with patch(
            "src.services.session_mgr.calculate_cost",
            return_value=0.001234,
        ):
            await mgr._log_api_usage(
                bot_type="student",
                model="gpt-5",
                usage_dict=usage,
            )

        # Should have added an entry to db
        db.add.assert_called_once()
        log_entry = db.add.call_args[0][0]
        assert log_entry.session_id == 42
        assert log_entry.bot_type == "student"
        assert log_entry.model == "gpt-5"
        assert log_entry.prompt_tokens == 100
        assert log_entry.completion_tokens == 50
        assert log_entry.total_tokens == 150
        assert log_entry.estimated_cost_usd == 0.001234
        db.flush.assert_called_once()

    async def test_skips_logging_when_usage_is_none(self):
        """Should skip logging when no usage info available."""
        db = _mock_db_session()
        mgr = SessionManager(db_session=db, session_id=1)

        await mgr._log_api_usage(
            bot_type="student",
            model="gpt-5",
            usage_dict=None,
        )

        db.add.assert_not_called()

    async def test_does_not_fail_on_logging_error(self):
        """Should swallow exceptions during logging."""
        db = _mock_db_session()
        db.add.side_effect = RuntimeError("DB error")
        mgr = SessionManager(db_session=db, session_id=1)
        db.execute = AsyncMock(
            return_value=_mock_scalar_result(_mock_session())
        )

        usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }

        with patch(
            "src.services.session_mgr.calculate_cost",
            return_value=0.001,
        ):
            # Should NOT raise
            await mgr._log_api_usage(
                bot_type="student",
                model="gpt-5",
                usage_dict=usage,
            )


class TestSessionManagerInitialize:
    """Tests for SessionManager.initialize method."""

    async def test_initializes_student_bot(self):
        """Should create StudentBot from session/scenario data."""
        db = _mock_db_session()
        mgr = SessionManager(db_session=db, session_id=1)

        mock_session = _mock_session()
        mock_scenario = _mock_scenario(student_template_id=1)

        # First query returns session, second returns scenario
        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            result = _mock_scalar_result(
                mock_session if call_count == 1 else mock_scenario
            )
            return result

        db.execute = mock_execute

        with (
            patch("src.services.session_mgr.StudentBot") as mock_sbot_cls,
            patch("src.services.session_mgr.MisconceptionAnalyzer"),
        ):
            await mgr.initialize()

        mock_sbot_cls.assert_called_once()
        assert mgr.scenario == mock_scenario

    async def test_initializes_tutor_when_enabled(self):
        """Should create TutorBot when scenario has tutor template."""
        db = _mock_db_session()
        mgr = SessionManager(db_session=db, session_id=1)

        mock_session = _mock_session()
        mock_scenario = _mock_scenario(
            tutor_template_id=2,
            student_template_id=1,
        )

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            result = _mock_scalar_result(
                mock_session if call_count == 1 else mock_scenario
            )
            return result

        db.execute = mock_execute

        with (
            patch("src.services.session_mgr.StudentBot"),
            patch("src.services.session_mgr.TutorBot") as mock_tbot_cls,
            patch("src.services.session_mgr.MisconceptionAnalyzer"),
        ):
            await mgr.initialize()

        mock_tbot_cls.assert_called_once()

    async def test_no_tutor_when_disabled(self):
        """Should not create TutorBot when tutor_template_id is None."""
        db = _mock_db_session()
        mgr = SessionManager(db_session=db, session_id=1)

        mock_session = _mock_session()
        mock_scenario = _mock_scenario(
            tutor_template_id=None,
            student_template_id=1,
        )

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            result = _mock_scalar_result(
                mock_session if call_count == 1 else mock_scenario
            )
            return result

        db.execute = mock_execute

        with (
            patch("src.services.session_mgr.StudentBot"),
            patch("src.services.session_mgr.TutorBot") as mock_tbot_cls,
            patch("src.services.session_mgr.MisconceptionAnalyzer"),
        ):
            await mgr.initialize()

        mock_tbot_cls.assert_not_called()
        assert mgr.tutor_bot is None

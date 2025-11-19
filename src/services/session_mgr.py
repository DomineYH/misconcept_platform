"""SessionManager service for orchestrating dialogue flow."""

import json
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import config
from src.models import ApiUsageLog, Message, Scenario, Session, calculate_cost
from src.services.misconception_analyzer import MisconceptionAnalyzer
from src.services.student_bot import StudentBot
from src.services.tutor_bot import TutorBot

logger = logging.getLogger(__name__)


class SessionManager:
    """Orchestrates teacher-student-tutor dialogue interactions."""

    def __init__(self, db_session: AsyncSession, session_id: int):
        """Initialize SessionManager for specific session.

        Args:
            db_session: Database session
            session_id: Dialogue session ID
        """
        self.db = db_session
        self.session_id = session_id
        self.student_bot = None
        self.tutor_bot = None  # Initialized conditionally in initialize()
        self.misconception_analyzer = None  # Initialized in initialize()
        self.scenario = None  # Store scenario for analyzer

    async def initialize(self) -> None:
        """Load session and initialize StudentBot with scenario."""
        # Load session and scenario
        result = await self.db.execute(
            select(Session).where(Session.id == self.session_id)
        )
        session = result.scalar_one()

        result = await self.db.execute(
            select(Scenario).where(Scenario.id == session.scenario_id)
        )
        scenario = result.scalar_one()
        self.scenario = scenario  # Store for misconception analysis

        # Load bot configuration from .env and scenario overrides
        bot_config = self._load_bot_config(scenario)

        # Initialize StudentBot with scenario context and configuration
        self.student_bot = StudentBot(
            scenario_prompt=scenario.prompt,
            scenario_title=scenario.title,
            student_profile=scenario.student_profile or "Grade 5 student",
            db_session=self.db,
            model=bot_config["student_model"],
            temperature=bot_config["student_temperature"],
            max_tokens=bot_config["student_max_tokens"],
        )

        # Conditionally initialize TutorBot based on scenario setting
        if bot_config["tutor_enabled"]:
            self.tutor_bot = TutorBot(
                db_session=self.db,
                scenario_title=scenario.title,
                prompt=scenario.prompt,
                student_profile=scenario.student_profile or "Grade 5 student",
                model=bot_config["tutor_model"],
                temperature=bot_config["tutor_temperature"],
                max_tokens=bot_config["tutor_max_tokens"],
                intervention_threshold=bot_config[
                    "tutor_intervention_threshold"
                ],
            )
        else:
            self.tutor_bot = None  # TutorBot disabled for this scenario

        # Initialize MisconceptionAnalyzer for tracking student responses
        self.misconception_analyzer = MisconceptionAnalyzer(
            db_session=self.db,
            model=config.ANALYSIS_MODEL,  # Use analysis model
            temperature=0.3,  # Low temperature for consistent analysis
        )

    async def process_teacher_message(
        self, teacher_content: str
    ) -> list[Message]:
        """Process teacher message and generate bot responses.

        Args:
            teacher_content: Teacher's question/message

        Returns:
            List of new Message objects (teacher, student, optional tutor)
        """
        if not self.student_bot:
            await self.initialize()

        new_messages = []

        # 1. Load conversation history (before saving teacher message)
        history = await self._get_conversation_history()

        # 2. Save teacher message
        teacher_msg = Message(
            session_id=self.session_id,
            role="teacher",
            content=teacher_content,
        )
        self.db.add(teacher_msg)
        await self.db.flush()  # Get ID without commit
        new_messages.append(teacher_msg)

        # 3. Generate student response
        (
            student_content,
            student_usage,
        ) = await self.student_bot.generate_response(teacher_content, history)

        # 3.1. Analyze misconception adherence in student response
        misconception_data = None
        try:
            misconception_analysis = (
                await self.misconception_analyzer.analyze_student_response(
                    student_message=student_content,
                    scenario_prompt=self.scenario.prompt,
                    student_profile=self.scenario.student_profile
                    or "Grade 5 student",
                    scenario_title=self.scenario.title,
                )
            )
            misconception_data = json.dumps(misconception_analysis)
        except Exception as e:
            logger.warning(f"Misconception analysis failed: {e}")
            # Continue without analysis data

        # 3.2. Save student message with metadata
        student_msg = Message(
            session_id=self.session_id,
            role="student",
            content=student_content,
            analysis_metadata=misconception_data,  # Store analysis result
        )
        self.db.add(student_msg)
        await self.db.flush()
        new_messages.append(student_msg)

        # Log StudentBot API usage
        await self._log_api_usage(
            bot_type="student",
            model=self.student_bot.model,
            usage_dict=student_usage,
        )

        # 4. Check if tutor should intervene (only if enabled)
        if self.tutor_bot:
            (
                tutor_feedback,
                tutor_usage,
            ) = await self.tutor_bot.generate_feedback(
                teacher_content, student_content, history
            )

            if tutor_feedback:
                tutor_msg = Message(
                    session_id=self.session_id,
                    role="tutor",
                    content=tutor_feedback,
                )
                self.db.add(tutor_msg)
                await self.db.flush()
                new_messages.append(tutor_msg)

                # Log TutorBot API usage (only if intervention occurred)
                await self._log_api_usage(
                    bot_type="tutor",
                    model=self.tutor_bot.model,
                    usage_dict=tutor_usage,
                )

        # 5. Commit all messages
        await self.db.commit()

        # Refresh to get created_at timestamps
        for msg in new_messages:
            await self.db.refresh(msg)

        return new_messages

    def _load_bot_config(self, scenario: Scenario) -> dict:
        """Load bot config from .env and scenario overrides.

        Configuration priority:
        1. Scenario-specific overrides (if set)
        2. Environment variables (.env)
        3. Hardcoded defaults

        Note: Database-based global config removed.
              All defaults now managed via .env.

        Args:
            scenario: Scenario model with optional bot config overrides

        Returns:
            Dictionary with complete bot configuration parameters
        """
        return {
            # StudentBot configuration
            "student_model": (
                scenario.chat_model  # Scenario override
                or config.CHAT_MODEL  # .env fallback
                or "gpt-4-turbo"  # Default
            ),
            "student_temperature": (
                scenario.chat_temperature
                if scenario.chat_temperature is not None
                else getattr(config, "STUDENT_TEMPERATURE", 0.7)
            ),
            "student_max_tokens": getattr(config, "STUDENT_MAX_TOKENS", 150),
            # TutorBot configuration
            "tutor_enabled": scenario.tutor_enabled,
            "tutor_model": config.ANALYSIS_MODEL or "gpt-3.5-turbo",
            "tutor_temperature": getattr(config, "TUTOR_TEMPERATURE", 0.3),
            "tutor_max_tokens": getattr(config, "TUTOR_MAX_TOKENS", 100),
            "tutor_intervention_threshold": (
                scenario.tutor_intervention_threshold
                if scenario.tutor_intervention_threshold is not None
                else getattr(config, "TUTOR_INTERVENTION_THRESHOLD", 3)
            ),
        }

    async def _get_conversation_history(self) -> list[dict]:
        """Retrieve conversation history for context.

        Returns:
            List of message dicts with role and content
        """
        result = await self.db.execute(
            select(Message)
            .where(Message.session_id == self.session_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

        return [{"role": msg.role, "content": msg.content} for msg in messages]

    async def _log_api_usage(
        self,
        bot_type: Literal["student", "tutor"],
        model: str,
        usage_dict: Optional[dict],
    ) -> None:
        """Log OpenAI API usage to database.

        Args:
            bot_type: Type of bot ('student' or 'tutor')
            model: OpenAI model name used
            usage_dict: Dictionary with prompt_tokens, completion_tokens,
                total_tokens. None if no usage info available.
        """
        if usage_dict is None:
            logger.warning(f"No usage info for {bot_type} bot (model: {model})")
            return

        try:
            # Calculate cost using pricing table
            cost = calculate_cost(
                model=model,
                prompt_tokens=usage_dict["prompt_tokens"],
                completion_tokens=usage_dict["completion_tokens"],
            )

            # Create log entry
            log_entry = ApiUsageLog(
                session_id=self.session_id,
                bot_type=bot_type,
                model=model,
                prompt_tokens=usage_dict["prompt_tokens"],
                completion_tokens=usage_dict["completion_tokens"],
                total_tokens=usage_dict["total_tokens"],
                estimated_cost_usd=cost,
            )

            self.db.add(log_entry)
            await self.db.flush()  # Persist immediately

            logger.debug(
                f"API usage logged: {bot_type} bot, "
                f"{usage_dict['total_tokens']} tokens, ${cost:.6f}"
            )

        except Exception as e:
            # Log error but don't fail the entire process
            logger.error(
                f"Failed to log API usage for {bot_type} bot: {str(e)}"
            )

    async def end_session(self) -> None:
        """Mark session as ended."""
        result = await self.db.execute(
            select(Session).where(Session.id == self.session_id)
        )
        session = result.scalar_one()

        session.ended_at = datetime.now(timezone.utc)
        await self.db.commit()


# TODO: Task 3.1.2/3.1.3 - API Usage Logging Tests
# TODO: test_api_usage_logging_student_message
#       - Verify StudentBot API call generates usage log entry
#       - Check prompt_tokens, completion_tokens, total_tokens accuracy
#       - Validate estimated_cost_usd calculation
# TODO: test_api_usage_logging_tutor_intervention
#       - Verify TutorBot API call generates usage log entry (when intervening)
#       - Check bot_type='tutor' correctly logged
#       - Validate model name matches tutor configuration
# TODO: test_api_usage_logging_failure_handling
#       - Verify logging failure doesn't break dialogue flow
#       - Check warning logs when usage info unavailable
#       - Ensure DB rollback doesn't affect message persistence

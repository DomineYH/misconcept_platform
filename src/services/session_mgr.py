"""SessionManager service for orchestrating dialogue flow."""

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import config
from src.models import ApiUsageLog, Message, Scenario, Session, calculate_cost
from src.services.config_cache import bot_config_cache
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

        # Load bot configuration from database (Phase 1: global config)
        bot_config = await self._load_bot_config(scenario)

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
                model=bot_config["tutor_model"],
                temperature=bot_config["tutor_temperature"],
                max_tokens=bot_config["tutor_max_tokens"],
                intervention_threshold=bot_config[
                    "tutor_intervention_threshold"
                ],
            )
        else:
            self.tutor_bot = None  # TutorBot disabled for this scenario

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

        # 1. Save teacher message
        teacher_msg = Message(
            session_id=self.session_id,
            role="teacher",
            content=teacher_content,
        )
        self.db.add(teacher_msg)
        await self.db.flush()  # Get ID without commit
        new_messages.append(teacher_msg)

        # 2. Load conversation history
        history = await self._get_conversation_history()

        # 3. Generate student response
        (
            student_content,
            student_usage,
        ) = await self.student_bot.generate_response(teacher_content, history)
        student_msg = Message(
            session_id=self.session_id,
            role="student",
            content=student_content,
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

    async def _load_bot_config(self, scenario: Scenario) -> dict:
        """Load bot config: Scenario > Global > Env > Default.

        Configuration priority:
        1. Scenario-specific overrides (highest priority)
        2. Global chatbot_config table
        3. Environment variables (fallback)
        4. Hardcoded defaults

        Args:
            scenario: Scenario model with optional bot config overrides

        Returns:
            Dictionary with complete bot configuration parameters
        """
        # Load global config from database using cache (<10ms)
        db_config = await bot_config_cache.get_global_config(self.db)

        # Apply scenario-specific overrides with proper priority
        return {
            # StudentBot configuration
            "student_model": (
                scenario.chat_model  # Priority 1: Scenario override
                or db_config.get("student_bot.model")  # Priority 2: Global DB
                or config.CHAT_MODEL  # Priority 3: Env variable
            ),
            "student_temperature": (
                scenario.chat_temperature  # Scenario override (can be 0.0)
                if scenario.chat_temperature is not None
                else float(db_config.get("student_bot.temperature", "0.7"))
            ),
            "student_max_tokens": int(
                db_config.get("student_bot.max_tokens", "150")
            ),
            # TutorBot configuration
            "tutor_enabled": scenario.tutor_enabled,  # NOT NULL
            "tutor_model": db_config.get(
                "tutor_bot.model", config.ANALYSIS_MODEL
            ),
            "tutor_temperature": float(
                db_config.get("tutor_bot.temperature", "0.3")
            ),
            "tutor_max_tokens": int(
                db_config.get("tutor_bot.max_tokens", "100")
            ),
            "tutor_intervention_threshold": (
                scenario.tutor_intervention_threshold  # Scenario override
                if scenario.tutor_intervention_threshold is not None
                else int(db_config.get("tutor_bot.intervention_threshold", "3"))
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

"""SessionManager service for orchestrating dialogue flow."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import config
from src.models import Message, Scenario, Session, calculate_cost
from src.services.misconception_analyzer import MisconceptionAnalyzer
from src.services.session_lifecycle import (
    ensure_session_writable,
    flush_with_stale_session_check,
)
from src.services.session_usage import log_api_usage
from src.services.student_bot import StudentBot
from src.services.tutor_bot import TutorBot

logger = logging.getLogger(__name__)


class SessionManager:
    """Orchestrates teacher-student-tutor dialogue interactions."""

    CONTEXT_WINDOW_TURNS: int = config.CONTEXT_WINDOW_TURNS

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
        session = await ensure_session_writable(self.db, self.session_id)
        tutor_intervention_count = session.tutor_intervention_count
        tutor_question_count = session.tutor_question_count

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
            template_id=scenario.student_template_id,
            model=bot_config["student_model"],
            reasoning_effort=bot_config["student_reasoning"],
            max_tokens=bot_config["student_max_tokens"],
        )

        # Conditionally initialize TutorBot based on scenario setting
        if bot_config["tutor_enabled"] and scenario.tutor_template_id:
            self.tutor_bot = TutorBot(
                db_session=self.db,
                template_id=scenario.tutor_template_id,
                scenario_title=scenario.title,
                prompt=scenario.prompt,
                student_profile=scenario.student_profile or "Grade 5 student",
                model=bot_config["tutor_model"],
                reasoning_effort=bot_config["tutor_reasoning"],
                max_tokens=bot_config["tutor_max_tokens"],
                intervention_threshold=bot_config[
                    "tutor_intervention_threshold"
                ],
                initial_intervention_count=tutor_intervention_count,
                initial_question_count=tutor_question_count,
                sensitivity=bot_config["tutor_sensitivity"],
            )
        else:
            self.tutor_bot = None  # TutorBot disabled for this scenario

        # Initialize MisconceptionAnalyzer for tracking student responses
        self.misconception_analyzer = MisconceptionAnalyzer(
            db_session=self.db,
            model=config.ANALYSIS_MODEL,
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
        await ensure_session_writable(self.db, self.session_id)
        teacher_msg = Message(
            session_id=self.session_id,
            role="teacher",
            content=teacher_content,
        )
        self.db.add(teacher_msg)
        await flush_with_stale_session_check(self.db, self.session_id)
        await self.db.commit()  # Teacher 메시지 즉시 가시화
        new_messages.append(teacher_msg)

        # 3. Generate student response (must be sequential - needed by others)
        (
            student_content,
            student_usage,
        ) = await self.student_bot.generate_response(teacher_content, history)

        # 3.1. Run MisconceptionAnalyzer and TutorBot in PARALLEL
        # Both depend on student_content but NOT on each other
        # Performance: saves ~2 seconds by avoiding sequential API calls
        analysis_coro = self.misconception_analyzer.analyze_student_response(
            student_message=student_content,
            scenario_prompt=self.scenario.prompt,
            student_profile=self.scenario.student_profile or "Grade 5 student",
            scenario_title=self.scenario.title,
        )

        parallel_tasks: list = [analysis_coro]
        tutor_task_idx: int | None = None
        if self.tutor_bot:
            parallel_tasks.append(
                self.tutor_bot.generate_feedback(
                    teacher_content, student_content, history
                )
            )
            tutor_task_idx = 1

        results = await asyncio.gather(*parallel_tasks, return_exceptions=True)

        misconception_data = None
        if not isinstance(results[0], Exception) and results[0] is not None:
            misconception_data = json.dumps(results[0])
        elif isinstance(results[0], Exception):
            logger.warning("Misconception analysis failed: %s", results[0])

        # 3.2. Save student message with metadata
        await ensure_session_writable(self.db, self.session_id)
        student_msg = Message(
            session_id=self.session_id,
            role="student",
            content=student_content,
            analysis_metadata=misconception_data,
        )
        self.db.add(student_msg)
        await flush_with_stale_session_check(self.db, self.session_id)
        new_messages.append(student_msg)

        # Log StudentBot API usage
        await self._log_api_usage(
            bot_type="student",
            model=self.student_bot.model,
            usage_dict=student_usage,
        )

        # 4. Process TutorBot result (from parallel execution)
        if tutor_task_idx is not None:
            tutor_result = results[tutor_task_idx]
            if not isinstance(tutor_result, Exception):
                tutor_feedback, tutor_usage = tutor_result
                if tutor_feedback:
                    await ensure_session_writable(self.db, self.session_id)
                    tutor_msg = Message(
                        session_id=self.session_id,
                        role="tutor",
                        content=tutor_feedback,
                    )
                    self.db.add(tutor_msg)
                    await flush_with_stale_session_check(
                        self.db, self.session_id
                    )
                    new_messages.append(tutor_msg)

                    # Log TutorBot API usage (only if intervention occurred)
                    await self._log_api_usage(
                        bot_type="tutor",
                        model=self.tutor_bot.model,
                        usage_dict=tutor_usage,
                    )
            else:
                logger.warning("TutorBot feedback failed: %s", tutor_result)

        # 5. Refresh to get created_at timestamps (dependency auto-commits)
        for msg in new_messages:
            await ensure_session_writable(self.db, self.session_id)
            await self.db.refresh(msg)

        # Persist TutorBot state to session
        if self.tutor_bot:
            sess = await ensure_session_writable(self.db, self.session_id)
            sess.tutor_intervention_count = self.tutor_bot.intervention_count
            sess.tutor_question_count = self.tutor_bot.question_count
            await flush_with_stale_session_check(self.db, self.session_id)

        return new_messages

    def _load_bot_config(self, scenario: Scenario) -> dict:
        """Load bot config from .env and scenario overrides.

        Configuration priority:
        1. Scenario-specific overrides (if set)
        2. Environment variables (.env)
        3. Hardcoded defaults

        Note: Temperature is not supported for GPT-5 Responses API.
              Use reasoning_effort (minimal/low/medium/high) instead.

        Args:
            scenario: Scenario model with optional bot config overrides

        Returns:
            Dictionary with complete bot configuration parameters:
            - student_model, student_reasoning, student_max_tokens
            - tutor_model, tutor_reasoning, tutor_max_tokens
            - tutor_enabled, tutor_intervention_threshold
        """
        return {
            # StudentBot configuration
            "student_model": (scenario.chat_model or config.CHAT_MODEL),
            "student_reasoning": config.STUDENT_REASONING or "medium",
            "student_max_tokens": config.STUDENT_MAX_TOKENS or 750,
            # TutorBot configuration
            "tutor_enabled": scenario.tutor_enabled,
            "tutor_model": config.ANALYSIS_MODEL,
            "tutor_reasoning": config.TUTOR_REASONING or "low",
            "tutor_max_tokens": config.TUTOR_MAX_TOKENS or 750,
            "tutor_intervention_threshold": (
                scenario.tutor_intervention_threshold
                if scenario.tutor_intervention_threshold is not None
                else config.TUTOR_INTERVENTION_THRESHOLD or 3
            ),
            "tutor_sensitivity": (
                scenario.tutor_sensitivity
                if hasattr(scenario, "tutor_sensitivity")
                else "medium"
            ),
        }

    async def _get_conversation_history(self) -> list[dict]:
        """Retrieve conversation history for context.

        Returns:
            List of message dicts with role and content.
            Limited to the most recent CONTEXT_WINDOW_TURNS messages.
        """
        result = await self.db.execute(
            select(Message)
            .where(Message.session_id == self.session_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()
        window = self.CONTEXT_WINDOW_TURNS
        recent = messages[-window:]
        return [{"role": msg.role, "content": msg.content} for msg in recent]

    async def _log_api_usage(
        self,
        bot_type: Literal["student", "tutor"],
        model: str,
        usage_dict: Optional[dict],
    ) -> None:
        await log_api_usage(
            db=self.db,
            session_id=self.session_id,
            bot_type=bot_type,
            model=model,
            usage_dict=usage_dict,
            cost_calculator=calculate_cost,
        )

    async def end_session(self) -> None:
        """Mark session as ended."""
        result = await self.db.execute(
            select(Session).where(
                Session.id == self.session_id, Session.deleted_at.is_(None)
            )
        )
        session = result.scalar_one()

        session.ended_at = datetime.now(timezone.utc)
        # Dependency auto-commits

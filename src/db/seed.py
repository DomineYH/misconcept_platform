"""Database seeding script with default data."""

import asyncio
import json
import os
from pathlib import Path

import bcrypt
from sqlalchemy import text

from src.db.connection import AsyncSessionLocal
from src.db.init_schema import init_schema


async def seed_database():
    """Populate database with default data."""
    # First ensure schema exists
    await init_schema()

    async with AsyncSessionLocal() as session:
        # Check if data already exists
        result = await session.execute(
            text("SELECT COUNT(*) FROM analysis_framework")
        )
        count = result.scalar()

        if count > 0:
            print("Database already seeded, skipping")
            return

        # Seed default user group
        await session.execute(
            text(
                """
                INSERT INTO user_group (name, description)
                VALUES (:name, :desc)
                """
            ),
            {
                "name": "default",
                "desc": "기본 그룹",
            },
        )

        # Get default group id
        group_result = await session.execute(
            text(
                "SELECT id FROM user_group "
                "WHERE name = 'default'"
            )
        )
        default_group_id = group_result.scalar()

        # Seed default analysis framework
        framework_labels = json.dumps(
            ["Pressing", "Linking", "Directing", "Recall"]
        )

        await session.execute(
            text(
                """
                INSERT INTO analysis_framework
                (name, description, labels_json)
                VALUES (:name, :desc, :labels)
                """
            ),
            {
                "name": "High/Low Leverage",
                "desc": (
                    "Pedagogical move classification framework "
                    "distinguishing high-leverage (Pressing, "
                    "Linking) from low-leverage (Directing, "
                    "Recall) questions"
                ),
                "labels": framework_labels,
            },
        )

        # Seed admin user with bcrypt password
        admin_password = os.getenv(
            "ADMIN_DEFAULT_PASSWORD", "admin123"
        )
        admin_hash = bcrypt.hashpw(
            admin_password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

        await session.execute(
            text(
                """
                INSERT INTO user
                (username, nickname, password_hash,
                 role, group_id)
                VALUES (:username, :nickname, :pw_hash,
                        :role, :group_id)
                """
            ),
            {
                "username": "admin",
                "nickname": "Administrator",
                "pw_hash": admin_hash,
                "role": "admin",
                "group_id": default_group_id,
            },
        )

        # Get framework_id and admin user_id
        framework_result = await session.execute(
            text(
                "SELECT id FROM analysis_framework "
                "WHERE name = :name"
            ),
            {"name": "High/Low Leverage"},
        )
        framework_id = framework_result.scalar()

        admin_result = await session.execute(
            text(
                "SELECT id FROM user "
                "WHERE username = :username"
            ),
            {"username": "admin"},
        )
        admin_id = admin_result.scalar()

        # Seed prompt templates (before scenario)
        student_template_id = await _seed_prompt_templates(
            session, admin_id
        )

        # Seed sample scenario with student_template_id
        await session.execute(
            text(
                """
                INSERT INTO scenario (
                    title, prompt, student_profile,
                    is_active, framework_id, created_by,
                    student_template_id,
                    chat_model, chat_temperature,
                    tutor_intervention_threshold
                )
                VALUES (
                    :title, :prompt, :profile,
                    :active, :fid, :created,
                    :student_tid,
                    :chat_model, :chat_temp,
                    :tutor_threshold
                )
                """
            ),
            {
                "title": "Fraction Addition Misconception",
                "prompt": (
                    "You are a 5th grade student who believes "
                    "that when adding fractions, you add both "
                    "numerators and denominators directly "
                    "(e.g., 1/2 + 1/3 = 2/5). "
                    "You are working on the problem: "
                    "What is 1/4 + 1/2?"
                ),
                "profile": (
                    "Grade 5 student, strong in whole number "
                    "arithmetic but struggles with fraction "
                    "concepts"
                ),
                "active": 1,
                "fid": framework_id,
                "created": admin_id,
                "student_tid": student_template_id,
                "chat_model": None,
                "chat_temp": None,
                "tutor_threshold": None,
            },
        )

        # Seed default chatbot configuration
        chatbot_configs = [
            {
                "key": "student_bot.model",
                "value": "gpt-5-mini",
                "type": "string",
                "desc": "StudentBot LLM model",
            },
            {
                "key": "student_bot.temperature",
                "value": "0.7",
                "type": "float",
                "desc": "StudentBot response creativity",
            },
            {
                "key": "student_bot.max_tokens",
                "value": "150",
                "type": "int",
                "desc": "StudentBot response length limit",
            },
            {
                "key": "tutor_bot.model",
                "value": "gpt-5-mini",
                "type": "string",
                "desc": "TutorBot LLM model",
            },
            {
                "key": "tutor_bot.temperature",
                "value": "0.3",
                "type": "float",
                "desc": "TutorBot response consistency",
            },
            {
                "key": "tutor_bot.max_tokens",
                "value": "100",
                "type": "int",
                "desc": "TutorBot response length limit",
            },
            {
                "key": "tutor_bot.intervention_threshold",
                "value": "3",
                "type": "int",
                "desc": "Interventions per 10 questions",
            },
        ]

        for cfg in chatbot_configs:
            await session.execute(
                text(
                    """
                    INSERT INTO chatbot_config
                    (config_key, config_value,
                     config_type, description)
                    VALUES (:key, :value, :type, :desc)
                    """
                ),
                cfg,
            )

        await session.commit()
        print("Database seeded with default data successfully")


async def _seed_prompt_templates(session, admin_id):
    """Seed prompt templates, return student template id."""
    prompts_dir = Path(__file__).parent.parent / "prompts"

    # Load StudentBot prompt
    student_path = prompts_dir / "student_system.txt"
    if student_path.exists():
        student_text = student_path.read_text(encoding="utf-8")
    else:
        print(f"Warning: {student_path} not found")
        student_text = (
            "당신은 오개념을 가진 학생입니다. "
            "(기본 폴백 프롬프트)"
        )

    await session.execute(
        text(
            """
            INSERT INTO prompt_template
            (bot_type, template_name, template_text,
             version, updated_by)
            VALUES (:bot_type, :name, :text,
                    :version, :updated_by)
            """
        ),
        {
            "bot_type": "student",
            "name": "Default",
            "text": student_text,
            "version": 1,
            "updated_by": admin_id,
        },
    )

    # Get student template id
    result = await session.execute(
        text(
            "SELECT id FROM prompt_template "
            "WHERE bot_type = 'student' AND "
            "template_name = 'Default'"
        )
    )
    student_template_id = result.scalar()

    # Load TutorBot prompt
    tutor_path = prompts_dir / "tutor_system.txt"
    if tutor_path.exists():
        tutor_text = tutor_path.read_text(encoding="utf-8")
    else:
        print(f"Warning: {tutor_path} not found")
        tutor_text = (
            "당신은 교수법 피드백을 제공하는 튜터입니다. "
            "(기본 폴백 프롬프트)"
        )

    await session.execute(
        text(
            """
            INSERT INTO prompt_template
            (bot_type, template_name, template_text,
             version, updated_by)
            VALUES (:bot_type, :name, :text,
                    :version, :updated_by)
            """
        ),
        {
            "bot_type": "tutor",
            "name": "Default",
            "text": tutor_text,
            "version": 1,
            "updated_by": admin_id,
        },
    )

    print(f"  - StudentBot prompt: {len(student_text)} chars")
    print(f"  - TutorBot prompt: {len(tutor_text)} chars")

    return student_template_id


async def seed_prompts():
    """Migrate prompt files to DB (legacy, now in seed_database)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM prompt_template")
        )
        count = result.scalar()

        if count > 0:
            print("Prompt templates already seeded, skipping")
            return

        admin_result = await session.execute(
            text(
                "SELECT id FROM user "
                "WHERE role = 'admin' LIMIT 1"
            )
        )
        admin_id = admin_result.scalar()
        await _seed_prompt_templates(session, admin_id)
        await session.commit()
        print("Prompt templates seeded successfully")


if __name__ == "__main__":
    asyncio.run(seed_database())
    asyncio.run(seed_prompts())

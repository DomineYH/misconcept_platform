"""Database seeding script with default data."""

import asyncio
import json
from sqlalchemy import select, text

from src.db.connection import AsyncSessionLocal
from src.db.init_schema import init_schema


async def seed_database():
    """Populate database with default framework, admin, and sample."""
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

        # Seed default analysis framework
        framework_labels = json.dumps([
            "Pressing",
            "Linking",
            "Directing",
            "Recall"
        ])

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
                    "distinguishing high-leverage (Pressing, Linking) "
                    "from low-leverage (Directing, Recall) questions"
                ),
                "labels": framework_labels,
            },
        )

        # Seed admin user
        await session.execute(
            text(
                """
                INSERT INTO user
                (student_uid, nickname, role)
                VALUES (:uid, :nickname, :role)
                """
            ),
            {
                "uid": "admin",
                "nickname": "Administrator",
                "role": "admin",
            },
        )

        # Get framework_id and admin user_id for sample scenario
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
                "SELECT id FROM user WHERE student_uid = :uid"
            ),
            {"uid": "admin"},
        )
        admin_id = admin_result.scalar()

        # Seed sample scenario
        await session.execute(
            text(
                """
                INSERT INTO scenario (
                    title, prompt, student_profile,
                    is_active, framework_id, created_by
                )
                VALUES (:title, :prompt, :profile,
                        :active, :fid, :created)
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
            },
        )

        await session.commit()
        print("Database seeded with default data successfully")


if __name__ == "__main__":
    asyncio.run(seed_database())

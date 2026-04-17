import asyncio
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault(
    "SESSION_SECRET",
    "0123456789abcdef0123456789abcdef",
)
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite+aiosqlite:////tmp/misconcept_platform_admin_test.db",
)

from fastapi.testclient import TestClient
from sqlalchemy import select

import src.models  # noqa: F401
from src.api.dependencies import get_admin_user
from src.db.connection import AsyncSessionLocal, Base, engine
from src.main import app
from src.models.analysis_framework import AnalysisFramework
from src.models.prompt_template import PromptTemplate
from src.models.scenario import Scenario
from src.models.session import Session


def override_admin_user():
    return SimpleNamespace(id=999, is_admin=True)


async def reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_scenario() -> dict[str, int]:
    async with AsyncSessionLocal() as session:
        framework = AnalysisFramework(
            name="Test Framework",
            description="Framework for tests",
            labels_json='["A", "B"]',
        )
        student_template = PromptTemplate(
            bot_type="student",
            template_name="Student Default",
            template_text="Student template text",
            version=1,
        )
        tutor_template = PromptTemplate(
            bot_type="tutor",
            template_name="Tutor Default",
            template_text="Tutor template text",
            version=1,
        )
        scenario = Scenario(
            title="Original Title",
            prompt="Original prompt text",
            student_profile="Original student profile",
            framework=framework,
            student_template=student_template,
            tutor_template=tutor_template,
            is_active=1,
            tutor_sensitivity="medium",
        )
        active_session = Session(scenario=scenario)
        session.add_all(
            [
                framework,
                student_template,
                tutor_template,
                scenario,
                active_session,
            ]
        )
        await session.flush()
        scenario_id = scenario.id
        framework_id = framework.id
        student_template_id = student_template.id
        tutor_template_id = tutor_template.id
        session_id = active_session.id
        await session.commit()
        return {
            "scenario_id": scenario_id,
            "framework_id": framework_id,
            "student_template_id": student_template_id,
            "tutor_template_id": tutor_template_id,
            "session_id": session_id,
        }


async def load_scenario(scenario_id: int) -> Scenario:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Scenario).where(Scenario.id == scenario_id)
        )
        return result.scalar_one()


async def load_session(session_id: int) -> Session:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Session).where(Session.id == session_id)
        )
        return result.scalar_one()


class AdminScenarioHostCompatTest(unittest.TestCase):
    def setUp(self) -> None:
        asyncio.run(reset_db())
        app.dependency_overrides[get_admin_user] = override_admin_user

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_post_update_endpoint_updates_scenario(self) -> None:
        seeded = asyncio.run(seed_scenario())

        with TestClient(app) as client:
            response = client.post(
                f"/admin/scenarios/{seeded['scenario_id']}/update",
                json={
                    "title": "Updated Title",
                    "prompt": "Updated prompt text",
                    "student_profile": "Updated student profile",
                    "framework_id": seeded["framework_id"],
                    "student_template_id": (seeded["student_template_id"]),
                    "tutor_template_id": seeded["tutor_template_id"],
                    "group_ids": [],
                    "problem_situation": "Updated problem situation",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Updated Title")
        self.assertEqual(
            response.json()["problem_situation"],
            "Updated problem situation",
        )

        scenario = asyncio.run(load_scenario(seeded["scenario_id"]))
        self.assertEqual(scenario.title, "Updated Title")
        self.assertEqual(scenario.prompt, "Updated prompt text")
        self.assertEqual(
            scenario.problem_situation, "Updated problem situation"
        )

    def test_post_update_endpoint_updates_problem_situation(
        self,
    ) -> None:
        seeded = asyncio.run(seed_scenario())

        with TestClient(app) as client:
            response = client.post(
                f"/admin/scenarios/{seeded['scenario_id']}/update",
                json={
                    "framework_id": seeded["framework_id"],
                    "student_template_id": (seeded["student_template_id"]),
                    "tutor_template_id": seeded["tutor_template_id"],
                    "group_ids": [],
                    "problem_situation": "New problem situation text",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["problem_situation"],
            "New problem situation text",
        )

        scenario = asyncio.run(load_scenario(seeded["scenario_id"]))
        self.assertEqual(
            scenario.problem_situation, "New problem situation text"
        )

    def test_post_delete_endpoint_soft_deletes_data(self) -> None:
        seeded = asyncio.run(seed_scenario())

        with TestClient(app) as client:
            response = client.post(
                f"/admin/scenarios/{seeded['scenario_id']}/delete"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "deleted")

        scenario = asyncio.run(load_scenario(seeded["scenario_id"]))
        active_session = asyncio.run(load_session(seeded["session_id"]))

        self.assertIsNotNone(scenario.deleted_at)
        self.assertIsNotNone(active_session.deleted_at)

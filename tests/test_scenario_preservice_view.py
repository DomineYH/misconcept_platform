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
    "sqlite+aiosqlite:////tmp/misconcept_platform_preservice_test.db",
)

from fastapi.testclient import TestClient
from sqlalchemy import select

import src.models  # noqa: F401
from src.api.dependencies import get_current_user, get_db_session
from src.db.connection import AsyncSessionLocal, Base, engine
from src.main import app
from src.models.analysis_framework import AnalysisFramework
from src.models.prompt_template import PromptTemplate
from src.models.scenario import Scenario
from src.models.scenario_group import ScenarioGroup
from src.models.session import Session
from src.models.user import User
from src.models.user_group import UserGroup


def override_current_user():
    return SimpleNamespace(
        id=1, role="teacher", group_id=1, is_admin=False
    )


async def reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_preservice_scenario() -> dict:
    async with AsyncSessionLocal() as session:
        group = UserGroup(name="TestGroup", description="test")
        user = User(
            username="teacher1",
            nickname="Teacher One",
            password_hash="hash",
            role="teacher",
            group=group,
        )
        framework = AnalysisFramework(
            name="Preservice Framework",
            description="Framework for preservice test",
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
            title="밀가루 반죽 오개념",
            prompt="SECRET_SYSTEM_PROMPT_SHOULD_NOT_LEAK",
            student_profile="학생 프로필",
            problem_situation=(
                "민수는 밀가루 반죽을 만들고 있습니다..."
            ),
            framework=framework,
            student_template=student_template,
            tutor_template=tutor_template,
            is_active=1,
            tutor_sensitivity="medium",
        )
        sg = ScenarioGroup(scenario=scenario, group=group)
        session.add_all(
            [
                group,
                user,
                framework,
                student_template,
                tutor_template,
                scenario,
                sg,
            ]
        )
        await session.flush()
        scenario_id = scenario.id
        await session.commit()
        return {"scenario_id": scenario_id}


class ScenarioPreserviceViewTest(unittest.TestCase):
    def setUp(self) -> None:
        asyncio.run(reset_db())
        app.dependency_overrides[get_current_user] = (
            override_current_user
        )

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_scenario_list_hides_prompt_shows_problem_situation(
        self,
    ) -> None:
        seeded = asyncio.run(seed_preservice_scenario())

        with TestClient(app) as client:
            response = client.get("/scenarios")

        self.assertEqual(response.status_code, 200)
        body = response.text
        # System prompt must NOT appear
        self.assertNotIn("SECRET_SYSTEM_PROMPT_SHOULD_NOT_LEAK", body)
        # Problem situation snippet must appear
        self.assertIn("민수는 밀가루 반죽을 만들고 있습니다...", body)

    def test_chat_page_hides_prompt_shows_problem_situation(
        self,
    ) -> None:
        seeded = asyncio.run(seed_preservice_scenario())

        with TestClient(app) as client:
            response = client.get(
                f"/scenarios/{seeded['scenario_id']}"
            )

        self.assertEqual(response.status_code, 200)
        body = response.text
        # System prompt must NOT appear
        self.assertNotIn("SECRET_SYSTEM_PROMPT_SHOULD_NOT_LEAK", body)
        # Problem situation must appear in the chat page
        self.assertIn("민수는 밀가루 반죽을 만들고 있습니다...", body)

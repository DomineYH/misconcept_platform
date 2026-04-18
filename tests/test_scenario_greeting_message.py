"""Regression tests for greeting_message feature (issue #12).

Covers all 6 Success Criteria:
  SC1: Admin create + update persists greeting (round-trip)
  SC2: Chat page renders greeting as message-mentor + greeting-message
  SC3: Chat page hides greeting when None or ""
  SC4: Pydantic rejects 5001-char; accepts 5000; HTML maxlength
  SC5: Greeting not in message table; not in bot prompt composition
  SC6: Issue #9 regression (system prompt hidden from preservice view)
"""

import asyncio
import os
import re
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
    "sqlite+aiosqlite:////tmp/misconcept_platform_greeting_test.db",
)

from fastapi.testclient import TestClient
from sqlalchemy import select, text

import src.models  # noqa: F401
from src.api.dependencies import get_admin_user, get_current_user
from src.db.connection import AsyncSessionLocal, Base, engine
from src.main import app
from src.models.analysis_framework import AnalysisFramework
from src.models.prompt_template import PromptTemplate
from src.models.scenario import Scenario
from src.models.scenario_group import ScenarioGroup
from src.models.user import User
from src.models.user_group import UserGroup

# ── Dependency overrides ──────────────────────────────────────


def _override_current_user():
    return SimpleNamespace(id=1, role="teacher", group_id=1, is_admin=False)


def _override_admin_user():
    return SimpleNamespace(id=999, is_admin=True)


# ── Helpers ───────────────────────────────────────────────────


async def reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _seed_admin_scenario(
    greeting_message=None,
) -> dict:
    """Seed scenario for admin CRUD tests (no user/group)."""
    async with AsyncSessionLocal() as session:
        framework = AnalysisFramework(
            name="Greeting Admin FW",
            description="FW for admin greeting tests",
            labels_json='["A", "B"]',
        )
        student_tpl = PromptTemplate(
            bot_type="student",
            template_name="Student Default",
            template_text="{scenario_title} {student_profile} {prompt}",
            version=1,
        )
        tutor_tpl = PromptTemplate(
            bot_type="tutor",
            template_name="Tutor Default",
            template_text="{scenario_title} {student_profile} {prompt}",
            version=1,
        )
        scenario = Scenario(
            title="Admin Greeting Test",
            prompt="System prompt for admin test",
            student_profile="Test student profile",
            greeting_message=greeting_message,
            framework=framework,
            student_template=student_tpl,
            tutor_template=tutor_tpl,
            is_active=1,
            tutor_sensitivity="medium",
        )
        session.add_all([framework, student_tpl, tutor_tpl, scenario])
        await session.flush()
        await session.commit()
        return {
            "scenario_id": scenario.id,
            "framework_id": framework.id,
            "student_template_id": student_tpl.id,
            "tutor_template_id": tutor_tpl.id,
        }


async def _seed_chat_scenario(
    greeting_message="GREETING_IN_CHAT_SENTINEL",
    problem_situation="문제 상황 텍스트입니다",
    prompt="SECRET_SYSTEM_PROMPT_SHOULD_NOT_LEAK",
) -> dict:
    """Seed scenario with user/group for chat-page tests."""
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
            name="Chat Greeting FW",
            description="FW for chat tests",
            labels_json='["A", "B"]',
        )
        student_tpl = PromptTemplate(
            bot_type="student",
            template_name="Student Default",
            template_text="{scenario_title} {student_profile} {prompt}",
            version=1,
        )
        tutor_tpl = PromptTemplate(
            bot_type="tutor",
            template_name="Tutor Default",
            template_text="{scenario_title} {student_profile} {prompt}",
            version=1,
        )
        scenario = Scenario(
            title="채팅 인사말 테스트",
            prompt=prompt,
            student_profile="학생 프로필",
            problem_situation=problem_situation,
            greeting_message=greeting_message,
            framework=framework,
            student_template=student_tpl,
            tutor_template=tutor_tpl,
            is_active=1,
            tutor_sensitivity="medium",
        )
        sg = ScenarioGroup(scenario=scenario, group=group)
        session.add_all(
            [
                group,
                user,
                framework,
                student_tpl,
                tutor_tpl,
                scenario,
                sg,
            ]
        )
        await session.flush()
        await session.commit()
        return {"scenario_id": scenario.id}


async def _load_scenario(scenario_id: int) -> Scenario:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Scenario).where(Scenario.id == scenario_id)
        )
        return result.scalar_one()


async def _count_messages(session_id: int) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM message " "WHERE session_id = :sid"),
            {"sid": session_id},
        )
        return result.scalar_one()


# ── SC1 + SC4: Admin CRUD & validation ────────────────────────


class GreetingMessageAdminTest(unittest.TestCase):
    """Admin CRUD persistence (SC1) and length validation (SC4)."""

    def setUp(self) -> None:
        asyncio.run(reset_db())
        app.dependency_overrides[get_admin_user] = _override_admin_user

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    # SC1 ──────────────────────────────────────────────────────
    def test_admin_create_and_update_persists_greeting(
        self,
    ) -> None:
        seeded = asyncio.run(_seed_admin_scenario())

        with TestClient(app) as client:
            resp = client.post(
                "/admin/scenarios",
                json={
                    "title": "New With Greeting",
                    "prompt": "System prompt for create test",
                    "student_profile": "Student profile text",
                    "greeting_message": "GREETING_SENTINEL_A",
                    "framework_id": seeded["framework_id"],
                    "student_template_id": (seeded["student_template_id"]),
                    "tutor_template_id": (seeded["tutor_template_id"]),
                    "group_ids": [],
                },
            )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(
            resp.json()["greeting_message"],
            "GREETING_SENTINEL_A",
        )
        new_id = resp.json()["id"]

        scenario = asyncio.run(_load_scenario(new_id))
        self.assertEqual(scenario.greeting_message, "GREETING_SENTINEL_A")

        # Update greeting
        with TestClient(app) as client:
            resp = client.post(
                f"/admin/scenarios/{new_id}/update",
                json={"greeting_message": "GREETING_SENTINEL_B"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["greeting_message"],
            "GREETING_SENTINEL_B",
        )

        scenario = asyncio.run(_load_scenario(new_id))
        self.assertEqual(scenario.greeting_message, "GREETING_SENTINEL_B")

    # SC4 ──────────────────────────────────────────────────────
    def test_greeting_exceeds_max_length_rejected(self) -> None:
        seeded = asyncio.run(_seed_admin_scenario())
        with TestClient(app) as client:
            resp = client.post(
                f"/admin/scenarios/{seeded['scenario_id']}/update",
                json={"greeting_message": "x" * 5001},
            )
        self.assertEqual(resp.status_code, 422)
        detail = resp.json().get("detail", [])
        self.assertTrue(
            any(
                "greeting_message" in str(err)
                and (
                    "max_length" in str(err)
                    or "string_too_long" in str(err)
                    or "at most" in str(err)
                )
                for err in detail
            ),
            f"422 must cite greeting_message length; got {detail!r}",
        )

    def test_admin_update_blank_string_clears_greeting(self) -> None:
        """Empty textarea posts `""`; backend strips to None. Without
        this path, admins cannot remove a greeting once set."""
        seeded = asyncio.run(
            _seed_admin_scenario(greeting_message="TO_BE_CLEARED"),
        )
        with TestClient(app) as client:
            resp = client.post(
                f"/admin/scenarios/{seeded['scenario_id']}/update",
                json={"greeting_message": ""},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["greeting_message"])
        scenario = asyncio.run(
            _load_scenario(seeded["scenario_id"]),
        )
        self.assertIsNone(scenario.greeting_message)

    def test_greeting_at_max_length_accepted(self) -> None:
        seeded = asyncio.run(_seed_admin_scenario())
        with TestClient(app) as client:
            resp = client.post(
                f"/admin/scenarios/{seeded['scenario_id']}/update",
                json={"greeting_message": "x" * 5000},
            )
        self.assertEqual(resp.status_code, 200)

    def test_admin_html_maxlength_on_greeting_textareas(
        self,
    ) -> None:
        with open("src/templates/admin/scenarios.html") as f:
            html = f.read()
        self.assertIn('id="new-greeting-message"', html)
        self.assertIn('id="edit-greeting-message"', html)
        self.assertGreaterEqual(
            html.count('maxlength="5000"'),
            4,  # prompt + student_profile + new + edit greeting
        )

    def test_admin_html_wires_greeting_in_js(self) -> None:
        """JS edit round-trip must be wired; template edit without this
        silently loses data. Plain text checks, no DOM required."""
        with open("src/templates/admin/scenarios.html") as f:
            html = f.read()
        # (C) scenariosData object key
        self.assertIn("greeting_message:", html)
        # (D) openEditPanel populates the edit textarea
        self.assertIn("'edit-greeting-message'", html)
        # (E/F) both submit handlers include greeting_message in POST body
        self.assertGreaterEqual(
            html.count("formData.get('greeting_message')"),
            2,  # create form + edit form
        )


# ── SC2, SC3, SC5, SC6: Chat rendering & leak prevention ─────


class GreetingMessageChatTest(unittest.TestCase):
    """Chat rendering (SC2/SC3), leak prevention (SC5), #9 regression (SC6)."""

    def setUp(self) -> None:
        asyncio.run(reset_db())
        app.dependency_overrides[get_current_user] = _override_current_user

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    # SC2 ──────────────────────────────────────────────────────
    def test_chat_renders_greeting_when_set(self) -> None:
        seeded = asyncio.run(
            _seed_chat_scenario(
                greeting_message="GREETING_IN_CHAT_SENTINEL",
            )
        )
        with TestClient(app) as client:
            resp = client.get(f"/scenarios/{seeded['scenario_id']}")
        self.assertEqual(resp.status_code, 200)
        body = resp.text
        self.assertIn("GREETING_IN_CHAT_SENTINEL", body)
        self.assertIn("message-mentor", body)
        self.assertIn("greeting-message", body)

    # SC3 ──────────────────────────────────────────────────────
    def test_chat_hides_greeting_when_none(self) -> None:
        seeded = asyncio.run(_seed_chat_scenario(greeting_message=None))
        with TestClient(app) as client:
            resp = client.get(f"/scenarios/{seeded['scenario_id']}")
        self.assertEqual(resp.status_code, 200)
        body = resp.text
        self.assertNotIn("message-mentor", body)
        self.assertNotIn("greeting-message", body)

    def test_chat_hides_greeting_when_empty_string(self) -> None:
        seeded = asyncio.run(_seed_chat_scenario(greeting_message=""))
        with TestClient(app) as client:
            resp = client.get(f"/scenarios/{seeded['scenario_id']}")
        self.assertEqual(resp.status_code, 200)
        body = resp.text
        self.assertNotIn("message-mentor", body)
        self.assertNotIn("greeting-message", body)

    # SC5 ──────────────────────────────────────────────────────
    def test_greeting_not_stored_as_message_row(self) -> None:
        seeded = asyncio.run(
            _seed_chat_scenario(
                greeting_message="GREETING_DB_SENTINEL",
            )
        )
        with TestClient(app) as client:
            resp = client.get(f"/scenarios/{seeded['scenario_id']}")
        self.assertEqual(resp.status_code, 200)

        match = re.search(
            r"window\.currentSessionId\s*=\s*(\d+)",
            resp.text,
        )
        self.assertIsNotNone(match)
        session_id = int(match.group(1))
        count = asyncio.run(_count_messages(session_id))
        self.assertEqual(count, 0)

    def test_greeting_not_injected_into_bot_prompts(self) -> None:
        """Textual safety net: greeting_message must not appear in
        any bot prompt composition path."""
        for path in [
            "src/services/student_bot.py",
            "src/services/tutor_bot.py",
            "src/services/analysis_pipeline.py",
            "src/services/prompt_manager.py",
            "src/services/session_mgr.py",
            "src/services/analyzer.py",
            "src/services/misconception_analyzer.py",
            "src/services/dialogue_analysis.py",
        ]:
            with open(path) as f:
                content = f.read()
            self.assertNotIn(
                "greeting_message",
                content,
                f"greeting_message leaked into {path}",
            )

    # SC6 ──────────────────────────────────────────────────────
    def test_issue_9_preservice_prompt_leak_still_hidden(
        self,
    ) -> None:
        seeded = asyncio.run(
            _seed_chat_scenario(
                greeting_message="GREETING_WITH_PROMPT",
                problem_situation="문제 상황이 표시됩니다",
                prompt="SECRET_SYSTEM_PROMPT_SHOULD_NOT_LEAK",
            )
        )
        with TestClient(app) as client:
            resp = client.get(f"/scenarios/{seeded['scenario_id']}")
        self.assertEqual(resp.status_code, 200)
        body = resp.text
        # Issue #9: system prompt must stay hidden
        self.assertNotIn("SECRET_SYSTEM_PROMPT_SHOULD_NOT_LEAK", body)
        # Problem situation must be visible
        self.assertIn("문제 상황이 표시됩니다", body)
        # Greeting coexists alongside hidden prompt
        self.assertIn("GREETING_WITH_PROMPT", body)

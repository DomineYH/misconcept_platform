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
    "sqlite+aiosqlite:////tmp/misconcept_platform_prompt_test.db",
)

from fastapi.testclient import TestClient
from sqlalchemy import select

import src.models  # noqa: F401
from src.api.dependencies import get_admin_user
from src.db.connection import AsyncSessionLocal, Base, engine
from src.main import app
from src.models.prompt_template import PromptTemplate
from src.models.user import User


def override_admin_user():
    return SimpleNamespace(id=999, is_admin=True, nickname="admin")


async def reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_prompt() -> int:
    async with AsyncSessionLocal() as session:
        admin_user = User(
            id=999,
            username="admin_test",
            nickname="admin",
            role="admin",
        )
        admin_user.set_password("password123")
        prompt = PromptTemplate(
            bot_type="student",
            template_name="Original Prompt",
            template_text="Original prompt text",
            version=1,
        )
        session.add_all([admin_user, prompt])
        await session.flush()
        prompt_id = prompt.id
        await session.commit()
        return prompt_id


async def load_prompt(prompt_id: int) -> PromptTemplate | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PromptTemplate).where(PromptTemplate.id == prompt_id)
        )
        return result.scalar_one_or_none()


class AdminPromptHostCompatTest(unittest.TestCase):
    def setUp(self) -> None:
        asyncio.run(reset_db())
        app.dependency_overrides[get_admin_user] = override_admin_user

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_post_update_endpoint_updates_prompt(self) -> None:
        prompt_id = asyncio.run(seed_prompt())

        with TestClient(app) as client:
            response = client.post(
                f"/admin/prompts/{prompt_id}/update",
                json={
                    "template_name": "Updated Prompt",
                    "template_text": "Updated prompt text",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["prompt"]["template_name"],
            "Updated Prompt",
        )

        prompt = asyncio.run(load_prompt(prompt_id))
        self.assertIsNotNone(prompt)
        self.assertEqual(prompt.template_name, "Updated Prompt")

    def test_post_delete_endpoint_deletes_prompt(self) -> None:
        prompt_id = asyncio.run(seed_prompt())

        with TestClient(app) as client:
            response = client.post(f"/admin/prompts/{prompt_id}/delete")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

        prompt = asyncio.run(load_prompt(prompt_id))
        self.assertIsNone(prompt)

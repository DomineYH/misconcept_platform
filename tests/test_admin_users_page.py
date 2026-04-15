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
    "sqlite+aiosqlite:////tmp/misconcept_platform_users_test.db",
)

from fastapi.testclient import TestClient

import src.models  # noqa: F401
from src.api.dependencies import get_admin_user
from src.db.connection import AsyncSessionLocal, Base, engine
from src.main import app
from src.models.user import User
from src.models.user_group import UserGroup


def override_admin_user():
    return SimpleNamespace(id=999, is_admin=True, role="admin")


async def reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_users() -> None:
    async with AsyncSessionLocal() as session:
        group = UserGroup(name="Test Group", description="Test group")
        user = User(
            username="teacher_01",
            nickname="테스트교사",
            role="teacher",
            group=group,
        )
        user.set_password("password123")
        session.add_all([group, user])
        await session.commit()


class AdminUsersPageTest(unittest.TestCase):
    def setUp(self) -> None:
        asyncio.run(reset_db())
        asyncio.run(seed_users())
        app.dependency_overrides[get_admin_user] = override_admin_user

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_users_page_renders_valid_user_data_script(self) -> None:
        with TestClient(app) as client:
            response = client.get("/admin/users")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("id: { {", response.text)
        self.assertNotIn("group_id: { {", response.text)
        self.assertIn('"1": {', response.text)
        self.assertIn('username: "teacher_01"', response.text)

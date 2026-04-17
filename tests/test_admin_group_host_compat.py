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
    "sqlite+aiosqlite:////tmp/misconcept_platform_group_test.db",
)

from fastapi.testclient import TestClient
from sqlalchemy import select

import src.models  # noqa: F401
from src.api.dependencies import get_admin_user
from src.db.connection import AsyncSessionLocal, Base, engine
from src.main import app
from src.models.user_group import UserGroup


def override_admin_user():
    return SimpleNamespace(id=999, is_admin=True)


async def reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_group() -> int:
    async with AsyncSessionLocal() as session:
        group = UserGroup(
            name="Original Group",
            description="Original description",
        )
        session.add(group)
        await session.flush()
        group_id = group.id
        await session.commit()
        return group_id


async def load_group(group_id: int) -> UserGroup | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserGroup).where(UserGroup.id == group_id)
        )
        return result.scalar_one_or_none()


class AdminGroupHostCompatTest(unittest.TestCase):
    def setUp(self) -> None:
        asyncio.run(reset_db())
        app.dependency_overrides[get_admin_user] = override_admin_user

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_post_update_endpoint_updates_group(self) -> None:
        group_id = asyncio.run(seed_group())

        with TestClient(app) as client:
            response = client.post(
                f"/admin/groups/{group_id}/update",
                json={
                    "name": "Updated Group",
                    "description": "Updated description",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Updated Group")

        group = asyncio.run(load_group(group_id))
        self.assertIsNotNone(group)
        self.assertEqual(group.name, "Updated Group")

    def test_post_delete_endpoint_deletes_group(self) -> None:
        group_id = asyncio.run(seed_group())

        with TestClient(app) as client:
            response = client.post(f"/admin/groups/{group_id}/delete")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "deleted")

        group = asyncio.run(load_group(group_id))
        self.assertIsNone(group)

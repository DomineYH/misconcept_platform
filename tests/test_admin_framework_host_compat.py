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
    "sqlite+aiosqlite:////tmp/misconcept_platform_framework_test.db",
)

from fastapi.testclient import TestClient
from sqlalchemy import select

import src.models  # noqa: F401
from src.api.dependencies import get_admin_user
from src.db.connection import AsyncSessionLocal, Base, engine
from src.main import app
from src.models.analysis_framework import AnalysisFramework


def override_admin_user():
    return SimpleNamespace(id=999, is_admin=True)


async def reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_framework() -> int:
    async with AsyncSessionLocal() as session:
        framework = AnalysisFramework(
            name="Original Framework",
            description="Original framework description",
            labels_json=(
                '[{"name":"A","criteria":"A criteria"},'
                '{"name":"B","criteria":"B criteria"}]'
            ),
        )
        session.add(framework)
        await session.flush()
        framework_id = framework.id
        await session.commit()
        return framework_id


async def load_framework(framework_id: int) -> AnalysisFramework | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AnalysisFramework).where(
                AnalysisFramework.id == framework_id
            )
        )
        return result.scalar_one_or_none()


class AdminFrameworkHostCompatTest(unittest.TestCase):
    def setUp(self) -> None:
        asyncio.run(reset_db())
        app.dependency_overrides[get_admin_user] = override_admin_user

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_post_update_endpoint_updates_framework(self) -> None:
        framework_id = asyncio.run(seed_framework())

        with TestClient(app) as client:
            response = client.post(
                f"/admin/frameworks/{framework_id}/update",
                json={
                    "name": "Updated Framework",
                    "description": "Updated framework description",
                    "labels": [
                        {"name": "XX", "criteria": "X criteria"},
                        {"name": "YY", "criteria": "Y criteria"},
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Updated Framework")

        framework = asyncio.run(load_framework(framework_id))
        self.assertIsNotNone(framework)
        self.assertEqual(framework.name, "Updated Framework")
        self.assertIn("X criteria", framework.labels_json)

    def test_post_delete_endpoint_deletes_framework(self) -> None:
        framework_id = asyncio.run(seed_framework())

        with TestClient(app) as client:
            response = client.post(f"/admin/frameworks/{framework_id}/delete")

        self.assertEqual(response.status_code, 200)
        framework = asyncio.run(load_framework(framework_id))
        self.assertIsNone(framework)

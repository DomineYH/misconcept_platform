"""Contract tests for bulk user registration endpoint."""

import pytest
from sqlalchemy import select
from src.models.user import User
from src.models.user_group import UserGroup


async def _login(client, username, password="test1234"):
    await client.post(
        "/login",
        data={"username": username, "password": password},
    )


@pytest.fixture
async def admin(async_session):
    user = User(
        username="reg_admin", nickname="관리자", role="admin"
    )
    user.set_password("test1234")
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
async def group(async_session):
    g = UserGroup(name="RegGroup")
    async_session.add(g)
    await async_session.flush()
    return g


class TestBulkRegister:
    @pytest.mark.asyncio
    async def test_register_creates_users(
        self, async_client, async_session, admin, group
    ):
        await _login(async_client, admin.username)
        resp = await async_client.post(
            "/admin/users/bulk/register",
            json={
                "users": [
                    {
                        "username": "bulk_r1",
                        "nickname": "벌크1",
                        "role": "teacher",
                        "group_id": group.id,
                    },
                    {
                        "username": "bulk_r2",
                        "nickname": "벌크2",
                        "role": "admin",
                        "group_id": None,
                    },
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success_count"] == 2
        assert data["fail_count"] == 0
        created = (
            await async_session.execute(
                select(User).where(
                    User.username.in_(["bulk_r1", "bulk_r2"])
                )
            )
        ).scalars().all()
        assert len(created) == 2

    @pytest.mark.asyncio
    async def test_register_reports_failures(
        self, async_client, async_session, admin
    ):
        existing = User(
            username="already_taken",
            nickname="기존",
            role="teacher",
        )
        existing.set_password("test1234")
        async_session.add(existing)
        await async_session.flush()
        await _login(async_client, admin.username)
        resp = await async_client.post(
            "/admin/users/bulk/register",
            json={
                "users": [
                    {
                        "username": "already_taken",
                        "nickname": "중복",
                    },
                    {
                        "username": "success_user",
                        "nickname": "성공",
                    },
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success_count"] == 1
        assert data["fail_count"] == 1
        assert data["failures"][0]["username"] == "already_taken"

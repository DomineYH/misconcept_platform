"""Contract tests for bulk user preview endpoint."""

import pytest
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
        username="prev_admin", nickname="관리자", role="admin"
    )
    user.set_password("test1234")
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
async def group(async_session):
    g = UserGroup(name="1학년")
    async_session.add(g)
    await async_session.flush()
    return g


def _csv_file(content: str):
    return {
        "file": ("test.csv", content.encode("utf-8"), "text/csv")
    }


class TestBulkPreview:
    @pytest.mark.asyncio
    async def test_valid_csv_returns_preview(
        self, async_client, admin, group
    ):
        await _login(async_client, admin.username)
        resp = await async_client.post(
            "/admin/users/bulk/preview",
            files=_csv_file(
                "username,nickname,role,group\n"
                "user_01,유저1,teacher,1학년\n"
                "user_02,유저2,,\n"
            ),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total"] == 2
        assert data["summary"]["valid"] == 2
        assert data["rows"][0]["group_id"] == group.id
        assert len(data["groups"]) >= 1

    @pytest.mark.asyncio
    async def test_invalid_csv_returns_400(
        self, async_client, admin
    ):
        await _login(async_client, admin.username)
        resp = await async_client.post(
            "/admin/users/bulk/preview",
            files=_csv_file("username,role\nkim,teacher\n"),
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_duplicate_username_shown_in_preview(
        self, async_client, async_session, admin
    ):
        existing = User(
            username="dup_user",
            nickname="기존",
            role="teacher",
        )
        existing.set_password("test1234")
        async_session.add(existing)
        await async_session.flush()
        await _login(async_client, admin.username)
        resp = await async_client.post(
            "/admin/users/bulk/preview",
            files=_csv_file(
                "username,nickname,role,group\n"
                "dup_user,중복시도,,\n"
            ),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["error"] == 1
        assert "이미 존재" in data["rows"][0]["errors"][0]

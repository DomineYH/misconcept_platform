"""Contract tests for bulk CSV template download."""

import pytest
from src.models.user import User


async def _login(client, username, password="test1234"):
    await client.post(
        "/login",
        data={"username": username, "password": password},
    )


@pytest.fixture
async def admin(async_session):
    user = User(
        username="tmpl_admin", nickname="관리자", role="admin"
    )
    user.set_password("test1234")
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
async def teacher(async_session):
    user = User(
        username="tmpl_teacher", nickname="교사", role="teacher"
    )
    user.set_password("test1234")
    async_session.add(user)
    await async_session.flush()
    return user


class TestBulkTemplateDownload:
    @pytest.mark.asyncio
    async def test_admin_can_download(self, async_client, admin):
        await _login(async_client, admin.username)
        resp = await async_client.get(
            "/admin/users/bulk/template"
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert (
            "attachment" in resp.headers["content-disposition"]
        )
        content = resp.content.decode("utf-8-sig")
        assert "username" in content
        assert "nickname" in content

    @pytest.mark.asyncio
    async def test_teacher_forbidden(
        self, async_client, teacher
    ):
        await _login(async_client, teacher.username)
        resp = await async_client.get(
            "/admin/users/bulk/template"
        )
        assert resp.status_code == 403

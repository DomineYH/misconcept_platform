"""Contract tests for admin bulk user creation endpoints."""

import csv
import io

import pytest
from sqlalchemy import select

from src.models.user import User
from src.models.user_group import UserGroup


def _csv_bytes(rows: list[dict[str, str]]) -> bytes:
    """Build a BOM-prefixed CSV payload for multipart uploads."""
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "username",
            "nickname",
            "password",
            "role",
            "group_name",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


async def _login(async_client, username: str, password: str = "test1234"):
    """Authenticate a client for admin bulk-user endpoint tests."""
    response = await async_client.post(
        "/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200


@pytest.fixture
async def admin_user(async_session) -> User:
    """Create an admin user for bulk-user endpoint tests."""
    user = User(
        username="bulk_admin",
        nickname="대량관리자",
        role="admin",
    )
    user.set_password("test1234")
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
async def teacher_user(async_session) -> User:
    """Create a teacher user for authz coverage."""
    user = User(
        username="bulk_teacher",
        nickname="일반교사",
        role="teacher",
    )
    user.set_password("test1234")
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
async def bulk_group(async_session) -> UserGroup:
    """Create a group referenced by bulk-create requests."""
    group = UserGroup(
        name="Bulk Endpoint Group",
        description="Group used by contract tests",
    )
    async_session.add(group)
    await async_session.flush()
    return group


class TestAdminUserBulkTemplate:
    """Contract coverage for the bulk CSV template download route."""

    def test_template_redirects_when_not_logged_in(self, test_client):
        """Unauthenticated requests must redirect to login."""
        response = test_client.get(
            "/admin/users/bulk-template.csv",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_template_requires_admin_role(
        self,
        async_client,
        teacher_user: User,
    ):
        """Non-admin users must receive 403 for the template route."""
        await _login(async_client, teacher_user.username)

        response = await async_client.get("/admin/users/bulk-template.csv")

        assert response.status_code == 403
        assert response.json()["detail"]

    @pytest.mark.asyncio
    async def test_admin_can_download_template_with_bom_and_exact_header(
        self,
        async_client,
        admin_user: User,
    ):
        """Template response must be a BOM-prefixed CSV with exact headers."""
        await _login(async_client, admin_user.username)

        response = await async_client.get("/admin/users/bulk-template.csv")

        assert response.status_code == 200
        assert "text/csv; charset=utf-8" in response.headers["content-type"]
        assert "attachment;" in response.headers["content-disposition"]
        assert response.content.startswith(b"\xef\xbb\xbf")

        decoded = response.content.decode("utf-8-sig").splitlines()
        assert decoded[0] == "username,nickname,password,role,group_name"


class TestAdminUserBulkPattern:
    """Contract coverage for pattern-mode bulk user creation."""

    @pytest.mark.asyncio
    async def test_pattern_route_requires_admin_role(
        self,
        async_client,
        teacher_user: User,
    ):
        """Non-admin users must be blocked from pattern mode."""
        await _login(async_client, teacher_user.username)

        response = await async_client.post(
            "/admin/users/bulk-pattern",
            data={
                "start_username": "teacher_1",
                "count": 1,
                "role": "teacher",
                "group_id": None,
            },
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_pattern_mode_skips_taken_suffixes(
        self,
        async_client,
        async_session,
        admin_user: User,
        bulk_group: UserGroup,
    ):
        """Pattern mode must skip collisions and still create N users."""
        taken_1 = User(
            username="pattern_1",
            nickname="pattern_1",
            role="teacher",
            group_id=bulk_group.id,
        )
        taken_1.set_password("existing123")
        taken_3 = User(
            username="pattern_3",
            nickname="pattern_3",
            role="teacher",
            group_id=bulk_group.id,
        )
        taken_3.set_password("existing123")
        async_session.add_all([taken_1, taken_3])
        await async_session.flush()

        await _login(async_client, admin_user.username)
        response = await async_client.post(
            "/admin/users/bulk-pattern",
            data={
                "start_username": "pattern_1",
                "count": 3,
                "role": "teacher",
                "group_id": bulk_group.id,
            },
        )

        created = (
            (
                await async_session.execute(
                    select(User)
                    .where(
                        User.username.in_(
                            ["pattern_2", "pattern_4", "pattern_5"]
                        )
                    )
                    .order_by(User.username)
                )
            )
            .scalars()
            .all()
        )

        assert response.status_code in (200, 201)
        assert response.json()["created_count"] == 3
        assert response.json()["failed_count"] == 0
        assert [user.username for user in created] == [
            "pattern_2",
            "pattern_4",
            "pattern_5",
        ]
        assert all(user.nickname == user.username for user in created)
        assert all(user.verify_password("0000") for user in created)

    @pytest.mark.asyncio
    async def test_bulk_pattern_keeps_legacy_password_rule(
        self,
        async_client,
        async_session,
        admin_user: User,
    ):
        """Bulk endpoints must accept the approved 0000 rule independently."""
        await _login(async_client, admin_user.username)

        legacy_response = await async_client.post(
            "/admin/users",
            json={
                "username": "legacy_short_pw",
                "password": "0000",
                "nickname": "짧은비번",
                "role": "teacher",
                "group_id": None,
            },
        )
        bulk_response = await async_client.post(
            "/admin/users/bulk-pattern",
            data={
                "start_username": "bulkshort_1",
                "count": 1,
                "role": "teacher",
                "group_id": None,
            },
        )

        created = await async_session.scalar(
            select(User).where(User.username == "bulkshort_1")
        )

        assert legacy_response.status_code == 422
        assert bulk_response.status_code in (200, 201)
        assert bulk_response.json()["created_count"] == 1
        assert created is not None
        assert created.verify_password("0000")


class TestAdminUserBulkCsv:
    """Contract coverage for multipart CSV uploads."""

    @pytest.mark.asyncio
    async def test_csv_route_requires_admin_role(
        self,
        async_client,
        teacher_user: User,
    ):
        """Non-admin users must be blocked from CSV mode."""
        await _login(async_client, teacher_user.username)

        response = await async_client.post(
            "/admin/users/bulk-csv",
            files={
                "file": (
                    "bulk-users.csv",
                    _csv_bytes([]),
                    "text/csv",
                )
            },
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_upload_csv_via_multipart_and_get_summary(
        self,
        async_client,
        async_session,
        admin_user: User,
        bulk_group: UserGroup,
    ):
        """CSV mode must accept multipart upload and create valid rows."""
        await _login(async_client, admin_user.username)

        response = await async_client.post(
            "/admin/users/bulk-csv",
            files={
                "file": (
                    "bulk-users.csv",
                    _csv_bytes(
                        [
                            {
                                "username": "csv_route_1",
                                "nickname": "CSV Route 1",
                                "password": "0000",
                                "role": "teacher",
                                "group_name": bulk_group.name,
                            },
                            {
                                "username": "csv_route_2",
                                "nickname": "CSV Route 2",
                                "password": "secret123",
                                "role": "admin",
                                "group_name": "",
                            },
                        ]
                    ),
                    "text/csv",
                )
            },
        )

        created = (
            (
                await async_session.execute(
                    select(User)
                    .where(User.username.in_(["csv_route_1", "csv_route_2"]))
                    .order_by(User.username)
                )
            )
            .scalars()
            .all()
        )
        created_map = {user.username: user for user in created}

        assert response.status_code in (200, 201)
        assert response.json()["created_count"] == 2
        assert response.json()["failed_count"] == 0
        assert created_map["csv_route_1"].group_id == bulk_group.id
        assert created_map["csv_route_1"].verify_password("0000")
        assert created_map["csv_route_2"].role == "admin"

    @pytest.mark.asyncio
    async def test_csv_duplicate_usernames_fail_in_place_not_by_renumbering(
        self,
        async_client,
        async_session,
        admin_user: User,
        bulk_group: UserGroup,
    ):
        """Duplicate CSV usernames must fail rather than auto-renumber."""
        existing = User(
            username="dup_csv_user",
            nickname="Existing CSV User",
            role="teacher",
            group_id=bulk_group.id,
        )
        existing.set_password("existing123")
        async_session.add(existing)
        await async_session.flush()

        await _login(async_client, admin_user.username)
        response = await async_client.post(
            "/admin/users/bulk-csv",
            files={
                "file": (
                    "bulk-users.csv",
                    _csv_bytes(
                        [
                            {
                                "username": "dup_csv_user",
                                "nickname": "Duplicate",
                                "password": "0000",
                                "role": "teacher",
                                "group_name": bulk_group.name,
                            },
                            {
                                "username": "csv_success",
                                "nickname": "Success",
                                "password": "0000",
                                "role": "teacher",
                                "group_name": bulk_group.name,
                            },
                        ]
                    ),
                    "text/csv",
                )
            },
        )

        persisted_usernames = set(
            (
                await async_session.execute(
                    select(User.username).where(
                        User.username.in_(
                            [
                                "dup_csv_user",
                                "dup_csv_user_1",
                                "csv_success",
                            ]
                        )
                    )
                )
            )
            .scalars()
            .all()
        )

        assert response.status_code in (200, 201)
        assert response.json()["created_count"] == 1
        assert response.json()["failed_count"] == 1
        assert persisted_usernames == {"dup_csv_user", "csv_success"}

    @pytest.mark.asyncio
    async def test_csv_upload_over_one_mebibyte_is_rejected_before_writes(
        self,
        async_client,
        async_session,
        admin_user: User,
    ):
        """Oversized CSV uploads must fail before any user is created."""
        await _login(async_client, admin_user.username)

        huge_field = "x" * (1024 * 1024)
        payload = (
            "username,nickname,password,role,group_name\n"
            f"too_big,{huge_field},0000,teacher,\n"
        ).encode("utf-8")

        response = await async_client.post(
            "/admin/users/bulk-csv",
            files={
                "file": (
                    "too-large.csv",
                    payload,
                    "text/csv",
                )
            },
        )

        persisted = await async_session.scalar(
            select(User).where(User.username == "too_big")
        )

        assert response.status_code == 400
        assert persisted is None

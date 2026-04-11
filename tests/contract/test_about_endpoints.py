"""Contract tests for About page endpoints."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.contributor import Contributor
from src.models.user import User


async def _login(client, username, password="test1234"):
    """Helper: log in via POST /login (no redirect follow)."""
    await client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


@pytest.fixture
async def admin_user(async_session: AsyncSession) -> User:
    """Create an admin user for testing."""
    user = User(
        username="admin_about", nickname="관리자", role="admin"
    )
    user.set_password("test1234")
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
async def teacher_user(async_session: AsyncSession) -> User:
    """Create a teacher user for testing."""
    user = User(
        username="teacher_about",
        nickname="김교사",
        role="teacher",
    )
    user.set_password("test1234")
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
async def sample_contributor(
    async_session: AsyncSession,
) -> Contributor:
    """Create a sample contributor for testing."""
    contributor = Contributor(
        name="홍길동",
        affiliation="한국대학교",
        bio="10년 경력의 교육 연구자",
        phone="010-1234-5678",
        email="hong@example.com",
        sort_order=0,
    )
    async_session.add(contributor)
    await async_session.flush()
    return contributor


class TestContributorCRUD:
    """Tests for contributor CRUD operations via API."""

    @pytest.mark.asyncio
    async def test_create_contributor_success(
        self,
        async_client,
        async_session: AsyncSession,
        admin_user: User,
    ):
        """Admin can create a contributor."""
        await _login(async_client, admin_user.username)
        payload = {
            "name": "홍길동",
            "affiliation": "한국대학교",
            "bio": "교육 연구자입니다.",
            "phone": "010-1234-5678",
            "email": "hong@example.com",
            "sort_order": 0,
        }
        response = await async_client.post(
            "/admin/about",
            json=payload,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "홍길동"
        assert data["affiliation"] == "한국대학교"
        assert data["bio"] == "교육 연구자입니다."
        assert data["phone"] == "010-1234-5678"
        assert data["email"] == "hong@example.com"
        assert data["id"] > 0

    @pytest.mark.asyncio
    async def test_create_contributor_without_contact(
        self,
        async_client,
        async_session: AsyncSession,
        admin_user: User,
    ):
        """Contributor can be created without phone/email."""
        await _login(async_client, admin_user.username)
        payload = {
            "name": "김철수",
            "affiliation": "서울교육청",
            "bio": "장학사",
            "sort_order": 1,
        }
        response = await async_client.post(
            "/admin/about",
            json=payload,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "김철수"
        assert data["phone"] is None
        assert data["email"] is None

    @pytest.mark.asyncio
    async def test_create_contributor_requires_admin(
        self,
        async_client,
        async_session: AsyncSession,
        teacher_user: User,
    ):
        """Non-admin cannot create a contributor."""
        await _login(async_client, teacher_user.username)
        payload = {
            "name": "테스트",
            "affiliation": "소속",
            "bio": "이력",
        }
        response = await async_client.post(
            "/admin/about",
            json=payload,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_contributor(
        self,
        async_client,
        async_session: AsyncSession,
        admin_user: User,
        sample_contributor: Contributor,
    ):
        """Admin can update a contributor."""
        await _login(async_client, admin_user.username)
        payload = {
            "name": "홍길동 (수정됨)",
            "affiliation": "서울대학교",
        }
        response = await async_client.post(
            f"/admin/about/{sample_contributor.id}/update",
            json=payload,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "홍길동 (수정됨)"
        assert data["affiliation"] == "서울대학교"
        # Unchanged fields remain
        assert data["bio"] == sample_contributor.bio

    @pytest.mark.asyncio
    async def test_update_contributor_not_found(
        self,
        async_client,
        async_session: AsyncSession,
        admin_user: User,
    ):
        """Returns 404 when updating non-existent contributor."""
        await _login(async_client, admin_user.username)
        response = await async_client.post(
            "/admin/about/99999/update",
            json={"name": "없음"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_contributor(
        self,
        async_client,
        async_session: AsyncSession,
        admin_user: User,
        sample_contributor: Contributor,
    ):
        """Admin can delete a contributor."""
        await _login(async_client, admin_user.username)
        response = await async_client.post(
            f"/admin/about/{sample_contributor.id}/delete",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        assert data["contributor_id"] == sample_contributor.id

    @pytest.mark.asyncio
    async def test_delete_contributor_not_found(
        self,
        async_client,
        async_session: AsyncSession,
        admin_user: User,
    ):
        """Returns 404 when deleting non-existent contributor."""
        await _login(async_client, admin_user.username)
        response = await async_client.post(
            "/admin/about/99999/delete",
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_contributor_missing_required_fields(
        self,
        async_client,
        async_session: AsyncSession,
        admin_user: User,
    ):
        """Returns 422 when required fields are missing."""
        await _login(async_client, admin_user.username)
        # Missing affiliation and bio
        payload = {"name": "홍길동"}
        response = await async_client.post(
            "/admin/about",
            json=payload,
        )
        assert response.status_code == 422


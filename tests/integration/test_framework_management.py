"""Integration tests for framework management UI (Web)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analysis_framework import AnalysisFramework
from src.models.scenario import Scenario
from src.models.user import User


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user."""
    user = User(
        student_uid="admin_fw_001", nickname="프레임워크관리자", role="admin"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def teacher_user(db_session: AsyncSession) -> User:
    """Create a teacher user."""
    user = User(
        student_uid="teacher_fw_001", nickname="일반교사", role="teacher"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_framework(
    db_session: AsyncSession,
) -> AnalysisFramework:
    """Create a test framework."""
    framework = AnalysisFramework(
        name="테스트 프레임워크",
        description="통합 테스트용 분석 프레임워크입니다.",
        labels_json='["높은 레버리지", "낮은 레버리지"]',
    )
    db_session.add(framework)
    await db_session.commit()
    await db_session.refresh(framework)
    return framework


class TestFrameworkManagement:
    """Test framework CRUD operations via web UI."""

    def test_get_framework_page_admin(
        self, test_client: TestClient, admin_user: User
    ):
        """Test: Admin can access framework management page."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Access framework page
        response = test_client.get("/admin/frameworks")
        assert response.status_code == 200
        assert "분석 프레임워크 관리" in response.text

    def test_get_framework_page_teacher_forbidden(
        self, test_client: TestClient, teacher_user: User
    ):
        """Test: Teacher cannot access framework management page."""
        # Login as teacher
        test_client.post(
            "/login",
            data={
                "student_uid": teacher_user.student_uid,
                "nickname": teacher_user.nickname,
            },
        )

        # Try to access framework page
        response = test_client.get("/admin/frameworks")
        assert response.status_code == 403

    def test_create_framework(
        self, test_client: TestClient, admin_user: User
    ):
        """Test: Create new framework via POST."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Create framework
        response = test_client.post(
            "/admin/frameworks",
            json={
                "name": "신규 프레임워크",
                "description": "새로 만든 분석 프레임워크입니다.",
                "labels": ["카테고리A", "카테고리B", "카테고리C"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "신규 프레임워크"
        assert data["description"] == "새로 만든 분석 프레임워크입니다."
        assert "labels_json" in data

    def test_create_framework_duplicate_name(
        self,
        test_client: TestClient,
        admin_user: User,
        test_framework: AnalysisFramework,
    ):
        """Test: Cannot create framework with duplicate name."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Try to create framework with same name
        response = test_client.post(
            "/admin/frameworks",
            json={
                "name": test_framework.name,
                "description": "다른 설명으로 작성된 프레임워크입니다.",
                "labels": ["라벨1", "라벨2"],
            },
        )

        assert response.status_code == 409
        assert "이미 존재합니다" in response.json()["detail"]

    def test_create_framework_invalid_labels(
        self, test_client: TestClient, admin_user: User
    ):
        """Test: Validation error when labels < 2."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Try to create framework with only 1 label
        response = test_client.post(
            "/admin/frameworks",
            json={
                "name": "잘못된 프레임워크",
                "description": "라벨이 부족합니다.",
                "labels": ["라벨1"],
            },
        )

        assert response.status_code == 422

    def test_update_framework(
        self,
        test_client: TestClient,
        admin_user: User,
        test_framework: AnalysisFramework,
    ):
        """Test: Update existing framework."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Update framework
        response = test_client.put(
            f"/admin/frameworks/{test_framework.id}",
            json={
                "name": "수정된 프레임워크",
                "description": "설명이 업데이트되었습니다.",
                "labels": [
                    "수정된라벨1",
                    "수정된라벨2",
                    "수정된라벨3",
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "수정된 프레임워크"
        assert data["description"] == "설명이 업데이트되었습니다."

    def test_delete_framework_success(
        self,
        test_client: TestClient,
        admin_user: User,
        test_framework: AnalysisFramework,
    ):
        """Test: Delete framework when not in use."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Delete framework
        response = test_client.delete(
            f"/admin/frameworks/{test_framework.id}"
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_framework_in_use(
        self,
        test_client: TestClient,
        admin_user: User,
        test_framework: AnalysisFramework,
        db_session: AsyncSession,
    ):
        """Test: Cannot delete framework if scenarios are using it."""
        # Create a scenario using this framework
        scenario = Scenario(
            title="테스트 시나리오",
            prompt="프롬프트",
            student_profile="학생 프로필",
            framework_id=test_framework.id,
            is_active=1,
        )
        db_session.add(scenario)
        await db_session.commit()

        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Try to delete framework
        response = test_client.delete(
            f"/admin/frameworks/{test_framework.id}"
        )

        assert response.status_code == 409
        assert "사용 중입니다" in response.json()["detail"]

    def test_framework_not_found(
        self, test_client: TestClient, admin_user: User
    ):
        """Test: 404 when framework doesn't exist."""
        # Login as admin
        test_client.post(
            "/login",
            data={
                "student_uid": admin_user.student_uid,
                "nickname": admin_user.nickname,
            },
        )

        # Try to update non-existent framework
        response = test_client.put(
            "/admin/frameworks/99999",
            json={
                "name": "존재하지 않는 프레임워크",
                "description": "이 프레임워크는 존재하지 않습니다.",
                "labels": ["라벨1", "라벨2"],
            },
        )

        assert response.status_code == 404
        assert "찾을 수 없습니다" in response.json()["detail"]

"""Integration test for session auto-creation flow (TEST-002).

Tests the complete flow:
1. User selects scenario from /scenarios/{id}
2. System auto-creates session
3. Chat page renders with session_id
"""
import pytest
import re
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import User, AnalysisFramework, Scenario, Session
from src.models.prompt_template import PromptTemplate


@pytest.fixture
async def test_student_template(db_session: AsyncSession) -> PromptTemplate:
    """Create test student template."""
    template = PromptTemplate(
        bot_type="student",
        template_name="Test Student Template",
        version=1,
        template_text=(
            "You are a test student bot. Scenario: {scenario_title}. "
            "Profile: {student_profile}. Context: {prompt}"
        ),
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest.fixture
async def test_framework(db_session: AsyncSession) -> AnalysisFramework:
    """Create test analysis framework."""
    framework = AnalysisFramework(
        name="Test Framework",
        description="For testing",
        labels_json='["Label1", "Label2", "Label3"]',
    )
    db_session.add(framework)
    await db_session.commit()
    await db_session.refresh(framework)
    return framework


@pytest.fixture
async def test_scenario(
    db_session: AsyncSession,
    test_framework: AnalysisFramework,
    test_student_template: PromptTemplate,
) -> Scenario:
    """Create active test scenario."""
    scenario = Scenario(
        title="Test Scenario",
        prompt="Test system prompt for scenario",
        student_profile="Test student profile",
        framework_id=test_framework.id,
        student_template_id=test_student_template.id,
        is_active=1,
    )
    db_session.add(scenario)
    await db_session.commit()
    await db_session.refresh(scenario)
    return scenario


@pytest.fixture
async def inactive_scenario(
    db_session: AsyncSession,
    test_framework: AnalysisFramework,
    test_student_template: PromptTemplate,
) -> Scenario:
    """Create inactive test scenario for rejection tests."""
    scenario = Scenario(
        title="Inactive Scenario",
        prompt="This scenario is inactive",
        student_profile="Should not be accessible",
        framework_id=test_framework.id,
        student_template_id=test_student_template.id,
        is_active=0,
    )
    db_session.add(scenario)
    await db_session.commit()
    await db_session.refresh(scenario)
    return scenario


class TestScenarioSelectCreatesSession:
    """Test that selecting a scenario auto-creates a session."""

    async def test_scenario_select_creates_session(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_scenario: Scenario,
    ):
        """시나리오 선택 시 자동으로 세션이 생성되는지 확인."""
        # Step 1: Login as teacher
        login_response = test_client.post(
            "/login",
            data={"student_uid": "test_teacher_001", "nickname": "테스트교사"},
            follow_redirects=False,
        )
        assert login_response.status_code == 303
        cookies = login_response.cookies

        # Get user_id for verification
        result = await db_session.execute(
            select(User).where(User.student_uid == "test_teacher_001")
        )
        user = result.scalar_one()

        # Step 2: Count sessions before scenario selection
        before_count_result = await db_session.execute(
            select(func.count()).select_from(Session)
        )
        before_count = before_count_result.scalar()

        # Step 3: Select scenario (GET /scenarios/{id})
        scenario_response = test_client.get(
            f"/scenarios/{test_scenario.id}", cookies=cookies
        )

        # Step 4: Verify response is successful
        assert scenario_response.status_code == 200
        assert "text/html" in scenario_response.headers["content-type"]

        # Step 5: Count sessions after scenario selection
        after_count_result = await db_session.execute(
            select(func.count()).select_from(Session)
        )
        after_count = after_count_result.scalar()

        # Step 6: Verify session was created
        assert after_count == before_count + 1, (
            f"Expected {before_count + 1} sessions, got {after_count}"
        )

        # Step 7: Verify session properties
        result = await db_session.execute(
            select(Session)
            .where(Session.scenario_id == test_scenario.id)
            .where(Session.teacher_id == user.id)
            .order_by(Session.id.desc())
        )
        created_session = result.scalar_one()

        assert created_session.scenario_id == test_scenario.id
        assert created_session.teacher_id == user.id
        assert created_session.ended_at is None

    async def test_multiple_sessions_allowed(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_scenario: Scenario,
    ):
        """동일 시나리오에 대해 여러 세션 생성 가능한지 확인."""
        # Login
        login_response = test_client.post(
            "/login",
            data={"student_uid": "test_teacher_002", "nickname": "테스트교사2"},
        )
        cookies = login_response.cookies

        # Get user_id
        result = await db_session.execute(
            select(User).where(User.student_uid == "test_teacher_002")
        )
        user = result.scalar_one()

        # First visit
        response1 = test_client.get(
            f"/scenarios/{test_scenario.id}", cookies=cookies
        )
        assert response1.status_code == 200

        # Second visit
        response2 = test_client.get(
            f"/scenarios/{test_scenario.id}", cookies=cookies
        )
        assert response2.status_code == 200

        # Verify two separate sessions were created
        result = await db_session.execute(
            select(Session)
            .where(Session.scenario_id == test_scenario.id)
            .where(Session.teacher_id == user.id)
        )
        sessions = result.scalars().all()

        assert len(sessions) >= 2
        # Verify they have different IDs
        session_ids = [s.id for s in sessions]
        assert len(session_ids) == len(set(session_ids))


class TestChatPageHasSessionId:
    """Test that chat.html receives and displays session_id correctly."""

    async def test_chat_page_has_session_id(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_scenario: Scenario,
    ):
        """chat.html에 session_id가 올바르게 전달되는지 확인."""
        # Step 1: Login
        login_response = test_client.post(
            "/login",
            data={"student_uid": "test_teacher_003", "nickname": "테스트교사3"},
        )
        cookies = login_response.cookies

        # Step 2: Access scenario (auto-creates session)
        response = test_client.get(
            f"/scenarios/{test_scenario.id}", cookies=cookies
        )

        assert response.status_code == 200
        html_content = response.text

        # Step 3: Verify session_id in JavaScript
        # Pattern: window.currentSessionId = <number>;
        js_pattern = r"window\.currentSessionId\s*=\s*(\d+)"
        match = re.search(js_pattern, html_content)

        assert match is not None, (
            "window.currentSessionId not found in HTML"
        )
        session_id_from_js = int(match.group(1))

        # Step 4: Verify HTMX attributes include session_id
        # Pattern: hx-get="/sessions/{id}/messages/updates"
        htmx_get_pattern = (
            rf'hx-get="/sessions/{session_id_from_js}/messages/updates"'
        )
        assert htmx_get_pattern in html_content, (
            f"HTMX hx-get with session_id {session_id_from_js} not found"
        )

        # Pattern: hx-post="/sessions/{id}/messages"
        htmx_post_pattern = (
            rf'hx-post="/sessions/{session_id_from_js}/messages"'
        )
        assert htmx_post_pattern in html_content, (
            f"HTMX hx-post with session_id {session_id_from_js} not found"
        )

        # Step 5: Verify session exists in database
        result = await db_session.execute(
            select(Session).where(Session.id == session_id_from_js)
        )
        db_session_obj = result.scalar_one_or_none()

        assert db_session_obj is not None, (
            f"Session {session_id_from_js} not found in database"
        )
        assert db_session_obj.scenario_id == test_scenario.id

    async def test_chat_page_includes_scenario_info(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_scenario: Scenario,
    ):
        """chat.html에 시나리오 정보가 포함되는지 확인."""
        # Login
        login_response = test_client.post(
            "/login",
            data={"student_uid": "test_teacher_004", "nickname": "테스트교사4"},
        )
        cookies = login_response.cookies

        # Access scenario
        response = test_client.get(
            f"/scenarios/{test_scenario.id}", cookies=cookies
        )

        assert response.status_code == 200
        html_content = response.text

        # Verify scenario title
        assert test_scenario.title in html_content

        # Verify student profile if present
        if test_scenario.student_profile:
            assert test_scenario.student_profile in html_content


class TestInactiveScenarioRejected:
    """Test that inactive scenarios are not accessible."""

    async def test_inactive_scenario_rejected(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        inactive_scenario: Scenario,
    ):
        """비활성화된 시나리오 접근 시 404 반환 확인."""
        # Step 1: Login as regular user (not admin)
        login_response = test_client.post(
            "/login",
            data={"student_uid": "test_teacher_005", "nickname": "테스트교사5"},
        )
        cookies = login_response.cookies

        # Get user to verify it's not admin
        result = await db_session.execute(
            select(User).where(User.student_uid == "test_teacher_005")
        )
        user = result.scalar_one()
        assert user.role != "admin"

        # Step 2: Count sessions before attempt
        before_count_result = await db_session.execute(
            select(func.count()).select_from(Session)
        )
        before_count = before_count_result.scalar()

        # Step 3: Try to access inactive scenario
        response = test_client.get(
            f"/scenarios/{inactive_scenario.id}", cookies=cookies
        )

        # Step 4: Verify 404 response
        assert response.status_code == 404

        # Step 5: Verify no session was created
        after_count_result = await db_session.execute(
            select(func.count()).select_from(Session)
        )
        after_count = after_count_result.scalar()

        assert after_count == before_count, (
            "Session should not be created for inactive scenario"
        )

    async def test_admin_can_access_inactive_scenario(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        inactive_scenario: Scenario,
    ):
        """관리자는 비활성 시나리오에 접근 가능한지 확인."""
        # Create admin user
        admin_user = User(
            student_uid="admin_001",
            nickname="관리자",
            role="admin",
        )
        db_session.add(admin_user)
        await db_session.commit()
        await db_session.refresh(admin_user)

        # Login as admin
        login_response = test_client.post(
            "/login",
            data={"student_uid": "admin_001", "nickname": "관리자"},
        )
        cookies = login_response.cookies

        # Access inactive scenario
        response = test_client.get(
            f"/scenarios/{inactive_scenario.id}", cookies=cookies
        )

        # Admin should be able to access
        assert response.status_code == 200

        # Verify session was created
        result = await db_session.execute(
            select(Session)
            .where(Session.scenario_id == inactive_scenario.id)
            .where(Session.teacher_id == admin_user.id)
        )
        session = result.scalar_one_or_none()

        assert session is not None


class TestSessionCreationErrorHandling:
    """Test error handling during session creation."""

    async def test_nonexistent_scenario_returns_404(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
    ):
        """존재하지 않는 시나리오 접근 시 404 확인."""
        # Login
        login_response = test_client.post(
            "/login",
            data={"student_uid": "test_teacher_006", "nickname": "테스트교사6"},
        )
        cookies = login_response.cookies

        # Try to access nonexistent scenario
        response = test_client.get("/scenarios/99999", cookies=cookies)

        # Verify 404
        assert response.status_code == 404

    async def test_unauthenticated_access_redirects(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_scenario: Scenario,
    ):
        """인증되지 않은 사용자는 로그인 페이지로 리디렉션."""
        # Access scenario without login
        response = test_client.get(
            f"/scenarios/{test_scenario.id}", follow_redirects=True
        )

        # Should redirect to login
        assert response.status_code == 200
        # Check if login page by looking for login form elements
        assert (
            "login" in response.text.lower()
            or "student_uid" in response.text
        )


class TestSessionIdConsistency:
    """Test that session_id remains consistent across operations."""

    async def test_session_id_used_in_subsequent_operations(
        self,
        test_client: TestClient,
        db_session: AsyncSession,
        test_scenario: Scenario,
    ):
        """생성된 세션 ID가 후속 작업에서 올바르게 사용되는지 확인."""
        # Login
        login_response = test_client.post(
            "/login",
            data={"student_uid": "test_teacher_007", "nickname": "테스트교사7"},
        )
        cookies = login_response.cookies

        # Access scenario to create session
        response = test_client.get(
            f"/scenarios/{test_scenario.id}", cookies=cookies
        )
        assert response.status_code == 200

        # Extract session_id from HTML
        js_pattern = r"window\.currentSessionId\s*=\s*(\d+)"
        match = re.search(js_pattern, response.text)
        assert match is not None
        session_id = int(match.group(1))

        # Verify we can access message updates for this session
        # (Testing message sending would require OpenAI API mock)
        updates_response = test_client.get(
            f"/sessions/{session_id}/messages/updates", cookies=cookies
        )

        # Should succeed (204 for no messages initially)
        assert updates_response.status_code == 204

        # Verify session exists in database with correct properties
        result = await db_session.execute(
            select(Session).where(Session.id == session_id)
        )
        db_session_obj = result.scalar_one()

        assert db_session_obj.scenario_id == test_scenario.id
        assert db_session_obj.ended_at is None

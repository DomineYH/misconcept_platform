"""Contract tests for authentication endpoints (T016)."""
import pytest
from fastapi.testclient import TestClient


class TestLoginEndpoint:
    """Test POST /login endpoint contract compliance."""

    def test_login_success_creates_session_cookie(
        self, test_client: TestClient
    ):
        """Verify successful login creates session cookie and redirects."""
        response = test_client.post(
            "/login",
            data={"student_uid": "student_001", "nickname": "김교사"},
            follow_redirects=False,
        )

        # Contract: 303 redirect to /scenarios
        assert response.status_code == 303
        assert response.headers["location"] == "/scenarios"

        # Contract: Set-Cookie header with HttpOnly, SameSite=Lax
        set_cookie = response.headers.get("set-cookie", "")
        assert "session_id=" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "SameSite=Lax" in set_cookie
        assert "Max-Age=28800" in set_cookie  # 8 hours

    def test_login_missing_fields_returns_400(
        self, test_client: TestClient
    ):
        """Verify missing required fields returns 400."""
        response = test_client.post(
            "/login", data={"student_uid": "student_001"}
        )

        assert response.status_code == 400
        assert "detail" in response.json()

    def test_login_invalid_student_uid_format_returns_400(
        self, test_client: TestClient
    ):
        """Verify invalid student_uid format returns 400."""
        response = test_client.post(
            "/login",
            data={
                "student_uid": "ab",  # Too short (min 3)
                "nickname": "김교사",
            },
        )

        assert response.status_code == 400
        assert "student_uid" in response.json()["detail"].lower()

    def test_login_invalid_credentials_returns_401(
        self, test_client: TestClient
    ):
        """Verify invalid credentials return 401."""
        # This will fail until we implement user authentication
        response = test_client.post(
            "/login",
            data={"student_uid": "nonexistent", "nickname": "invalid"},
        )

        assert response.status_code == 401
        assert "detail" in response.json()

    def test_get_login_returns_html_form(self, test_client: TestClient):
        """Verify GET /login returns HTML form."""
        response = test_client.get("/login")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestLogoutEndpoint:
    """Test POST /logout endpoint contract compliance."""

    def test_logout_clears_session_and_redirects(
        self, test_client: TestClient
    ):
        """Verify logout clears session cookie and redirects to login."""
        # First login to get session
        login_response = test_client.post(
            "/login",
            data={"student_uid": "student_001", "nickname": "김교사"},
        )
        assert login_response.status_code == 303

        # Now logout
        logout_response = test_client.post(
            "/logout", follow_redirects=False
        )

        # Contract: 303 redirect to /login
        assert logout_response.status_code == 303
        assert logout_response.headers["location"] == "/login"

        # Contract: Clear session cookie (Max-Age=0)
        set_cookie = logout_response.headers.get("set-cookie", "")
        assert "Max-Age=0" in set_cookie or "session_id=;" in set_cookie

"""Contract tests for authentication endpoints (T016)."""
import pytest
from fastapi.testclient import TestClient


class TestLoginEndpoint:
    """Test POST /login endpoint contract compliance."""

    def test_login_success_creates_session_cookie(
        self, test_client: TestClient
    ):
        """Verify successful login creates session cookie."""
        response = test_client.post(
            "/login",
            data={
                "username": "student_001",
                "password": "test1234",
            },
            follow_redirects=False,
        )

        # Contract: 303 redirect to /scenarios
        assert response.status_code == 303
        assert (
            response.headers["location"] == "/scenarios"
        )

        # Contract: Set-Cookie header
        set_cookie = response.headers.get(
            "set-cookie", ""
        )
        assert "session_id=" in set_cookie
        assert "httponly" in set_cookie.lower()
        assert "samesite=lax" in set_cookie.lower()
        assert "Max-Age=28800" in set_cookie  # 8 hours

    def test_login_missing_fields_returns_400(
        self, test_client: TestClient
    ):
        """Verify missing fields returns 422."""
        response = test_client.post(
            "/login", data={"username": "student_001"}
        )

        assert response.status_code == 422
        assert "detail" in response.json()

    def test_login_invalid_username_format_returns_400(
        self, test_client: TestClient
    ):
        """Verify invalid username format returns 422."""
        response = test_client.post(
            "/login",
            data={
                "username": "ab",  # Too short (min 3)
                "password": "test1234",
            },
        )

        assert response.status_code == 422
        assert "detail" in response.json()

    def test_login_invalid_credentials_returns_401(
        self, test_client: TestClient
    ):
        """Verify invalid credentials return 401."""
        response = test_client.post(
            "/login",
            data={
                "username": "nonexistent",
                "password": "invalidpw",
            },
            follow_redirects=False,
        )

        # 401 for invalid credentials (HTML response)
        assert response.status_code == 401
        assert (
            "text/html"
            in response.headers["content-type"]
        )

    def test_get_login_returns_html_form(
        self, test_client: TestClient
    ):
        """Verify GET /login returns HTML form."""
        response = test_client.get("/login")

        assert response.status_code == 200
        assert (
            "text/html"
            in response.headers["content-type"]
        )


class TestLogoutEndpoint:
    """Test POST /logout endpoint contract compliance."""

    def test_logout_clears_session_and_redirects(
        self, test_client: TestClient
    ):
        """Verify logout clears session and redirects."""
        # First login to get session
        login_response = test_client.post(
            "/login",
            data={
                "username": "student_001",
                "password": "test1234",
            },
            follow_redirects=False,
        )
        assert login_response.status_code == 303

        cookies = login_response.cookies

        # Now logout with session cookies
        logout_response = test_client.post(
            "/logout",
            cookies=cookies,
            follow_redirects=False,
        )

        # Contract: 303 redirect to /login
        assert logout_response.status_code == 303
        assert (
            logout_response.headers["location"]
            == "/login"
        )

        # Contract: Clear session cookie
        set_cookie = logout_response.headers.get(
            "set-cookie", ""
        )
        assert (
            "Max-Age=0" in set_cookie
            or "session_id=;" in set_cookie
            or "session_id=null" in set_cookie
        )

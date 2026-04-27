"""Contract tests for scenario endpoints (T017)."""

from fastapi.testclient import TestClient


class TestScenariosListEndpoint:
    """Test GET /scenarios endpoint contract compliance."""

    def test_scenarios_requires_authentication(self, test_client: TestClient):
        """Verify unauthenticated request redirects to login."""
        response = test_client.get("/scenarios", follow_redirects=False)

        # App redirects to /login (303) rather than returning 401
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_scenarios_returns_active_scenarios_html(
        self, test_client: TestClient
    ):
        """Verify authenticated request returns HTML with scenarios."""
        # First login to get session
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
            follow_redirects=False,
        )
        assert login_response.status_code == 303

        # Get session cookie
        cookies = login_response.cookies

        # Request scenarios with session
        response = test_client.get("/scenarios", cookies=cookies)

        # Contract: 200 with HTML content
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestScenarioDetailEndpoint:
    """Test GET /scenarios/{id} endpoint contract compliance."""

    def test_scenario_detail_requires_authentication(
        self, test_client: TestClient
    ):
        """Verify unauthenticated request redirects to login."""
        response = test_client.get("/scenarios/1", follow_redirects=False)

        # App redirects to /login (303) rather than returning 401
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_scenario_detail_returns_dialogue_interface(
        self, test_client: TestClient
    ):
        """Verify authenticated request returns dialogue interface."""
        # Login first
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
            follow_redirects=False,
        )
        cookies = login_response.cookies

        # Request scenario detail
        response = test_client.get("/scenarios/1", cookies=cookies)

        # Contract: 200 with HTML dialogue interface
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_scenario_detail_nonexistent_returns_404(
        self, test_client: TestClient
    ):
        """Verify nonexistent scenario returns 404."""
        # Login first
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
            follow_redirects=False,
        )
        cookies = login_response.cookies

        # Request nonexistent scenario
        response = test_client.get("/scenarios/99999", cookies=cookies)

        assert response.status_code == 404
        assert "detail" in response.json()

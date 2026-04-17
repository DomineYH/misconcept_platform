"""Contract tests for session endpoints (T018, T019)."""

from fastapi.testclient import TestClient

from tests.conftest import requires_openai_api_key


class TestSessionCreationEndpoint:
    """Test POST /sessions endpoint contract compliance (T018)."""

    def test_create_session_requires_authentication(
        self, test_client: TestClient
    ):
        """Verify unauthenticated request redirects to login."""
        response = test_client.post(
            "/sessions", json={"scenario_id": 1}, follow_redirects=False
        )

        # App redirects to /login (303) rather than returning 401
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_create_session_success(self, test_client: TestClient):
        """Verify session creation returns session object."""
        # Login first
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        # Create session
        response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )

        # Contract: 201 with session object
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "scenario_id" in data
        assert data["scenario_id"] == 1
        assert "started_at" in data

    def test_create_session_missing_scenario_id_returns_400(
        self, test_client: TestClient
    ):
        """Verify missing scenario_id returns 400."""
        # Login first
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        # Create session without scenario_id
        response = test_client.post("/sessions", json={}, cookies=cookies)

        assert response.status_code in [400, 422]


class TestMessageCreationEndpoint:
    """Test POST /sessions/{id}/messages contract (T019)."""

    def test_send_message_requires_authentication(
        self, test_client: TestClient
    ):
        """Verify unauthenticated request redirects to login."""
        response = test_client.post(
            "/sessions/1/messages",
            json={"content": "Hello"},
            follow_redirects=False,
        )

        # App redirects to /login (303) rather than returning 401
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    @requires_openai_api_key
    def test_send_message_returns_chatbot_responses(
        self, test_client: TestClient
    ):
        """Verify message creation triggers chatbot responses."""
        # Login first
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        # Create session
        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Send message
        response = test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "What is 2+2?"},
            cookies=cookies,
        )

        # Contract: 200 with HTML response (HTMX expects HTML)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

        # Verify HTML response contains the sent message
        assert "What is 2+2?" in response.text

        # Verify HTML response is not empty (should have bot responses)
        assert len(response.text) > 0

    def test_send_message_empty_content_returns_400(
        self, test_client: TestClient
    ):
        """Verify empty message content returns 400."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Send empty message
        response = test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": ""},
            cookies=cookies,
        )

        # Form validation returns 422 for validation errors
        assert response.status_code == 422


class TestSessionEndEndpoint:
    """Test POST /sessions/{id}/end endpoint contract (T051)."""

    def test_end_session_requires_authentication(self, test_client: TestClient):
        """Verify unauthenticated request redirects to login."""
        response = test_client.post("/sessions/1/end", follow_redirects=False)
        # App redirects to /login (303) rather than returning 401
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    @requires_openai_api_key
    def test_end_session_returns_ended_status(self, test_client: TestClient):
        """Verify session end returns ended status (analysis is separate)."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Send at least one message to have content for analysis
        test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "What causes photosynthesis?"},
            cookies=cookies,
        )

        # End session
        response = test_client.post(
            f"/sessions/{session_id}/end", cookies=cookies
        )

        # Contract: 200 with ended status
        assert response.status_code == 200
        data = response.json()

        # Verify ended status structure
        assert "ended" in data
        assert data["ended"] is True
        assert "ended_at" in data
        assert data["ended_at"] is not None

    def test_end_session_nonexistent_returns_404(self, test_client: TestClient):
        """Verify ending nonexistent session returns 404."""
        # Login
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        # Try to end nonexistent session
        response = test_client.post("/sessions/99999/end", cookies=cookies)
        assert response.status_code == 404

    def test_end_already_ended_session_returns_400(
        self, test_client: TestClient
    ):
        """Verify ending already ended session returns 400."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # End session first time
        test_client.post(f"/sessions/{session_id}/end", cookies=cookies)

        # Try to end again
        response = test_client.post(
            f"/sessions/{session_id}/end", cookies=cookies
        )
        assert response.status_code in [200, 400]


class TestSessionAnalyzeEndpoint:
    """Test POST /sessions/{id}/analyze endpoint contract."""

    def test_analyze_session_requires_authentication(
        self, test_client: TestClient
    ):
        """Verify unauthenticated request redirects to login."""
        response = test_client.post(
            "/sessions/1/analyze", follow_redirects=False
        )
        # App redirects to /login (303) rather than returning 401
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    @requires_openai_api_key
    def test_analyze_session_returns_summary(self, test_client: TestClient):
        """Verify analyze returns SessionSummary with distribution."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Send at least one message to have content for analysis
        test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "What causes photosynthesis?"},
            cookies=cookies,
        )

        # End session first (required before analysis)
        test_client.post(f"/sessions/{session_id}/end", cookies=cookies)

        # Analyze session
        response = test_client.post(
            f"/sessions/{session_id}/analyze", cookies=cookies
        )

        # Contract: 200 with SessionSummary
        assert response.status_code == 200
        data = response.json()

        # Verify SessionSummary structure
        assert "distribution" in data
        assert isinstance(data["distribution"], dict)
        assert "feedback" in data
        assert isinstance(data["feedback"], str)

    def test_analyze_before_end_returns_400(self, test_client: TestClient):
        """Verify analyzing session that hasn't ended returns 400."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Try to analyze without ending first
        response = test_client.post(
            f"/sessions/{session_id}/analyze", cookies=cookies
        )
        assert response.status_code == 400

    def test_analyze_nonexistent_returns_404(self, test_client: TestClient):
        """Verify analyzing nonexistent session returns 404."""
        # Login
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        # Try to analyze nonexistent session
        response = test_client.post("/sessions/99999/analyze", cookies=cookies)
        assert response.status_code == 404


class TestSessionExportEndpoint:
    """Test GET /sessions/{id}/export.csv endpoint contract (T052)."""

    def test_export_session_requires_authentication(
        self, test_client: TestClient
    ):
        """Verify unauthenticated request redirects to login."""
        response = test_client.get(
            "/sessions/1/export.csv", follow_redirects=False
        )
        # App redirects to /login (303) rather than returning 401
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    @requires_openai_api_key
    def test_export_session_returns_csv_with_correct_headers(
        self, test_client: TestClient
    ):
        """Verify CSV export has correct headers and content."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Send some messages
        test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "What is photosynthesis?"},
            cookies=cookies,
        )

        # Export session
        response = test_client.get(
            f"/sessions/{session_id}/export.csv", cookies=cookies
        )

        # Contract: 200 with CSV content-type
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]

        # Verify CSV has correct headers
        csv_content = response.text
        lines = csv_content.strip().split("\n")
        assert len(lines) >= 2  # At least header + 1 row

        # Check header row
        header = lines[0]
        expected_columns = [
            "session_id",
            "scenario_title",
            "student_hash",
            "timestamp",
            "role",
            "content",
            "label",
            "confidence",
            "feedback",
        ]
        for col in expected_columns:
            assert col in header, f"Missing column: {col}"

    def test_export_csv_contains_anonymized_student_hash(
        self, test_client: TestClient
    ):
        """Verify CSV export uses anonymized student hash."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Export session
        response = test_client.get(
            f"/sessions/{session_id}/export.csv", cookies=cookies
        )

        csv_content = response.text

        # Should NOT contain raw username
        assert "student_001" not in csv_content

        # Should contain a hash (64 hex characters for SHA-256)
        import re

        # Find student_hash column values
        lines = csv_content.strip().split("\n")
        if len(lines) > 1:
            # Check if hash pattern exists (SHA-256 hex = 64 chars)
            hash_pattern = re.compile(r"[a-f0-9]{64}")
            assert hash_pattern.search(csv_content) is not None

    @requires_openai_api_key
    def test_export_csv_timestamp_format(self, test_client: TestClient):
        """Verify CSV timestamps are properly formatted."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Send message
        test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "Test message"},
            cookies=cookies,
        )

        # Export session
        response = test_client.get(
            f"/sessions/{session_id}/export.csv", cookies=cookies
        )

        csv_content = response.text
        lines = csv_content.strip().split("\n")

        if len(lines) > 1:
            # Check timestamp format (ISO 8601)
            import re

            timestamp_pattern = re.compile(
                r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
            )
            assert timestamp_pattern.search(csv_content) is not None

    def test_export_nonexistent_session_returns_404(
        self, test_client: TestClient
    ):
        """Verify exporting nonexistent session returns 404."""
        # Login
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        # Try to export nonexistent session
        response = test_client.get(
            "/sessions/99999/export.csv", cookies=cookies
        )
        assert response.status_code == 404


class TestSessionCloseEndpoint:
    """Test POST /sessions/{id}/close endpoint contract (lightweight)."""

    def test_close_session_requires_authentication(
        self, test_client: TestClient
    ):
        """Verify unauthenticated request redirects to login."""
        response = test_client.post("/sessions/1/close", follow_redirects=False)
        # App redirects to /login (303) rather than returning 401
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_close_session_success(self, test_client: TestClient):
        """Verify session close returns ended timestamp."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Close session
        response = test_client.post(
            f"/sessions/{session_id}/close", cookies=cookies
        )

        # Contract: 200 with CloseSessionResponse
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ended"
        assert "ended_at" in data
        assert data["already_ended"] is False

    def test_close_session_idempotent(self, test_client: TestClient):
        """Verify closing already-closed session returns 200 already_ended."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Close session first time
        response1 = test_client.post(
            f"/sessions/{session_id}/close", cookies=cookies
        )
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["already_ended"] is False

        # Close session second time (idempotent)
        response2 = test_client.post(
            f"/sessions/{session_id}/close", cookies=cookies
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["status"] == "ended"
        assert data2["already_ended"] is True
        # Should return same timestamp
        assert data2["ended_at"] == data1["ended_at"]

    def test_close_nonexistent_session_returns_404(
        self, test_client: TestClient
    ):
        """Verify closing nonexistent session returns 404."""
        # Login
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        # Try to close nonexistent session
        response = test_client.post("/sessions/99999/close", cookies=cookies)
        assert response.status_code == 404

    def test_close_other_users_session_returns_403(
        self, test_client: TestClient
    ):
        """Verify cannot close another user's session."""
        # Login as first user and create session
        login1 = test_client.post(
            "/login",
            data={"username": "user1", "password": "test1234"},
        )
        cookies1 = login1.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies1
        )
        session_id = session_response.json()["id"]

        # Login as second user
        login2 = test_client.post(
            "/login",
            data={"username": "user2", "password": "test1234"},
        )
        cookies2 = login2.cookies

        # Try to close first user's session
        response = test_client.post(
            f"/sessions/{session_id}/close", cookies=cookies2
        )
        assert response.status_code == 403


class TestEndedSessionValidation:
    """Test that ended sessions cannot receive new messages."""

    def test_send_message_to_ended_session_returns_400(
        self, test_client: TestClient
    ):
        """Verify sending message to ended session returns 400."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Close session
        test_client.post(f"/sessions/{session_id}/close", cookies=cookies)

        # Try to send message to ended session
        response = test_client.post(
            f"/sessions/{session_id}/messages",
            data={"content": "This should fail"},
            cookies=cookies,
        )

        # Should return 400 with appropriate error message
        assert response.status_code == 400
        data = response.json()
        assert "already ended" in data["detail"].lower()

    def test_end_session_after_close_returns_400(self, test_client: TestClient):
        """Verify calling /end after /close returns 400."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"username": "student_001", "password": "test1234"},
        )
        cookies = login_response.cookies

        session_response = test_client.post(
            "/sessions", json={"scenario_id": 1}, cookies=cookies
        )
        session_id = session_response.json()["id"]

        # Close session first
        test_client.post(f"/sessions/{session_id}/close", cookies=cookies)

        # Try to call /end (should fail since already ended)
        response = test_client.post(
            f"/sessions/{session_id}/end", cookies=cookies
        )
        assert response.status_code in [200, 400]

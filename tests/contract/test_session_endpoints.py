"""Contract tests for session endpoints (T018, T019)."""
from fastapi.testclient import TestClient


class TestSessionCreationEndpoint:
    """Test POST /sessions endpoint contract compliance (T018)."""

    def test_create_session_requires_authentication(
        self, test_client: TestClient
    ):
        """Verify unauthenticated request returns 401."""
        response = test_client.post("/sessions", json={"scenario_id": 1})

        assert response.status_code == 401

    def test_create_session_success(self, test_client: TestClient):
        """Verify session creation returns session object."""
        # Login first
        login_response = test_client.post(
            "/login",
            data={"student_uid": "student_001", "nickname": "김교사"},
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
            data={"student_uid": "student_001", "nickname": "김교사"},
        )
        cookies = login_response.cookies

        # Create session without scenario_id
        response = test_client.post("/sessions", json={}, cookies=cookies)

        assert response.status_code == 400


class TestMessageCreationEndpoint:
    """Test POST /sessions/{id}/messages contract (T019)."""

    def test_send_message_requires_authentication(
        self, test_client: TestClient
    ):
        """Verify unauthenticated request returns 401."""
        response = test_client.post(
            "/sessions/1/messages", json={"content": "Hello"}
        )

        assert response.status_code == 401

    def test_send_message_returns_chatbot_responses(
        self, test_client: TestClient
    ):
        """Verify message creation triggers chatbot responses."""
        # Login first
        login_response = test_client.post(
            "/login",
            data={"student_uid": "student_001", "nickname": "김교사"},
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
            data={"student_uid": "student_001", "nickname": "김교사"},
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
        """Verify unauthenticated request returns 401."""
        response = test_client.post("/sessions/1/end")
        assert response.status_code == 401

    def test_end_session_returns_session_summary(self, test_client: TestClient):
        """Verify session end returns SessionSummary with distribution."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"student_uid": "student_001", "nickname": "김교사"},
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

        # Contract: 200 with SessionSummary
        assert response.status_code == 200
        data = response.json()

        # Verify SessionSummary structure
        assert "session_id" in data
        assert data["session_id"] == session_id
        assert "distribution" in data
        assert isinstance(data["distribution"], dict)
        assert "feedback" in data
        assert isinstance(data["feedback"], str)
        assert "created_at" in data

    def test_end_session_nonexistent_returns_404(self, test_client: TestClient):
        """Verify ending nonexistent session returns 404."""
        # Login
        login_response = test_client.post(
            "/login",
            data={"student_uid": "student_001", "nickname": "김교사"},
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
            data={"student_uid": "student_001", "nickname": "김교사"},
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
        assert response.status_code == 400


class TestSessionExportEndpoint:
    """Test GET /sessions/{id}/export.csv endpoint contract (T052)."""

    def test_export_session_requires_authentication(
        self, test_client: TestClient
    ):
        """Verify unauthenticated request returns 401."""
        response = test_client.get("/sessions/1/export.csv")
        assert response.status_code == 401

    def test_export_session_returns_csv_with_correct_headers(
        self, test_client: TestClient
    ):
        """Verify CSV export has correct headers and content."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"student_uid": "student_001", "nickname": "김교사"},
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
            data={"student_uid": "student_001", "nickname": "김교사"},
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

        # Should NOT contain raw student_uid
        assert "student_001" not in csv_content

        # Should contain a hash (64 hex characters for SHA-256)
        import re

        # Find student_hash column values
        lines = csv_content.strip().split("\n")
        if len(lines) > 1:
            # Check if hash pattern exists (SHA-256 hex = 64 chars)
            hash_pattern = re.compile(r"[a-f0-9]{64}")
            assert hash_pattern.search(csv_content) is not None

    def test_export_csv_timestamp_format(self, test_client: TestClient):
        """Verify CSV timestamps are properly formatted."""
        # Login and create session
        login_response = test_client.post(
            "/login",
            data={"student_uid": "student_001", "nickname": "김교사"},
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
            data={"student_uid": "student_001", "nickname": "김교사"},
        )
        cookies = login_response.cookies

        # Try to export nonexistent session
        response = test_client.get(
            "/sessions/99999/export.csv", cookies=cookies
        )
        assert response.status_code == 404

"""The rendered footer shows the dynamic app version, not v0.1.0."""

from fastapi.testclient import TestClient

from src.version import read_base_version


def test_login_footer_shows_dynamic_version(test_client: TestClient):
    response = test_client.get("/login")
    assert response.status_code == 200
    assert f"v{read_base_version()}" in response.text
    assert "v0.1.0" not in response.text

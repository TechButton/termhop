"""Health metadata lets operators confirm a coordinated protocol cutover."""
from fastapi.testclient import TestClient

from relay.main import create_app


def test_health_reports_protocol_and_release(monkeypatch):
    monkeypatch.setenv("PROTOCOL_VERSION", "2")
    monkeypatch.setenv("TERMHOP_RELEASE", "test-commit")
    with TestClient(create_app()) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "protocol_version": 2,
        "release": "test-commit",
    }

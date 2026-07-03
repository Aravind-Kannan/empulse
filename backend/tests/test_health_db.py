"""Health endpoint tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)


def test_health_db_ok(client):
    response = client.get("/health/db")
    assert response.status_code == 200
    body = response.json()
    assert body["postgres"] == "ok"
    assert body["environment"] in ("development", "production")


def test_health_db_unavailable(client):
    with patch(
        "app.routes.health.check_database_connection",
        return_value=(False, "connection refused"),
    ):
        response = client.get("/health/db")

    assert response.status_code == 503
    body = response.json()
    assert body["postgres"] == "unavailable"
    assert body["detail"] == "connection refused"

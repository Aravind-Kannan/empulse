"""Exit handover Slack DM delivery tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.schemas.integrations import SlackConfigRequest
from app.services.integration_config_store import save_slack_config
from app.tenancy import TENANT_HEADER

from tests.conftest import add_employee


@pytest.fixture()
def client(db):
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_send_handover_slack_dm_success(client, db, tenant):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-slack-exit",
        name="Slack Exit Engineer",
        email="slack-exit@acme.com",
    )
    save_slack_config(
        db,
        tenant.id,
        SlackConfigRequest(
            bot_token="xoxb-test-token",
            workspace_url="https://acme.slack.com",
        ),
    )
    from app.models.operational import EmployeeIdentity

    db.add(
        EmployeeIdentity(
            tenant_id=tenant.id,
            employee_id=employee.id,
            provider="slack",
            provider_username_or_id="U123HANDOVER",
            confidence="confirmed",
        )
    )
    db.commit()

    handover_mock = MagicMock()
    handover_mock.employee_id = employee.id
    handover_mock.employee_name = employee.name
    handover_mock.markdown = "# Handover\n\nBody"
    handover_mock.filename = "handover-slack-exit-engineer.md"

    with patch(
        "app.services.exit_slack_delivery.build_handover_markdown",
        new_callable=AsyncMock,
        return_value=handover_mock,
    ), patch(
        "app.services.exit_slack_delivery.open_dm_channel",
        return_value="D999",
    ) as open_dm, patch(
        "app.services.exit_slack_delivery.upload_markdown_to_channel",
        return_value="F123",
    ) as upload:
        response = client.post(
            f"/api/exit/handover/send-slack?id={employee.id}",
            headers={TENANT_HEADER: str(tenant.id)},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["slack_user_id"] == "U123HANDOVER"
    assert payload["channel_id"] == "D999"
    assert payload["file_id"] == "F123"
    open_dm.assert_called_once_with("xoxb-test-token", "U123HANDOVER")
    upload.assert_called_once()
    assert upload.call_args.kwargs["channel_id"] == "D999"
    assert upload.call_args.kwargs["filename"].endswith(".md")

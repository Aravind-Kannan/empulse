"""GitHub credential validation tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.integration_validate import validate_github_credentials


def test_validate_github_credentials_success():
    repo_response = MagicMock()
    repo_response.status_code = 200
    repo_response.json.return_value = {
        "full_name": "acme/platform",
        "default_branch": "main",
    }

    with patch(
        "app.services.integration_validate.requests.get",
        return_value=repo_response,
    ):
        message = validate_github_credentials(
            "ghp_test_token",
            repository_urls=["https://github.com/acme/platform"],
            branch_targets=["main"],
        )

    assert "acme/platform" in message


def test_validate_github_credentials_repo_not_found():
    repo_response = MagicMock()
    repo_response.status_code = 404
    repo_response.text = "Not Found"

    with patch(
        "app.services.integration_validate.requests.get",
        return_value=repo_response,
    ):
        with pytest.raises(ValueError, match="not found or this token cannot access"):
            validate_github_credentials(
                "ghp_test_token",
                repository_urls=["https://github.com/acme/private-repo"],
            )


def test_validate_github_credentials_missing_branch():
    repo_response = MagicMock()
    repo_response.status_code = 200
    repo_response.json.return_value = {
        "full_name": "acme/platform",
        "default_branch": "main",
    }
    branch_response = MagicMock()
    branch_response.status_code = 404
    branch_response.text = "Branch not found"

    with patch(
        "app.services.integration_validate.requests.get",
        side_effect=[repo_response, branch_response],
    ):
        with pytest.raises(ValueError, match="Branch 'develop' was not found"):
            validate_github_credentials(
                "ghp_test_token",
                repository_urls=["https://github.com/acme/platform"],
                branch_targets=["develop"],
            )

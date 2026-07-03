"""GitHub file-content ingest flag tests."""

from __future__ import annotations

from unittest.mock import patch

from app.schemas.integrations import GitHubConfigRequest
from app.services.github_code import github_ingest_file_content_enabled


def test_github_ingest_file_content_disabled_by_default():
    config = GitHubConfigRequest(
        repository_url="https://github.com/acme/repo",
        personal_access_token="token",
    )
    with patch("app.config.get_settings") as settings_mock:
        settings_mock.return_value.github_ingest_file_content = False
        assert github_ingest_file_content_enabled(config) is False


def test_github_ingest_file_content_per_integration_override():
    config = GitHubConfigRequest(
        repository_url="https://github.com/acme/repo",
        personal_access_token="token",
        ingest_file_content=True,
    )
    with patch("app.config.get_settings") as settings_mock:
        settings_mock.return_value.github_ingest_file_content = False
        assert github_ingest_file_content_enabled(config) is True


def test_github_ingest_file_content_env_override():
    config = GitHubConfigRequest(
        repository_url="https://github.com/acme/repo",
        personal_access_token="token",
    )
    with patch("app.config.get_settings") as settings_mock:
        settings_mock.return_value.github_ingest_file_content = True
        assert github_ingest_file_content_enabled(config) is True

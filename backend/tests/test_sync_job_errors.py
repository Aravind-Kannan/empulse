"""Tests for sync job user-facing error messages."""

from __future__ import annotations

from app.services.sync_job_errors import format_sync_job_error


def test_loop_mismatch_is_friendly():
    raw = (
        "Task <Task pending name='Task-761' coro=<_execute_integration_sync_job() "
        "running at ...> got Future <Future pending> attached to a different loop"
    )
    message = format_sync_job_error(raw)
    assert "different loop" not in message
    assert "Restart the backend" in message


def test_short_errors_pass_through():
    assert format_sync_job_error("GitHub integration is not configured.") == (
        "GitHub integration is not configured."
    )

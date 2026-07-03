"""Investigation reference noise filtering."""

from app.schemas.investigation import InvestigationReference
from app.services.investigation import (
    _filter_investigation_references,
    _is_placeholder_reference_url,
    _is_reference_noise_text,
)


def test_reference_noise_detects_notion_metadata_and_slack_warnings():
    assert _is_reference_noise_text(
        "Notion page 'Weekly To-do List' (runbook) last edited 2026-06-30 "
        "documents unlinked, authored by unknown."
    )
    assert _is_reference_noise_text(
        "Warnings: Could not reach Slack API: HTTPSConnectionPool(host='slack.com'): "
        "Read timed out."
    )


def test_filter_investigation_references_drops_noise_and_placeholders():
    refs = _filter_investigation_references(
        [
            InvestigationReference(
                id="n1",
                type="notion",
                title="Notion page 'Weekly To-do List' (runbook) last edited 2026-06-30",
                url="notion://page",
                snippet="documents unlinked, authored by unknown.",
            ),
            InvestigationReference(
                id="s1",
                type="slack",
                title="Warnings: Could not reach Slack API",
                url="slack://thread",
                snippet="Read timed out.",
            ),
            InvestigationReference(
                id="j1",
                type="jira",
                title="SCRUM-42: Checkout 500s",
                url="https://jira.example.com/browse/SCRUM-42",
                snippet="Bug · High · Open",
            ),
        ]
    )
    assert len(refs) == 1
    assert refs[0].id == "j1"


def test_placeholder_reference_urls():
    assert _is_placeholder_reference_url("notion://page") is True
    assert _is_placeholder_reference_url("slack://thread") is True
    assert (
        _is_placeholder_reference_url("https://www.notion.so/acme/runbook") is False
    )

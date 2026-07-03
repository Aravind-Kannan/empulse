from app.schemas.investigation import IncidentSummary, InvestigationReference
from app.services.investigation import (
    _finalize_jira_references,
    _find_related_jira_tickets,
    _workaround_from_resolved_jira,
)
from app.services.jira_types import JiraIssueActivity


def _issue(
    key: str,
    summary: str,
    *,
    status: str = "Open",
    status_category: str = "indeterminate",
    done: bool = False,
) -> JiraIssueActivity:
    category = "done" if done else status_category
    st = "Closed" if done else status
    return JiraIssueActivity(
        issue_key=key,
        issue_type="Bug",
        priority="High",
        status=st,
        status_category=category,
        project_key="ENG",
        summary=summary,
        issue_url=f"https://jira.example/browse/{key}",
    )


def test_find_related_jira_by_title_overlap(monkeypatch) -> None:
    issues = [
        _issue("ENG-10", "Identity mapping fails for SAML users"),
        _issue("ENG-11", "Identity mapping bug in OAuth callback"),
        _issue(
            "ENG-12",
            "Identity mapping resolution: clear cache, re-sync IdP metadata, validate group claims.",
            done=True,
        ),
        _issue("ENG-99", "Payment gateway timeout during checkout"),
    ]
    monkeypatch.setattr(
        "app.services.investigation.get_cached_jira_issues",
        lambda: issues,
    )

    incident = IncidentSummary(
        id="jira:ENG-10",
        title="Identity mapping bug for enterprise SSO",
        status="Open",
        system_scope="Auth",
        jira_id="ENG-10",
        updated_at="2026-07-01T10:00:00Z",
        source="jira",
    )

    related = _find_related_jira_tickets(incident)
    keys = {ref.title.split(":")[0] for ref in related}
    assert "ENG-11" in keys
    assert "ENG-12" in keys
    assert "ENG-99" not in keys


def test_workaround_from_resolved_related_jira(monkeypatch) -> None:
    issues = [
        _issue("ENG-10", "Identity mapping fails for SAML users"),
        _issue(
            "ENG-12",
            "Identity mapping resolution: clear cache, re-sync IdP metadata, validate group claims.",
            done=True,
        ),
    ]
    monkeypatch.setattr(
        "app.services.investigation.get_cached_jira_issues",
        lambda: issues,
    )

    incident = IncidentSummary(
        id="jira:ENG-10",
        title="Identity mapping bug for enterprise SSO",
        status="Open",
        system_scope="Auth",
        jira_id="ENG-10",
        updated_at="2026-07-01T10:00:00Z",
        source="jira",
    )

    workaround = _workaround_from_resolved_jira(incident)
    assert workaround is not None
    assert "ENG-12" in workaround
    assert "clear cache" in workaround.lower()


def test_finalize_jira_references_dedupes_and_excludes_active() -> None:
    refs = [
        InvestigationReference(
            id="jira-ENG-10",
            type="jira",
            title="Jira ENG-10",
            url="jira://ENG-10",
            snippet="Jira ticket ENG-10 linked to active incident investigation.",
        ),
        InvestigationReference(
            id="jira-live-ENG-10",
            type="jira",
            title="ENG-10: Identity mapping fails",
            url="https://jira.example/browse/ENG-10",
            snippet="Bug · High · Open",
        ),
        InvestigationReference(
            id="jira-related-ENG-11",
            type="jira",
            title="ENG-11: Identity mapping bug in OAuth callback",
            url="https://jira.example/browse/ENG-11",
            snippet="Bug · High · Open",
        ),
        InvestigationReference(
            id="jira-ENG-11",
            type="jira",
            title="Jira ENG-11",
            url="jira://ENG-11",
            snippet="Duplicate key with different url",
        ),
    ]

    finalized = _finalize_jira_references(refs, active_jira_id="ENG-10")
    keys = {_jira_key_from_title(ref.title) for ref in finalized}

    assert "ENG-10" not in keys
    assert "ENG-11" in keys
    assert len(finalized) == 1


def _jira_key_from_title(title: str) -> str:
    return title.split(":")[0].strip()

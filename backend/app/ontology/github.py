"""GitHub → canonical ontology normalizers."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.ontology.canonical import (
    CanonicalChangeEvent,
    CanonicalCodeArtifact,
    CanonicalComponentRef,
    CanonicalPersonRef,
)
from app.schemas.integrations import GitHubConfigRequest
from app.services.github_doa import dominant_blame_author_login
from app.services.github_types import GitHubPullRequestActivity
from app.services.identity_resolver import resolve_author_employee_id


def normalize_github_code_snapshot(
    snap,
    *,
    db: Session,
    tenant_id: uuid.UUID,
    components_by_id: dict,
) -> CanonicalCodeArtifact:
    component_ref = None
    if snap.component_id and snap.component_id in components_by_id:
        comp = components_by_id[snap.component_id]
        component_ref = CanonicalComponentRef(
            component_id=snap.component_id,
            name=getattr(comp, "name", ""),
        )

    blame_author = None
    top_author = dominant_blame_author_login(snap)
    if top_author:
        employee_id = resolve_author_employee_id(
            db,
            tenant_id,
            "github",
            f"gh-{top_author}",
            quarantine_event_type="github_blame",
            quarantine_payload={"file_path": snap.file_path, "ref": snap.ref},
        )
        blame_author = CanonicalPersonRef(
            employee_id=employee_id,
            provider="github",
            provider_user_id=f"gh-{top_author}",
            display_name=top_author,
        )

    return CanonicalCodeArtifact(
        source="github",
        repository_url=snap.repository_url,
        file_path=snap.file_path,
        ref=snap.ref,
        blob_sha=snap.content_sha,
        content_preview=snap.content_preview,
        patch_preview=snap.patch_preview,
        blame_summary=snap.blame_summary(),
        primary_authors=tuple(snap.primary_authors[:8]),
        component=component_ref,
        blame_author=blame_author,
    )


def normalize_github_pr_file_change(
    activity: GitHubPullRequestActivity,
    file_change,
    *,
    config: GitHubConfigRequest,
    db: Session,
    tenant_id: uuid.UUID,
    components_by_id: dict,
) -> CanonicalChangeEvent | None:
    component_ref = None
    if file_change.component_id:
        component = components_by_id.get(file_change.component_id)
        component_ref = CanonicalComponentRef(
            component_id=file_change.component_id,
            name=getattr(component, "name", "") if component else file_change.component_id,
        )

    author_employee_id = resolve_author_employee_id(
        db,
        tenant_id,
        "github",
        activity.author_provider_user_id,
        demo_fallback_employee_id=None,
        quarantine_event_type="github_pr",
        quarantine_payload={
            "pr_number": activity.pr_number,
            "commit_sha": activity.commit_sha,
            "pr_url": activity.pr_url,
        },
    )
    author = CanonicalPersonRef(
        employee_id=author_employee_id,
        provider="github",
        provider_user_id=activity.author_provider_user_id,
        display_name=activity.author_login,
    )

    return CanonicalChangeEvent(
        source="github",
        event_kind="pull_request",
        repository_url=config.repository_url,
        pr_number=activity.pr_number,
        commit_sha=activity.commit_sha,
        branch=activity.branch or config.branch_target,
        file_path=file_change.path,
        loc_added=file_change.loc_added,
        loc_removed=file_change.loc_removed,
        pr_url=activity.pr_url,
        author=author,
        component=component_ref,
        properties={
            "loc_added": file_change.loc_added,
            "loc_removed": file_change.loc_removed,
            "pr_url": activity.pr_url,
            "file_path": file_change.path,
        },
    )

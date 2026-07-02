"""Tests for GitHub code + blame snapshot collection."""

from __future__ import annotations

from app.schemas.integrations import GitHubConfigRequest
from app.services.github_code import collect_github_code_snapshots
from app.services.github_types import GitHubFileChange, GitHubPullRequestActivity


def _activity(path: str = "src/api/handler.py", component_id: str = "comp-api") -> GitHubPullRequestActivity:
    return GitHubPullRequestActivity(
        pr_number=42,
        commit_sha="deadbeef1234567890",
        merge_commit_sha="deadbeef1234567890",
        branch="main",
        author_login="benrivera",
        author_provider_user_id="gh-benrivera",
        author_type="User",
        pr_url="https://github.com/acme/repo/pull/42",
        merged_at="2025-01-15T12:00:00Z",
        files=[
            GitHubFileChange(
                path=path,
                loc_added=12,
                loc_removed=3,
                component_id=component_id,
                status="modified",
                patch_preview="@@ -1,3 +1,5 @@\n+def new_handler():\n+    pass",
                blob_sha="sha123",
            )
        ],
    )


def test_collect_fixture_code_snapshots():
    config = GitHubConfigRequest(
        repository_url="https://github.com/acme/repo",
        personal_access_token="",
        branch_target="main",
        path_component_map={"src/api/": "comp-api"},
        default_component_id=None,
    )
    snapshots = collect_github_code_snapshots(
        config,
        [_activity()],
        use_fixture=True,
    )
    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap.file_path == "src/api/handler.py"
    assert snap.content_preview
    assert snap.blame_ranges
    assert snap.primary_authors
    assert "new_handler" in snap.patch_preview or snap.patch_preview

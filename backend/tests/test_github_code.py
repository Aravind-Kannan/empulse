"""Tests for GitHub code + blame snapshot collection."""

from __future__ import annotations

from app.schemas.integrations import GitHubConfigRequest
from app.services.github_code import collect_github_code_snapshots, fetch_blame_ranges
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
        ingest_file_content=True,
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


def test_collect_code_snapshots_skips_content_by_default():
    config = GitHubConfigRequest(
        repository_url="https://github.com/acme/repo",
        personal_access_token="",
        branch_target="main",
        path_component_map={"src/api/": "comp-api"},
    )
    snapshots = collect_github_code_snapshots(
        config,
        [_activity()],
        use_fixture=True,
    )
    assert len(snapshots) == 1
    assert snapshots[0].content_preview == ""
    assert snapshots[0].patch_preview == ""
    assert snapshots[0].file_path == "src/api/handler.py"
    assert snapshots[0].blame_ranges
    assert snapshots[0].primary_authors


def test_fetch_blame_ranges_parses_commit_blame(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "data": {
                    "repository": {
                        "object": {
                            "blame": {
                                "ranges": [
                                    {
                                        "startingLine": 1,
                                        "endingLine": 10,
                                        "commit": {
                                            "oid": "abc123def",
                                            "author": {
                                                "user": {"login": "dev1"},
                                                "name": "Dev One",
                                                "email": "dev@example.com",
                                            },
                                        },
                                    }
                                ]
                            }
                        }
                    }
                }
            }

    monkeypatch.setattr(
        "app.services.github_code.requests.post",
        lambda *args, **kwargs: FakeResponse(),
    )
    ranges = fetch_blame_ranges(
        "token",
        "acme",
        "repo",
        "src/main.py",
        "main",
        max_ranges=None,
    )
    assert len(ranges) == 1
    assert ranges[0].author_login == "dev1"
    assert ranges[0].starting_line == 1
    assert ranges[0].ending_line == 10

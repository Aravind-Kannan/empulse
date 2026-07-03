"""Full-repository GitHub ingestion with file contents and paginated blame."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import requests

from sqlalchemy.orm import Session

from app.schemas.integrations import GitHubConfigRequest
from app.services.github_client import (
    GITHUB_API,
    GitHubClientError,
    _headers,
    list_repository_branches,
    parse_repository_url,
)
from app.services.github_code import (
    GitHubCodeFileSnapshot,
    MAX_PATCH_CHARS,
    _fetch_file_content,
    _fixture_code_snapshot,
    fetch_blame_ranges,
)
from app.services.github_doa import should_exclude_repo_path
from app.services.github_path_mapper import map_path_to_component
from app.services.integration_config_store import get_github_config, record_integration_sync
from app.services.integration_sync import (
    _load_org_context,
    analyze_github_code_payload,
)
from app.services.integration_telemetry import mark_sync_completed
from app.services.sync_job_errors import SyncJobCancelled
from app.services.sync_ledger import (
    count_graph_edges,
    plan_sync_ingest,
    record_synced_items,
)
from app.services.tenant_cognee import tenant_add_data_points
from app.tenancy import tenant_dataset_name

logger = logging.getLogger(__name__)

FULL_REPO_BATCH_SIZE = 25
MAX_FILES_PER_REPO = 2_000
MAX_TREE_FILE_BYTES = 1_048_576

FIXTURE_TREE_PATHS = (
    "backend/app/main.py",
    "backend/app/services/github_code.py",
    "frontend/src/lib/integrations.ts",
    "README.md",
)

FIXTURE_BRANCHES = ("main", "develop")

FIXTURE_BRANCH_DIFF_PATHS: dict[str, list[str]] = {
    "develop": ["frontend/src/lib/integrations.ts"],
}

CancelCheck = Callable[[], None]


@dataclass
class RepoTreeFile:
    path: str
    blob_sha: str
    size: int
    patch_preview: str = ""


@dataclass
class BranchSyncPlan:
    branch: str
    ref_sha: str
    tree_files: list[RepoTreeFile]
    sync_mode: Literal["full", "diff"] = "full"
    base_branch: str | None = None


ProgressCallback = Callable[[str, str, dict[str, int | str] | None], None]


def _normalize_repo_url(repository_url: str) -> str:
    return repository_url.strip().rstrip("/")


def _progress_stats(
    *,
    branches_total: int,
    branches_completed: int,
    current_branch: str,
    files_total: int,
    files_completed: int,
) -> dict[str, int | str]:
    return {
        "branches_total": branches_total,
        "branches_completed": branches_completed,
        "current_branch": current_branch,
        "files_total": files_total,
        "files_completed": files_completed,
    }


def _progress_message(stats: dict[str, int | str]) -> str:
    branches_total = int(stats["branches_total"])
    branches_completed = int(stats["branches_completed"])
    files_total = int(stats["files_total"])
    files_completed = int(stats["files_completed"])
    current_branch = str(stats["current_branch"])

    branch_part = (
        f"branch {branches_completed + 1}/{branches_total}: {current_branch}"
        if branches_total > 1
        else f"branch {current_branch}"
    )
    return f"Syncing {files_completed}/{files_total} files · {branch_part}"


def resolve_sync_branches(
    config: GitHubConfigRequest,
    repository_url: str,
    *,
    token: str,
    use_fixture: bool = False,
) -> list[str]:
    """Branches to walk based on integration config (specific list or all)."""
    if use_fixture or not token:
        targets = config.resolved_branch_targets() or ["main"]
        if config.sync_all_branches:
            return list(FIXTURE_BRANCHES)
        return targets

    if config.sync_all_branches:
        _, branches = list_repository_branches(token, repository_url)
        return branches or ["main"]

    return config.resolved_branch_targets() or ["main"]


def resolve_repository_default_branch(
    repository_url: str,
    *,
    token: str,
    use_fixture: bool = False,
) -> str:
    if use_fixture or not token:
        return "main"
    default_branch, _ = list_repository_branches(token, repository_url)
    return default_branch or "main"


def order_branches_with_default_first(
    branches: list[str],
    default_branch: str,
) -> list[str]:
    ordered: list[str] = []
    if default_branch in branches:
        ordered.append(default_branch)
    for branch in branches:
        if branch != default_branch:
            ordered.append(branch)
    return ordered


def _truncate_patch(text: str) -> str:
    cleaned = text.strip()
    if len(cleaned) <= MAX_PATCH_CHARS:
        return cleaned
    return cleaned[: MAX_PATCH_CHARS - 3] + "..."


def _resolve_branch_ref(
    session: requests.Session,
    token: str,
    owner: str,
    repo: str,
    branch: str,
    *,
    use_fixture: bool = False,
) -> str:
    if use_fixture or not token:
        return f"fixture-{branch}"

    response = session.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/branches/{branch}",
        headers=_headers(token),
        timeout=30,
    )
    if response.status_code >= 400:
        raise GitHubClientError(
            f"Failed to resolve branch '{branch}' ({response.status_code})"
        )
    payload = response.json()
    commit = payload.get("commit") or {}
    sha = commit.get("sha")
    if not sha:
        raise GitHubClientError(f"Branch '{branch}' has no commit SHA.")
    return sha


def fetch_repo_tree_files(
    token: str,
    owner: str,
    repo: str,
    ref_sha: str,
    *,
    use_fixture: bool = False,
) -> list[RepoTreeFile]:
    """List blob paths from a recursive git tree walk."""
    if use_fixture or not token:
        return [
            RepoTreeFile(path=path, blob_sha=f"fixture-{index}", size=512)
            for index, path in enumerate(FIXTURE_TREE_PATHS)
        ]

    session = requests.Session()
    response = session.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{ref_sha}",
        headers=_headers(token),
        params={"recursive": "1"},
        timeout=60,
    )
    if response.status_code >= 400:
        raise GitHubClientError(
            f"GitHub tree API failed ({response.status_code}): {response.text[:200]}"
        )

    payload = response.json()
    if payload.get("truncated"):
        logger.warning(
            "Git tree for %s/%s@%s was truncated by GitHub API",
            owner,
            repo,
            ref_sha[:12],
        )

    files: list[RepoTreeFile] = []
    for entry in payload.get("tree") or []:
        if entry.get("type") != "blob":
            continue
        path = (entry.get("path") or "").strip()
        if not path or should_exclude_repo_path(path):
            continue
        size = int(entry.get("size") or 0)
        if size > MAX_TREE_FILE_BYTES:
            continue
        files.append(
            RepoTreeFile(
                path=path,
                blob_sha=(entry.get("sha") or ""),
                size=size,
            )
        )

    files.sort(key=lambda item: item.path)
    if len(files) > MAX_FILES_PER_REPO:
        logger.warning(
            "Repository tree capped at %d files (discovered %d)",
            MAX_FILES_PER_REPO,
            len(files),
        )
        files = files[:MAX_FILES_PER_REPO]
    return files


def fetch_branch_diff_files(
    token: str,
    owner: str,
    repo: str,
    base_ref: str,
    head_ref: str,
    *,
    head_branch: str,
    use_fixture: bool = False,
) -> list[RepoTreeFile]:
    """Files that differ on head_ref relative to base_ref (patch-only branch ingest)."""
    if use_fixture or not token:
        paths = FIXTURE_BRANCH_DIFF_PATHS.get(head_branch, [])
        return [
            RepoTreeFile(
                path=path,
                blob_sha=f"fixture-diff-{index}",
                size=256,
                patch_preview=_truncate_patch(
                    "@@ -1,3 +1,5 @@\n+export function repoSync() {}"
                ),
            )
            for index, path in enumerate(paths)
        ]

    session = requests.Session()
    response = session.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/compare/{base_ref}...{head_ref}",
        headers=_headers(token),
        timeout=60,
    )
    if response.status_code >= 400:
        raise GitHubClientError(
            f"GitHub compare API failed ({response.status_code}): {response.text[:200]}"
        )

    payload = response.json()
    if payload.get("status") == "identical":
        return []

    files: list[RepoTreeFile] = []
    for row in payload.get("files") or []:
        status = (row.get("status") or "").strip()
        if status == "removed":
            continue
        path = (row.get("filename") or "").strip()
        if not path or should_exclude_repo_path(path):
            continue
        patch = _truncate_patch(row.get("patch") or "")
        files.append(
            RepoTreeFile(
                path=path,
                blob_sha=(row.get("sha") or ""),
                size=0,
                patch_preview=patch,
            )
        )

    files.sort(key=lambda item: item.path)
    if len(files) > MAX_FILES_PER_REPO:
        logger.warning(
            "Branch diff capped at %d files (discovered %d)",
            MAX_FILES_PER_REPO,
            len(files),
        )
        files = files[:MAX_FILES_PER_REPO]
    return files


def build_branch_sync_plans(
    config: GitHubConfigRequest,
    repository_url: str,
    branches: list[str],
    *,
    default_branch: str,
    use_fixture: bool = False,
    progress: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> list[BranchSyncPlan]:
    owner, repo = parse_repository_url(repository_url)
    token = (config.personal_access_token or "").strip()
    session = requests.Session()
    plans: list[BranchSyncPlan] = []
    default_ref: str | None = None

    for index, branch in enumerate(branches):
        if cancel_check is not None:
            cancel_check()

        if progress is not None:
            stats = _progress_stats(
                branches_total=len(branches),
                branches_completed=index,
                current_branch=branch,
                files_total=0,
                files_completed=0,
            )
            progress(
                "fetching",
                f"Resolving branch {index + 1}/{len(branches)}: {branch}…",
                stats,
            )

        ref_sha = _resolve_branch_ref(
            session,
            token,
            owner,
            repo,
            branch,
            use_fixture=use_fixture,
        )

        if branch == default_branch:
            default_ref = ref_sha
            tree_files = fetch_repo_tree_files(
                token,
                owner,
                repo,
                ref_sha,
                use_fixture=use_fixture,
            )
            plans.append(
                BranchSyncPlan(
                    branch=branch,
                    ref_sha=ref_sha,
                    tree_files=tree_files,
                    sync_mode="full",
                )
            )
            continue

        if default_ref is None:
            default_ref = _resolve_branch_ref(
                session,
                token,
                owner,
                repo,
                default_branch,
                use_fixture=use_fixture,
            )

        diff_files = fetch_branch_diff_files(
            token,
            owner,
            repo,
            default_ref,
            ref_sha,
            head_branch=branch,
            use_fixture=use_fixture,
        )
        plans.append(
            BranchSyncPlan(
                branch=branch,
                ref_sha=ref_sha,
                tree_files=diff_files,
                sync_mode="diff",
                base_branch=default_branch,
            )
        )

    return plans


def _snapshot_for_path(
    session: requests.Session,
    *,
    token: str,
    owner: str,
    repo: str,
    repository_url: str,
    ref_sha: str,
    path: str,
    component_id: str | None,
    use_fixture: bool,
    patch_preview: str = "",
) -> GitHubCodeFileSnapshot:
    if use_fixture or not token:
        return _fixture_code_snapshot(
            repository_url,
            path,
            ref_sha,
            component_id,
            patch_preview=patch_preview,
        )

    content, content_sha = _fetch_file_content(
        session, token, owner, repo, path, ref_sha
    )
    blame = fetch_blame_ranges(token, owner, repo, path, ref_sha, max_ranges=None)
    authors = sorted({row.author_login for row in blame if row.author_login})
    return GitHubCodeFileSnapshot(
        repository_url=repository_url,
        file_path=path,
        ref=ref_sha,
        component_id=component_id,
        content_preview=content,
        patch_preview=_truncate_patch(patch_preview),
        blame_ranges=blame,
        primary_authors=authors,
        content_sha=content_sha or "",
    )


def collect_branch_snapshots(
    config: GitHubConfigRequest,
    repository_url: str,
    tree_files: list[RepoTreeFile],
    components_by_id: dict,
    *,
    branch: str,
    ref_sha: str,
    branches_total: int,
    branches_completed: int,
    files_total: int,
    files_completed_offset: int,
    use_fixture: bool = False,
    progress: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> tuple[list[GitHubCodeFileSnapshot], int]:
    """Fetch content and blame for each selected file in batches."""
    owner, repo = parse_repository_url(repository_url)
    token = (config.personal_access_token or "").strip()
    components_by_name = {
        component.name.lower(): component.id for component in components_by_id.values()
    }
    session = requests.Session()
    snapshots: list[GitHubCodeFileSnapshot] = []
    files_completed = files_completed_offset
    branch_total = len(tree_files)

    for batch_start in range(0, branch_total, FULL_REPO_BATCH_SIZE):
        batch = tree_files[batch_start : batch_start + FULL_REPO_BATCH_SIZE]

        for tree_file in batch:
            if cancel_check is not None:
                cancel_check()

            component_id = map_path_to_component(
                tree_file.path,
                path_component_map=config.path_component_map,
                repo_name=repo,
                components_by_id=components_by_id,
                components_by_name=components_by_name,
                default_component_id=config.default_component_id,
            )
            try:
                snapshots.append(
                    _snapshot_for_path(
                        session,
                        token=token,
                        owner=owner,
                        repo=repo,
                        repository_url=repository_url,
                        ref_sha=ref_sha,
                        path=tree_file.path,
                        component_id=component_id,
                        use_fixture=use_fixture,
                        patch_preview=tree_file.patch_preview,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Skipping full-repo snapshot for %s@%s: %s",
                    tree_file.path,
                    ref_sha[:12],
                    exc,
                )
                snapshots.append(
                    GitHubCodeFileSnapshot(
                        repository_url=repository_url,
                        file_path=tree_file.path,
                        ref=ref_sha,
                        component_id=component_id,
                        content_sha=tree_file.blob_sha,
                    )
                )

            files_completed += 1
            if progress is not None:
                stats = _progress_stats(
                    branches_total=branches_total,
                    branches_completed=branches_completed,
                    current_branch=branch,
                    files_total=files_total,
                    files_completed=files_completed,
                )
                progress("fetching", _progress_message(stats), stats)

    return snapshots, files_completed


def _collect_repo_snapshots_blocking(
    repo_config: GitHubConfigRequest,
    normalized_url: str,
    components_by_id: dict,
    *,
    use_fixture: bool = False,
    progress: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> tuple[list[GitHubCodeFileSnapshot], list[BranchSyncPlan], int, list[str]]:
    """Blocking GitHub tree walk + file/blame fetch (runs in a worker thread)."""
    owner, repo = parse_repository_url(normalized_url)
    token = (repo_config.personal_access_token or "").strip()

    branches = resolve_sync_branches(
        repo_config,
        normalized_url,
        token=token,
        use_fixture=use_fixture,
    )
    if not branches:
        raise ValueError(f"No branches configured for {normalized_url}.")

    default_branch = resolve_repository_default_branch(
        normalized_url,
        token=token,
        use_fixture=use_fixture,
    )
    branches = order_branches_with_default_first(branches, default_branch)

    if progress is not None:
        progress(
            "fetching",
            f"Preparing {len(branches)} branch{'es' if len(branches) != 1 else ''} "
            f"for {owner}/{repo} (default: {default_branch})…",
            _progress_stats(
                branches_total=len(branches),
                branches_completed=0,
                current_branch=branches[0],
                files_total=0,
                files_completed=0,
            ),
        )

    branch_plans = build_branch_sync_plans(
        repo_config,
        normalized_url,
        branches,
        default_branch=default_branch,
        use_fixture=use_fixture,
        progress=progress,
        cancel_check=cancel_check,
    )

    files_total = sum(len(plan.tree_files) for plan in branch_plans)
    if files_total == 0:
        raise ValueError(f"No ingestible files found in {normalized_url}.")

    if progress is not None:
        progress(
            "fetching",
            f"Discovered {files_total} files across {len(branch_plans)} branch"
            f"{'es' if len(branch_plans) != 1 else ''} — fetching contents…",
            _progress_stats(
                branches_total=len(branch_plans),
                branches_completed=0,
                current_branch=branch_plans[0].branch,
                files_total=files_total,
                files_completed=0,
            ),
        )

    all_snapshots: list[GitHubCodeFileSnapshot] = []
    files_completed = 0
    synced_branches: list[str] = []

    for branch_index, plan in enumerate(branch_plans):
        if cancel_check is not None:
            cancel_check()

        if not plan.tree_files:
            synced_branches.append(plan.branch)
            continue

        branch_snapshots, files_completed = collect_branch_snapshots(
            repo_config,
            normalized_url,
            plan.tree_files,
            components_by_id,
            branch=plan.branch,
            ref_sha=plan.ref_sha,
            branches_total=len(branch_plans),
            branches_completed=branch_index,
            files_total=files_total,
            files_completed_offset=files_completed,
            use_fixture=use_fixture,
            progress=progress,
            cancel_check=cancel_check,
        )
        all_snapshots.extend(branch_snapshots)
        synced_branches.append(plan.branch)

        if progress is not None:
            mode_label = "full" if plan.sync_mode == "full" else f"diff vs {plan.base_branch}"
            stats = _progress_stats(
                branches_total=len(branch_plans),
                branches_completed=branch_index + 1,
                current_branch=plan.branch,
                files_total=files_total,
                files_completed=files_completed,
            )
            progress(
                "fetching",
                f"Finished branch {plan.branch} ({mode_label}) "
                f"({branch_index + 1}/{len(branch_plans)})",
                stats,
            )

    return all_snapshots, branch_plans, files_total, synced_branches


async def process_github_repo_sync(
    db: Session,
    tenant_id: uuid.UUID,
    repository_url: str,
    *,
    progress: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
    use_fixture: bool = False,
) -> dict[str, int | str | list[str]]:
    """Walk configured branches for one repo, ingest code files + blame into Cognee."""

    def report(phase: str, message: str, stats: dict[str, int | str] | None = None) -> None:
        if cancel_check is not None:
            cancel_check()
        if progress is not None:
            progress(phase, message, stats)

    def _check_cancel() -> None:
        if cancel_check is not None:
            cancel_check()

    normalized_url = _normalize_repo_url(repository_url)
    config = get_github_config(db, tenant_id)
    if not config:
        raise ValueError("GitHub integration is not configured.")

    configured_urls = {
        _normalize_repo_url(url) for url in config.resolved_repository_urls()
    }
    if normalized_url not in configured_urls:
        raise ValueError(
            f"Repository '{normalized_url}' is not in the GitHub integration config."
        )

    repo_config = config.with_repository(normalized_url)

    from app.services.github_identity import prepare_github_identity_context

    report("fetching", "Loading GitHub contributors for identity mapping…")
    await asyncio.to_thread(prepare_github_identity_context, db, tenant_id, repo_config)

    employee_nodes, component_nodes, components_by_id = _load_org_context(db, tenant_id)

    all_snapshots, branch_plans, files_total, synced_branches = await asyncio.to_thread(
        _collect_repo_snapshots_blocking,
        repo_config,
        normalized_url,
        components_by_id,
        use_fixture=use_fixture,
        progress=report,
        cancel_check=cancel_check,
    )
    branch_label = ", ".join(synced_branches)
    files_completed = len(all_snapshots)

    _check_cancel()
    report("building_graph", "Building Cognee graph nodes from repository files…")
    code_lines, data_points, edge_count = analyze_github_code_payload(
        all_snapshots,
        employee_nodes,
        component_nodes,
        db,
        tenant_id,
        components_by_id=components_by_id,
    )

    ingest_plan = plan_sync_ingest(db, tenant_id, "github", data_points)
    data_points = ingest_plan.to_ingest
    from app.ontology.crosslinks import apply_ontology_cross_links

    edge_count = count_graph_edges(data_points)
    edge_count += apply_ontology_cross_links(data_points)

    report("building_graph", ingest_plan.progress_message(), None)

    diff_branches = [
        plan.branch for plan in branch_plans if plan.sync_mode == "diff" and plan.tree_files
    ]
    narrative_lines = [
        f"Full GitHub repository sync for {normalized_url}.",
        f"Branches: {branch_label}.",
    ]
    if diff_branches:
        narrative_lines.append(
            f"Non-default branches ingested as diffs only: {', '.join(diff_branches)}."
        )
    narrative_lines.extend(
        [
            f"Discovered {files_total} file(s); prepared {len(all_snapshots)} code snapshot(s).",
            *code_lines[:40],
        ]
    )
    if len(code_lines) > 40:
        narrative_lines.append(f"+{len(code_lines) - 40} more file summaries.")
    narrative = "\n".join(narrative_lines)

    if data_points:
        _check_cancel()
        report(
            "building_graph",
            f"Indexing {len(data_points)} repository file nodes into Cognee…",
            _progress_stats(
                branches_total=len(branch_plans),
                branches_completed=len(branch_plans),
                current_branch=synced_branches[-1] if synced_branches else "",
                files_total=files_total,
                files_completed=files_completed,
            ),
        )
        await tenant_add_data_points(
            tenant_id,
            data_points,
            employee_nodes=employee_nodes,
            component_nodes=component_nodes,
        )
        record_synced_items(db, tenant_id, "github", ingest_plan.ledger_items)

    dataset = tenant_dataset_name(tenant_id)
    from app.ontology.enrichment import run_post_structured_cognify_enrichment

    await run_post_structured_cognify_enrichment(
        "github",
        tenant_id,
        narrative,
        ingest_plan,
        report=report,
    )

    report("finalizing", "Updating ownership graph from git blame…", None)
    from app.services.integration_telemetry import apply_github_blame_telemetry

    apply_github_blame_telemetry(db, tenant_id, all_snapshots)

    report("finalizing", "Finishing repository sync…", None)
    db.commit()
    mark_sync_completed("github")
    record_integration_sync(db, tenant_id, "github")

    ledger_note = ingest_plan.result_note()
    narrative_preview = narrative[:280]
    if ledger_note:
        narrative_preview = f"{ledger_note} {narrative_preview}"[:280]

    mapped_count = sum(1 for snap in all_snapshots if snap.component_id)
    return {
        "source": "github_repo",
        "repository_url": normalized_url,
        "branch": branch_label,
        "ref": branch_plans[-1].ref_sha if branch_plans else "",
        "branches_synced": synced_branches,
        "branches_total": len(synced_branches),
        "cognee_dataset": dataset,
        "documents_ingested": len(data_points) if data_points else 0,
        "graph_nodes_created": len(data_points),
        "graph_edges_created": edge_count,
        "narrative_preview": narrative_preview,
        "items_fetched": ingest_plan.fetched_count,
        "items_new": ingest_plan.new_count,
        "items_updated": ingest_plan.updated_count,
        "items_skipped": ingest_plan.skipped_count,
        "skipped_preview": ingest_plan.skipped_preview,
        "already_synced_note": ledger_note,
        "files_discovered": files_total,
        "files_mapped_to_components": mapped_count,
    }

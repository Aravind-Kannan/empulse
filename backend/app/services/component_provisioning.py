"""Auto-provision org-chart components from GitHub repositories and Jira projects."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field

import requests
from sqlalchemy.orm import Session

from app.models.operational import Component
from app.schemas.integrations import GitHubConfigRequest, JiraConfigRequest
from app.services.github_client import list_repository_branches, parse_repository_url
from app.services.github_repo_sync import (
    _resolve_branch_ref,
    fetch_repo_tree_files,
)
from app.services.employee_ids import scope_component_id
from app.services.component_management import consolidate_duplicate_components
from app.services.integration_config_store import save_github_config, save_jira_config
from app.services.jira_client import fetch_jira_project_components

logger = logging.getLogger(__name__)

AUTO_DESC_PREFIX = "AUTO:"
MAX_COMPONENT_ID_LEN = 64

EXCLUDED_TOP_LEVEL = frozenset(
    {
        ".github",
        ".git",
        "node_modules",
        "dist",
        "build",
        "vendor",
        "coverage",
        ".vscode",
        ".idea",
        "docs",
        "scripts",
        "tools",
        "__pycache__",
        ".venv",
        "venv",
        "tmp",
        "temp",
        "public",
        "static",
        "assets",
        "test",
        "tests",
        "__tests__",
    }
)
MONOREPO_CONTAINER_DIRS = frozenset(
    {"services", "packages", "apps", "libs", "modules", "components"}
)
MIN_FILES_PER_PARTITION = 5


@dataclass
class RepoPartition:
    """A logical sub-component within a repository."""

    slug: str
    display_name: str
    path_prefix: str


@dataclass
class ProvisionResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    component_ids: list[str] = field(default_factory=list)


def _slugify(*parts: str) -> str:
    return "-".join(
        re.sub(r"[^a-z0-9]+", "-", (part or "").lower()).strip("-")
        for part in parts
        if (part or "").strip()
    )


def _component_id(prefix: str, *parts: str) -> str:
    body = _slugify(*parts)
    candidate = f"{prefix}-{body}" if body else prefix
    if len(candidate) <= MAX_COMPONENT_ID_LEN:
        return candidate
    return candidate[:MAX_COMPONENT_ID_LEN].rstrip("-")


def _auto_description(source: str, tag: str) -> str:
    return f"{AUTO_DESC_PREFIX}{source}:{tag}"


def _is_auto_managed(row: Component) -> bool:
    return (row.description or "").startswith(AUTO_DESC_PREFIX)


def _upsert_component(
    db: Session,
    tenant_id: uuid.UUID,
    component_id: str,
    name: str,
    source: str,
    tag: str,
) -> str:
    """Insert or update an auto-managed component. Returns created|updated|skipped."""
    component_id = scope_component_id(component_id, tenant_id)
    description = _auto_description(source, tag)
    row = db.get(Component, component_id)
    if row is None:
        db.add(
            Component(
                id=component_id,
                tenant_id=tenant_id,
                name=name,
                description=description,
            )
        )
        return "created"
    if row.tenant_id != tenant_id:
        return "skipped"
    if not _is_auto_managed(row):
        return "skipped"
    row.name = name
    row.description = description
    return "updated"


def discover_repo_partitions(paths: list[str]) -> list[RepoPartition]:
    """Infer monorepo sub-components from repository file paths."""
    top_counts: dict[str, int] = {}
    nested_counts: dict[tuple[str, str], int] = {}

    for raw_path in paths:
        path = raw_path.strip().lstrip("/")
        if not path:
            continue
        parts = path.split("/")
        top = parts[0]
        if top in EXCLUDED_TOP_LEVEL or top.startswith("."):
            continue
        top_counts[top] = top_counts.get(top, 0) + 1
        if len(parts) >= 2 and top in MONOREPO_CONTAINER_DIRS:
            child = parts[1]
            if child in EXCLUDED_TOP_LEVEL or child.startswith("."):
                continue
            nested_counts[(top, child)] = nested_counts.get((top, child), 0) + 1

    nested_candidates = [
        RepoPartition(
            slug=_slugify(container, child),
            display_name=child.replace("-", " ").replace("_", " ").title(),
            path_prefix=f"{container}/{child}/",
        )
        for (container, child), count in sorted(nested_counts.items())
        if count >= MIN_FILES_PER_PARTITION
    ]
    if len(nested_candidates) >= 2:
        return nested_candidates

    top_candidates = [
        RepoPartition(
            slug=_slugify(top),
            display_name=top.replace("-", " ").replace("_", " ").title(),
            path_prefix=f"{top}/",
        )
        for top, count in sorted(top_counts.items())
        if count >= MIN_FILES_PER_PARTITION
    ]
    if len(top_candidates) >= 2:
        return top_candidates

    return []


def _tree_paths_for_repo(
    config: GitHubConfigRequest,
    repository_url: str,
    *,
    use_fixture: bool = False,
) -> list[str]:
    owner, repo = parse_repository_url(repository_url)
    token = (config.personal_access_token or "").strip()
    repo_config = config.with_repository(repository_url)
    branch = (repo_config.branch_target or "main").strip() or "main"

    if use_fixture or not token:
        tree_files = fetch_repo_tree_files(
            token,
            owner,
            repo,
            f"fixture-{branch}",
            use_fixture=True,
        )
        return [item.path for item in tree_files]

    session = requests.Session()
    try:
        default_branch, _ = list_repository_branches(token, repository_url)
    except Exception:
        logger.warning(
            "Could not list branches for %s; using configured branch %s",
            repository_url,
            branch,
            exc_info=True,
        )
        default_branch = branch

    ref_sha = _resolve_branch_ref(
        session,
        token,
        owner,
        repo,
        default_branch,
        use_fixture=False,
    )
    tree_files = fetch_repo_tree_files(token, owner, repo, ref_sha, use_fixture=False)
    return [item.path for item in tree_files]


def provision_github_components_for_repo(
    db: Session,
    tenant_id: uuid.UUID,
    config: GitHubConfigRequest,
    repository_url: str,
    *,
    use_fixture: bool = False,
) -> ProvisionResult:
    """Create or update components for one GitHub repository."""
    consolidate_duplicate_components(db, tenant_id)
    owner, repo = parse_repository_url(repository_url)
    repo_label = f"{owner}/{repo}"
    paths = _tree_paths_for_repo(config, repository_url, use_fixture=use_fixture)
    partitions = discover_repo_partitions(paths)
    result = ProvisionResult()
    path_map = dict(config.path_component_map or {})
    repo_prefix = scope_component_id(_component_id("comp-gh", owner, repo), tenant_id)

    if partitions:
        for partition in partitions:
            component_id = scope_component_id(
                _component_id("comp-gh", owner, repo, partition.slug),
                tenant_id,
            )
            action = _upsert_component(
                db,
                tenant_id,
                component_id,
                f"{repo_label} / {partition.display_name}",
                "github",
                f"{repo_label}:{partition.path_prefix}",
            )
            _tally_action(result, action, component_id)
            if partition.path_prefix not in path_map:
                path_map[partition.path_prefix] = component_id
    else:
        action = _upsert_component(
            db,
            tenant_id,
            repo_prefix,
            repo_label,
            "github",
            repo_label,
        )
        _tally_action(result, action, repo_prefix)

    if path_map != (config.path_component_map or {}):
        updated_config = config.model_copy(update={"path_component_map": path_map})
        if not updated_config.default_component_id:
            updated_config = updated_config.model_copy(
                update={"default_component_id": result.component_ids[0]}
                if result.component_ids
                else {}
            )
        save_github_config(db, tenant_id, updated_config)

    db.commit()
    return result


def provision_github_components(
    db: Session,
    tenant_id: uuid.UUID,
    config: GitHubConfigRequest,
    *,
    use_fixture: bool = False,
) -> ProvisionResult:
    """Provision components for every configured GitHub repository."""
    aggregate = ProvisionResult()
    for repository_url in config.resolved_repository_urls():
        try:
            repo_result = provision_github_components_for_repo(
                db,
                tenant_id,
                config,
                repository_url,
                use_fixture=use_fixture,
            )
            config = get_github_config_refreshed(db, tenant_id) or config
        except Exception:
            logger.exception(
                "Component provisioning failed for GitHub repo %s", repository_url
            )
            continue
        aggregate.created += repo_result.created
        aggregate.updated += repo_result.updated
        aggregate.skipped += repo_result.skipped
        aggregate.component_ids.extend(repo_result.component_ids)
    return aggregate


def provision_jira_components(
    db: Session,
    tenant_id: uuid.UUID,
    config: JiraConfigRequest,
    *,
    use_fixture: bool = False,
) -> ProvisionResult:
    """Create or update components from Jira project components."""
    consolidate_duplicate_components(db, tenant_id)
    result = ProvisionResult()
    component_field_map = dict(config.component_field_map or {})
    project_component_map = dict(config.project_component_map or {})

    discovered = fetch_jira_project_components(config, use_fixture=use_fixture)
    components_by_project: dict[str, list[str]] = {}

    for item in discovered:
        project_key = item.project_key.upper()
        component_id = scope_component_id(
            _component_id("comp-jira", project_key, item.name),
            tenant_id,
        )
        action = _upsert_component(
            db,
            tenant_id,
            component_id,
            f"{project_key} / {item.name}",
            "jira",
            f"{project_key}:{item.name}",
        )
        _tally_action(result, action, component_id)
        components_by_project.setdefault(project_key, []).append(component_id)
        if item.name not in component_field_map:
            component_field_map[item.name] = component_id

    configured_projects = [
        key.strip().upper()
        for key in (config.project_keys or "").split(",")
        if key.strip()
    ]
    for project_key in configured_projects:
        if project_key in project_component_map:
            continue
        project_components = components_by_project.get(project_key, [])
        if project_components:
            project_component_map[project_key] = project_components[0]
            continue
        fallback_id = scope_component_id(
            _component_id("comp-jira", project_key),
            tenant_id,
        )
        action = _upsert_component(
            db,
            tenant_id,
            fallback_id,
            f"Jira {project_key}",
            "jira",
            f"project:{project_key}",
        )
        _tally_action(result, action, fallback_id)
        project_component_map[project_key] = fallback_id

    updates: dict[str, object] = {}
    if component_field_map != (config.component_field_map or {}):
        updates["component_field_map"] = component_field_map
    if project_component_map != (config.project_component_map or {}):
        updates["project_component_map"] = project_component_map
    if not config.default_component_id and result.component_ids:
        updates["default_component_id"] = result.component_ids[0]
    if updates:
        save_jira_config(
            db,
            tenant_id,
            config.model_copy(update=updates),
        )

    db.commit()
    return result


def get_github_config_refreshed(
    db: Session,
    tenant_id: uuid.UUID,
) -> GitHubConfigRequest | None:
    from app.services.integration_config_store import get_github_config

    return get_github_config(db, tenant_id)


def _tally_action(result: ProvisionResult, action: str, component_id: str) -> None:
    if action == "created":
        result.created += 1
        result.component_ids.append(component_id)
    elif action == "updated":
        result.updated += 1
        result.component_ids.append(component_id)
    else:
        result.skipped += 1

"""Auto-provision org-chart components from GitHub repositories and Jira projects."""

from __future__ import annotations

import json
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
from app.services.github_component_display import format_github_component_name
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
FEATURE_DOC_PREFIXES = (
    "docs/features/",
    "docs/modules/",
    "features/",
    "modules/",
)
METADATA_ROOT_FILES = ("README.md", "package.json", "pyproject.toml")
ARCHITECTURAL_REPO_SUFFIXES = frozenset(
    {
        "backend",
        "frontend",
        "api",
        "web",
        "mobile",
        "core",
        "server",
        "client",
        "worker",
        "gateway",
        "service",
    }
)


@dataclass
class RepoTreeContext:
    owner: str
    repo: str
    paths: list[str]
    ref_sha: str
    token: str
    use_fixture: bool


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


def _normalize_map_prefix(raw: str) -> str:
    cleaned = raw.strip().strip("`").strip()
    if not cleaned:
        return ""
    cleaned = cleaned.lstrip("/")
    if cleaned.endswith("/"):
        return cleaned
    if "." in cleaned.split("/")[-1]:
        return cleaned
    return f"{cleaned}/"


def parse_mapped_source_paths(markdown: str) -> list[str]:
    """Parse bullet paths under a '## Mapped source paths' heading in feature READMEs."""
    lines = markdown.splitlines()
    in_section = False
    paths: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("## ") and "mapped source paths" in stripped.lower():
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if not in_section:
            continue
        if not stripped.startswith(("-", "*")):
            continue
        body = stripped.lstrip("-*").strip()
        if body.startswith("`") and "`" in body[1:]:
            body = body[1 : body.index("`", 1)]
        normalized = _normalize_map_prefix(body)
        if normalized:
            paths.append(normalized)
    return paths


def _workspace_repo_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[3]


def _read_feature_readme_content(
    context: RepoTreeContext,
    readme_path: str,
) -> str:
    if not context.use_fixture and context.token:
        from app.services.github_code import _fetch_file_content

        session = requests.Session()
        content, _ = _fetch_file_content(
            session,
            context.token,
            context.owner,
            context.repo,
            readme_path,
            context.ref_sha,
        )
        return content

    local_path = _workspace_repo_root() / readme_path
    if local_path.is_file():
        return local_path.read_text(encoding="utf-8")
    return ""


def _apply_feature_readme_path_mappings(
    path_map: dict[str, str],
    tree_context: RepoTreeContext,
    partitions: list[RepoPartition],
    component_id_by_slug: dict[str, str],
) -> None:
    """Register code paths listed in feature READMEs for GitHub attribution."""
    path_set = set(tree_context.paths)
    for partition in partitions:
        component_id = component_id_by_slug.get(partition.slug)
        if not component_id:
            continue
        readme_path = next(
            (
                candidate
                for candidate in (
                    f"{partition.path_prefix}README.md",
                    f"{partition.path_prefix}readme.md",
                )
                if candidate in path_set
            ),
            None,
        )
        if readme_path is None and not tree_context.use_fixture:
            continue
        if readme_path is None:
            readme_path = f"{partition.path_prefix}README.md"
        content = _read_feature_readme_content(tree_context, readme_path)
        for mapped_prefix in parse_mapped_source_paths(content):
            path_map[mapped_prefix] = component_id


def _humanize_slug(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("-", " ").replace("_", " ")).strip().title()


def _humanize_repo_name(repo: str) -> str:
    """Derive a short product name from a repository slug (no owner prefix)."""
    slug = (repo or "").strip()
    if not slug:
        return "Repository"
    tokens = [part for part in re.split(r"[-_]+", slug) if part]
    if len(tokens) >= 2 and tokens[-1].lower() in ARCHITECTURAL_REPO_SUFFIXES:
        return _humanize_slug(tokens[-1])
    return _humanize_slug(slug)


def _clean_package_name(raw_name: str) -> str | None:
    name = (raw_name or "").strip()
    if not name:
        return None
    if name.startswith("@"):
        name = name.split("/", 1)[-1]
    name = name.split("/")[-1]
    if name in {".", ".."}:
        return None
    return _humanize_slug(name)


def _parse_project_name_from_metadata(path: str, content: str) -> str | None:
    if not content.strip():
        return None
    if path.endswith("package.json"):
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return None
        for key in ("name", "title"):
            cleaned = _clean_package_name(str(payload.get(key) or ""))
            if cleaned:
                return cleaned
        description = str(payload.get("description") or "").strip()
        if description:
            return _humanize_slug(description.split(".", 1)[0][:48])
        return None
    if path.endswith("pyproject.toml"):
        match = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if match:
            return _clean_package_name(match.group(1))
        return None
    if path.lower().endswith("readme.md"):
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
                if title and title.lower() not in {"readme", "documentation", "docs"}:
                    return _humanize_slug(title)
        return None
    return None


def _fixture_metadata_content(path: str, repo: str) -> str:
    if path == "README.md":
        return f"# {_humanize_repo_name(repo)}\n"
    if path.endswith("package.json"):
        folder = path.rsplit("/", 1)[0] if "/" in path else repo
        return json.dumps({"name": folder.split("/")[-1]})
    return ""


def _discover_feature_doc_partitions(paths: list[str]) -> list[RepoPartition]:
    """Infer feature components from docs/features or similar markdown trees."""
    counts: dict[tuple[str, str], int] = {}
    for raw_path in paths:
        path = raw_path.strip().lstrip("/")
        for prefix in FEATURE_DOC_PREFIXES:
            if not path.startswith(prefix):
                continue
            remainder = path[len(prefix) :]
            feature = remainder.split("/", 1)[0]
            if not feature or feature in EXCLUDED_TOP_LEVEL or feature.startswith("."):
                break
            key = (prefix, feature)
            counts[key] = counts.get(key, 0) + 1
            break

    partitions = [
        RepoPartition(
            slug=_slugify(feature),
            display_name=_humanize_slug(feature),
            path_prefix=f"{prefix}{feature}/",
        )
        for (prefix, feature), count in sorted(counts.items())
        if count >= 1
    ]
    if len(partitions) >= 2:
        return partitions
    return []


def _discover_monorepo_partitions(paths: list[str]) -> list[RepoPartition]:
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
            display_name=_humanize_slug(child),
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
            display_name=_humanize_slug(top),
            path_prefix=f"{top}/",
        )
        for top, count in sorted(top_counts.items())
        if count >= MIN_FILES_PER_PARTITION
    ]
    if len(top_candidates) >= 2:
        return top_candidates

    return []


def discover_repo_partitions(paths: list[str]) -> list[RepoPartition]:
    """Infer feature or monorepo sub-components from repository file paths."""
    feature_partitions = _discover_feature_doc_partitions(paths)
    if feature_partitions:
        return feature_partitions
    return _discover_monorepo_partitions(paths)


def _metadata_paths_to_fetch(paths: list[str], partition: RepoPartition | None = None) -> list[str]:
    path_set = set(paths)
    candidates: list[str] = []
    if partition is None:
        for name in METADATA_ROOT_FILES:
            if name in path_set:
                candidates.append(name)
    else:
        prefix = partition.path_prefix.rstrip("/")
        for name in METADATA_ROOT_FILES:
            candidate = f"{prefix}/{name}"
            if candidate in path_set:
                candidates.append(candidate)
    return candidates


def _infer_project_name(
    context: RepoTreeContext,
    partition: RepoPartition | None = None,
) -> str | None:
    for path in _metadata_paths_to_fetch(context.paths, partition):
        if context.use_fixture or not context.token:
            content = _fixture_metadata_content(path, context.repo)
        else:
            from app.services.github_code import _fetch_file_content

            session = requests.Session()
            content, _ = _fetch_file_content(
                session,
                context.token,
                context.owner,
                context.repo,
                path,
                context.ref_sha,
            )
        name = _parse_project_name_from_metadata(path, content)
        if name:
            return name
    return None


def _single_repo_component_name(context: RepoTreeContext) -> str:
    return _infer_project_name(context) or _humanize_repo_name(context.repo)


def _partition_component_name(context: RepoTreeContext, partition: RepoPartition) -> str:
    return format_github_component_name(
        f"{context.owner}/{context.repo}",
        partition.path_prefix,
    )


def _tree_context_for_repo(
    config: GitHubConfigRequest,
    repository_url: str,
    *,
    use_fixture: bool = False,
) -> RepoTreeContext:
    owner, repo = parse_repository_url(repository_url)
    token = (config.personal_access_token or "").strip()
    repo_config = config.with_repository(repository_url)
    branch = (repo_config.branch_target or "main").strip() or "main"

    if use_fixture or not token:
        ref_sha = f"fixture-{branch}"
        tree_files = fetch_repo_tree_files(
            token,
            owner,
            repo,
            ref_sha,
            use_fixture=True,
        )
        return RepoTreeContext(
            owner=owner,
            repo=repo,
            paths=[item.path for item in tree_files],
            ref_sha=ref_sha,
            token=token,
            use_fixture=True,
        )

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
    return RepoTreeContext(
        owner=owner,
        repo=repo,
        paths=[item.path for item in tree_files],
        ref_sha=ref_sha,
        token=token,
        use_fixture=False,
    )


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
    tree_context = _tree_context_for_repo(config, repository_url, use_fixture=use_fixture)
    partitions = discover_repo_partitions(tree_context.paths)
    result = ProvisionResult()
    path_map = dict(config.path_component_map or {})
    repo_prefix = scope_component_id(_component_id("comp-gh", owner, repo), tenant_id)

    if partitions:
        component_id_by_slug: dict[str, str] = {}
        for partition in partitions:
            component_id = scope_component_id(
                _component_id("comp-gh", owner, repo, partition.slug),
                tenant_id,
            )
            component_id_by_slug[partition.slug] = component_id
            action = _upsert_component(
                db,
                tenant_id,
                component_id,
                _partition_component_name(tree_context, partition),
                "github",
                f"{repo_label}:{partition.path_prefix}",
            )
            _tally_action(result, action, component_id)
            if partition.path_prefix not in path_map:
                path_map[partition.path_prefix] = component_id
        _apply_feature_readme_path_mappings(
            path_map,
            tree_context,
            partitions,
            component_id_by_slug,
        )
    else:
        action = _upsert_component(
            db,
            tenant_id,
            repo_prefix,
            _single_repo_component_name(tree_context),
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
            _humanize_slug(item.name),
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
            _humanize_slug(project_key),
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

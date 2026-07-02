"""Map GitHub file paths to org chart components."""

from __future__ import annotations

import re

from app.models.operational import Component


def _normalize_prefix(prefix: str) -> str:
    return prefix.strip().strip("/")


def map_path_to_component(
    path: str,
    *,
    path_component_map: dict[str, str],
    repo_name: str,
    components_by_id: dict[str, Component],
    components_by_name: dict[str, str],
    default_component_id: str | None,
) -> str | None:
    """Resolve a file path to a component id (priority: prefix map → repo name → default)."""
    normalized_path = path.strip().lstrip("/")

    best_match: tuple[int, str] | None = None
    for prefix, component_id in path_component_map.items():
        norm_prefix = _normalize_prefix(prefix)
        if not norm_prefix:
            continue
        if normalized_path == norm_prefix or normalized_path.startswith(f"{norm_prefix}/"):
            if best_match is None or len(norm_prefix) > best_match[0]:
                best_match = (len(norm_prefix), component_id)

    if best_match:
        return best_match[1]

    repo_key = repo_name.lower().replace("_", "-")
    for component_id, component in components_by_id.items():
        slug = re.sub(r"[^a-z0-9]+", "-", component.name.lower()).strip("-")
        if repo_key in slug or slug in repo_key:
            return component_id
        if component_id.lower().endswith(repo_key) or repo_key in component_id.lower():
            return component_id
        if component.name.lower() in repo_name.lower():
            return component_id

    if default_component_id and default_component_id in components_by_id:
        return default_component_id

    return None


def apply_path_mapping(
    activities: list,
    *,
    path_component_map: dict[str, str],
    repo_name: str,
    components_by_id: dict[str, Component],
    default_component_id: str | None,
) -> tuple[list, list[str]]:
    """Attach component_id to file changes; return unmapped paths audit list."""
    components_by_name = {
        component.name.lower(): component.id for component in components_by_id.values()
    }
    unmapped_paths: list[str] = []

    for activity in activities:
        for file_change in activity.files:
            component_id = map_path_to_component(
                file_change.path,
                path_component_map=path_component_map,
                repo_name=repo_name,
                components_by_id=components_by_id,
                components_by_name=components_by_name,
                default_component_id=default_component_id,
            )
            file_change.component_id = component_id
            if component_id is None:
                unmapped_paths.append(file_change.path)

    return activities, unmapped_paths

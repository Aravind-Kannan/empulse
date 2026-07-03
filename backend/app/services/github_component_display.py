"""Readable labels for auto-provisioned GitHub components."""

from __future__ import annotations

import re

AUTO_GITHUB_PREFIX = "AUTO:github:"
AUTO_DESC_PREFIX = "AUTO:"


def parse_github_auto_tag(description: str | None) -> tuple[str, str] | None:
    """
    Parse `AUTO:github:owner/repo:path/prefix/` into (repo_label, path_prefix).

    repo_label may be `owner/repo` or a single slug.
    """
    if not description or not description.startswith(AUTO_DESC_PREFIX):
        return None
    body = description[len(AUTO_DESC_PREFIX) :]
    if not body.startswith("github:"):
        return None
    payload = body[len("github:") :]
    repo_label, _, path_prefix = payload.partition(":")
    repo_label = repo_label.strip()
    path_prefix = path_prefix.strip()
    if not repo_label or not path_prefix:
        return None
    return repo_label, path_prefix


def repo_slug(repo_label: str) -> str:
    """`Aravind-Kannan/empulse` → `empulse`."""
    cleaned = repo_label.strip().strip("/")
    if "/" in cleaned:
        return cleaned.rsplit("/", 1)[-1]
    return cleaned


MONOREPO_CONTAINER_DIRS = frozenset(
    {"services", "packages", "apps", "libs", "modules", "components"}
)


def github_provision_key(description: str | None) -> str | None:
    """Stable key for the same auto-provisioned GitHub path."""
    parsed = parse_github_auto_tag(description)
    if not parsed:
        return None
    repo_label, path_prefix = parsed
    path = path_prefix.strip().strip("/")
    if not path:
        return repo_label.strip()
    return f"{repo_label.strip()}:{path}"


def display_folder(path_prefix: str) -> str:
    """
    Human folder label for a mapped GitHub path.

    - `notion-docs/` → `notion-docs`
    - `docs/features/era/` → `era` (not `docs`)
    - `services/payments/` → `services/payments`
    """
    parts = [part for part in path_prefix.strip().strip("/").split("/") if part]
    if not parts:
        return ""
    if len(parts) >= 3 and parts[0] == "docs" and parts[1] == "features":
        return parts[2]
    if len(parts) >= 2 and parts[0] in MONOREPO_CONTAINER_DIRS:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


def primary_folder(path_prefix: str) -> str:
    """Backward-compatible alias for display_folder."""
    return display_folder(path_prefix)


def format_github_component_name(repo_label: str, path_prefix: str) -> str:
    """`empulse / notion-docs` — repo slug plus first path segment."""
    folder = primary_folder(path_prefix)
    if folder:
        return f"{repo_slug(repo_label)} / {folder}"
    return repo_slug(repo_label)


def format_github_component_name_from_description(description: str | None) -> str | None:
    parsed = parse_github_auto_tag(description)
    if not parsed:
        return None
    repo_label, path_prefix = parsed
    return format_github_component_name(repo_label, path_prefix)


def is_github_managed_component(description: str | None) -> bool:
    return parse_github_auto_tag(description) is not None


def format_github_component_name_from_label(label: str) -> str | None:
    """
    Legacy stored names like `Aravind-Kannan/empulse / Notion Docs`.

    Prefer folder-like suffix when it looks like a path slug.
    """
    if " / " not in label:
        return None
    repo_part, suffix = label.rsplit(" / ", 1)
    repo_part = repo_part.strip()
    suffix = suffix.strip()
    if not repo_part or not suffix:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", suffix.lower()).strip("-")
    if slug and ("-" in slug or suffix.islower()):
        folder = slug
    else:
        folder = re.sub(r"\s+", "-", suffix.lower()).strip("-")
    return format_github_component_name(repo_part, f"{folder}/")

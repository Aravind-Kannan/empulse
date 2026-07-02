"""Stable ERA evidence identifiers (Step 12)."""

from __future__ import annotations

import hashlib


def stable_evidence_id(
    *,
    dimension: str,
    title: str,
    component_id: str | None = None,
) -> str:
    payload = f"{dimension}\0{title}\0{component_id or ''}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"ev-{digest}"


def normalize_evidence_ids(items: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in items:
        row = dict(item)
        row["id"] = stable_evidence_id(
            dimension=str(row.get("dimension", "")),
            title=str(row.get("title", "")),
            component_id=row.get("component_id"),
        )
        normalized.append(row)
    return normalized

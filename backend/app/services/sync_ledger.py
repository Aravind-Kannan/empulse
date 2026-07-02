"""Incremental sync ledger — skip items already ingested into Cognee."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.integration_sync_record import IntegrationSyncRecord

ItemKeyFn = Callable[[Any], str]
ItemVersionFn = Callable[[Any], str]
ItemLabelFn = Callable[[Any], str]


@dataclass
class LedgerItem:
    external_key: str
    content_version: str
    display_label: str
    node: Any


@dataclass
class SyncIngestPlan:
    fetched_count: int
    to_ingest: list[Any] = field(default_factory=list)
    ledger_items: list[LedgerItem] = field(default_factory=list)
    new_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    skipped_preview: list[str] = field(default_factory=list)

    @property
    def should_cognify(self) -> bool:
        return len(self.to_ingest) > 0

    def progress_message(self) -> str:
        if self.fetched_count == 0:
            return "No items fetched from provider."
        if not self.to_ingest:
            return (
                f"All {self.skipped_count} item(s) already in Cognee — nothing new to ingest."
            )
        parts = []
        if self.new_count:
            parts.append(f"{self.new_count} new")
        if self.updated_count:
            parts.append(f"{self.updated_count} updated")
        if self.skipped_count:
            parts.append(f"{self.skipped_count} already synced")
        summary = ", ".join(parts)
        return f"Ingesting {len(self.to_ingest)} item(s) ({summary})."

    def cognify_message(self) -> str:
        if not self.should_cognify:
            return "Skipped cognify — all fetched data already in graph."
        return "Running Cognee cognify on new and updated metadata…"

    def result_note(self) -> str:
        if self.skipped_count == 0:
            return ""
        note = f"{self.skipped_count} item(s) already in Cognee (unchanged)."
        if self.skipped_preview:
            sample = ", ".join(self.skipped_preview[:5])
            if self.skipped_count > 5:
                sample += f", +{self.skipped_count - 5} more"
            note += f" Examples: {sample}."
        return note


def _resolve_item_spec(source: str, node: Any) -> tuple[ItemKeyFn, ItemVersionFn, ItemLabelFn] | None:
    if source == "github" and hasattr(node, "content_preview"):
        return (_github_code_key, _github_code_version, _github_code_label)
    return _SOURCE_SPECS.get(source)


def _github_code_key(node: Any) -> str:
    return f"code|{node.repository_url}|{node.file_path}|{node.ref}"


def _github_code_version(node: Any) -> str:
    return f"{node.blob_sha}|{node.blame_summary}|{len(node.content_preview)}"


def _github_code_label(node: Any) -> str:
    ref_short = (node.ref or "")[:7]
    return f"{node.file_path} @ {ref_short}"


def _github_key(node: Any) -> str:
    return f"{node.repository_url}|{node.pr_number}|{node.commit_sha}|{node.file_path}"


def _github_version(node: Any) -> str:
    return f"{node.loc_added}|{node.loc_removed}|{node.branch}"


def _github_label(node: Any) -> str:
    return f"PR #{node.pr_number} {node.file_path}"


def _jira_key(node: Any) -> str:
    return node.ticket_id


def _jira_version(node: Any) -> str:
    return f"{node.status}|{node.priority}|{node.issue_type}"


def _jira_label(node: Any) -> str:
    return node.ticket_id


def _notion_key(node: Any) -> str:
    return node.page_id


def _notion_version(node: Any) -> str:
    return node.last_edited


def _notion_label(node: Any) -> str:
    return node.title or node.page_id


def _slack_key(node: Any) -> str:
    return node.thread_id


def _slack_version(node: Any) -> str:
    return f"{node.channel_name}|{node.title}"


def _slack_label(node: Any) -> str:
    return f"#{node.channel_name} {node.title}"


_SOURCE_SPECS: dict[str, tuple[ItemKeyFn, ItemVersionFn, ItemLabelFn]] = {
    "github": (_github_key, _github_version, _github_label),
    "jira": (_jira_key, _jira_version, _jira_label),
    "notion": (_notion_key, _notion_version, _notion_label),
    "slack": (_slack_key, _slack_version, _slack_label),
}


def _load_ledger(
    db: Session,
    tenant_id: uuid.UUID,
    source: str,
) -> dict[str, str]:
    rows = (
        db.query(IntegrationSyncRecord)
        .filter(
            IntegrationSyncRecord.tenant_id == tenant_id,
            IntegrationSyncRecord.source == source,
        )
        .all()
    )
    return {row.external_key: row.content_version for row in rows}


def plan_sync_ingest(
    db: Session,
    tenant_id: uuid.UUID,
    source: str,
    data_points: list[Any],
) -> SyncIngestPlan:
    """Split fetched graph nodes into new/updated vs already-synced unchanged items."""
    spec = _resolve_item_spec(source, data_points[0]) if data_points else _SOURCE_SPECS.get(source)
    plan = SyncIngestPlan(fetched_count=len(data_points))
    if not data_points:
        return plan

    if not spec and source not in _SOURCE_SPECS:
        plan.to_ingest = list(data_points)
        plan.new_count = len(data_points)
        return plan

    existing = _load_ledger(db, tenant_id, source)

    for node in data_points:
        item_spec = _resolve_item_spec(source, node) or spec
        if not item_spec:
            plan.to_ingest.append(node)
            plan.new_count += 1
            continue
        key_fn, version_fn, label_fn = item_spec
        external_key = key_fn(node)
        content_version = version_fn(node)
        display_label = label_fn(node)
        prior = existing.get(external_key)

        if prior is not None and prior == content_version:
            plan.skipped_count += 1
            if len(plan.skipped_preview) < 10:
                plan.skipped_preview.append(display_label)
            continue

        plan.to_ingest.append(node)
        plan.ledger_items.append(
            LedgerItem(
                external_key=external_key,
                content_version=content_version,
                display_label=display_label,
                node=node,
            )
        )
        if prior is None:
            plan.new_count += 1
        else:
            plan.updated_count += 1

    return plan


def record_synced_items(
    db: Session,
    tenant_id: uuid.UUID,
    source: str,
    ledger_items: list[LedgerItem],
) -> None:
    """Upsert ledger rows for items successfully sent to Cognee."""
    if not ledger_items:
        return

    now = datetime.now(UTC).replace(tzinfo=None)
    keys = [item.external_key for item in ledger_items]
    existing_rows = (
        db.query(IntegrationSyncRecord)
        .filter(
            IntegrationSyncRecord.tenant_id == tenant_id,
            IntegrationSyncRecord.source == source,
            IntegrationSyncRecord.external_key.in_(keys),
        )
        .all()
    )
    by_key = {row.external_key: row for row in existing_rows}

    for item in ledger_items:
        row = by_key.get(item.external_key)
        if row is None:
            row = IntegrationSyncRecord(
                tenant_id=tenant_id,
                source=source,
                external_key=item.external_key,
            )
            db.add(row)
        row.content_version = item.content_version
        row.display_label = item.display_label
        row.synced_at = now


def count_graph_edges(data_points: list[Any]) -> int:
    """Count relationship edges on graph nodes slated for ingest."""
    edge_attrs = (
        "contributedTo",
        "modifies",
        "assignedTo",
        "blocksComponent",
        "documentedBy",
        "authoredBy",
        "resolvedBy",
        "discussesComponent",
        "documentsComponent",
        "blameAttributedTo",
    )
    total = 0
    for node in data_points:
        for attr in edge_attrs:
            if getattr(node, attr, None):
                total += 1
    return total

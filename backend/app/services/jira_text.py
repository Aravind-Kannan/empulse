"""Plain-text helpers for Jira ADF payloads."""

from __future__ import annotations

from typing import Any


def adf_to_plain_text(node: Any) -> str:
    """Convert Atlassian Document Format (API v3) to plain text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_to_plain_text(item) for item in node)
    if not isinstance(node, dict):
        return str(node)

    node_type = str(node.get("type") or "")
    if node_type == "text":
        return str(node.get("text") or "")

    parts: list[str] = []
    for child in node.get("content") or []:
        parts.append(adf_to_plain_text(child))

    if node_type in {"paragraph", "heading", "listItem", "blockquote", "rule"}:
        parts.append("\n")
    elif node_type in {"bulletList", "orderedList"}:
        parts.append("\n")

    return "".join(parts)


def truncate_jira_text(text: str, *, max_len: int = 2000) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[: max_len - 1]}…"

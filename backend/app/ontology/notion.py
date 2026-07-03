"""Notion → canonical ontology normalizers."""

from __future__ import annotations

from app.ontology.canonical import (
    CanonicalComponentRef,
    CanonicalDocument,
    CanonicalPersonRef,
)
from app.ontology.jira_keys import extract_jira_issue_keys
from app.services.notion_types import NotionDocRecord


def normalize_notion_document(
    doc: NotionDocRecord,
    *,
    components_by_id: dict,
    employee_names: dict[str, str] | None = None,
) -> CanonicalDocument | None:
    if doc.is_archived or doc.is_inaccessible:
        return None

    component_ref = None
    if doc.component_id and doc.component_id in components_by_id:
        comp = components_by_id[doc.component_id]
        component_ref = CanonicalComponentRef(
            component_id=doc.component_id,
            name=getattr(comp, "name", ""),
        )

    author = None
    if doc.owner_employee_id:
        author = CanonicalPersonRef(
            employee_id=doc.owner_employee_id,
            provider="notion",
            provider_user_id=doc.owner_email or doc.owner_employee_id,
            display_name=(employee_names or {}).get(doc.owner_employee_id, ""),
        )

    return CanonicalDocument(
        source="notion",
        page_id=doc.page_id,
        title=doc.title,
        last_edited=doc.last_edited_at.isoformat(),
        page_url=doc.page_url,
        doc_kind=doc.page_kind,
        author=author,
        component=component_ref,
        referenced_work_item_ids=extract_jira_issue_keys(doc.title),
    )

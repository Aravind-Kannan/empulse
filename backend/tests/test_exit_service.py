"""Exit handover Cognee synthesis service."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from app.services.exit_service import compile_exit_handover_file

from tests.conftest import add_employee


def test_compile_exit_handover_file_structure(db, tenant):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-handover-001",
        name="Alice Chen",
        email="alice@acme.com",
    )

    with patch(
        "app.services.exit_service._cognee_handover_research",
        new_callable=AsyncMock,
        return_value={
            "knowledge": [],
            "incidents": [],
            "operations": [],
            "documentation": [],
            "blast_radius": [],
        },
    ):
        markdown = asyncio.run(
            compile_exit_handover_file(db, employee.id, tenant.id)
        )

    assert markdown.startswith("# Employee Handover Blueprint: Alice Chen")
    assert "## 1. System Components Requiring Transfer" in markdown
    assert "## 2. Active Open Tasks (Jira Operations)" in markdown
    assert "## 3. Implicit Troubleshooting Areas (Slack Context Extracted)" in markdown
    assert "## 4. Documentation Gaps & Untracked Hotfixes Needing Writeups" in markdown

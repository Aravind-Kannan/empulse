"""Member roster sync should replace stale employees on re-import."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.models.operational import Employee
from app.schemas.employee_master import (
    EmployeeMasterDataResponse,
    FetchUsersRequest,
    MasterDataEmployee,
)
from app.services.member_roster_sync import sync_member_roster

from tests.conftest import add_employee


@pytest.mark.asyncio
async def test_sync_member_roster_replace_removes_stale_employees(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-stale",
        name="Stale User",
        email="stale@acme.com",
    )

    master = EmployeeMasterDataResponse(
        company=tenant.company_name,
        employees=[
            MasterDataEmployee(
                id="emp-fresh",
                name="Fresh User",
                role="Engineer",
                email="fresh@acme.com",
                tenure_years=1.0,
                manager_id=None,
            )
        ],
        sources_queried=["slack"],
        roles_discovered=["Engineer"],
        records_merged=1,
        hierarchy_mode="flat",
        source_errors=[],
    )

    with patch(
        "app.services.member_roster_sync.fetch_employee_master_data",
        return_value=master,
    ):
        with patch(
            "app.services.member_roster_sync.ingest_org_chart_to_cognee",
            new_callable=AsyncMock,
            return_value={
                "cognee_dataset": "ds",
                "graph_nodes_created": 0,
                "graph_edges_created": 0,
            },
        ):
            await sync_member_roster(
                db,
                tenant,
                FetchUsersRequest(sources=["slack"], company=tenant.company_name),
                replace_existing=True,
            )

    remaining = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant.id)
        .order_by(Employee.email)
        .all()
    )
    assert len(remaining) == 1
    assert remaining[0].email == "fresh@acme.com"


@pytest.mark.asyncio
async def test_sync_member_roster_merge_keeps_unmatched_existing(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-stale",
        name="Stale User",
        email="stale@acme.com",
    )

    master = EmployeeMasterDataResponse(
        company=tenant.company_name,
        employees=[
            MasterDataEmployee(
                id="emp-fresh",
                name="Fresh User",
                role="Engineer",
                email="fresh@acme.com",
                tenure_years=1.0,
                manager_id=None,
            )
        ],
        sources_queried=["slack"],
        roles_discovered=["Engineer"],
        records_merged=1,
        hierarchy_mode="flat",
        source_errors=[],
    )

    with patch(
        "app.services.member_roster_sync.fetch_employee_master_data",
        return_value=master,
    ):
        with patch(
            "app.services.member_roster_sync.ingest_org_chart_to_cognee",
            new_callable=AsyncMock,
            return_value={
                "cognee_dataset": "ds",
                "graph_nodes_created": 0,
                "graph_edges_created": 0,
            },
        ):
            await sync_member_roster(
                db,
                tenant,
                FetchUsersRequest(sources=["slack"], company=tenant.company_name),
                replace_existing=False,
            )

    emails = {
        employee.email
        for employee in db.query(Employee).filter(Employee.tenant_id == tenant.id).all()
    }
    assert emails == {"fresh@acme.com", "stale@acme.com"}

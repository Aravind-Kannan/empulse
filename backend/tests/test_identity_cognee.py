"""Tests for identity → Cognee graph sync."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from app.models.operational import Employee, EmployeeIdentity
from app.schemas.identity import EmployeeIdentityMapping
from app.services.cognee_ingest import build_graph_employee, build_tenant_org_graph_nodes
from app.services.identity_cognee import sync_employee_identities_to_cognee
from app.services.identity_mapping import save_identity_mappings

from tests.conftest import add_employee


def test_build_graph_employee_includes_provider_ids(db, tenant):
    add_employee(
        db,
        tenant.id,
        employee_id="emp-1",
        name="Ben Rivera",
        email="ben@acme.com",
    )
    db.add(
        EmployeeIdentity(
            tenant_id=tenant.id,
            employee_id="emp-1",
            provider="github",
            provider_username_or_id="gh-benrivera",
            confidence="confirmed",
        )
    )
    db.add(
        EmployeeIdentity(
            tenant_id=tenant.id,
            employee_id="emp-1",
            provider="slack",
            provider_username_or_id="U02BEN",
            confidence="confirmed",
        )
    )
    db.commit()

    employee = db.query(Employee).filter(Employee.id == "emp-1").one()
    identities = (
        db.query(EmployeeIdentity)
        .filter(EmployeeIdentity.employee_id == "emp-1")
        .all()
    )
    node = build_graph_employee(employee, identities)
    assert node.github_id == "gh-benrivera"
    assert node.slack_id == "U02BEN"
    assert node.jira_id == ""


def test_build_tenant_org_graph_nodes_loads_identities(db, tenant):
    add_employee(db, tenant.id, employee_id="emp-1", name="Ben", email="ben@acme.com")
    db.add(
        EmployeeIdentity(
            tenant_id=tenant.id,
            employee_id="emp-1",
            provider="github",
            provider_username_or_id="gh-benrivera",
            confidence="confirmed",
        )
    )
    db.commit()

    employee_nodes, _, _ = build_tenant_org_graph_nodes(db, tenant.id)
    assert employee_nodes["emp-1"].github_id == "gh-benrivera"


def test_save_identity_mappings_syncs_employee_to_cognee(db, tenant):
    add_employee(db, tenant.id, employee_id="emp-1", name="Ben", email="ben@acme.com")

    with patch(
        "app.services.identity_cognee.sync_employee_identities_to_cognee",
        new_callable=AsyncMock,
    ) as sync_mock:
        from app.routes.identity import update_identity_mappings
        from app.schemas.identity import IdentityMappingsUpdateRequest

        saved = asyncio.run(
            update_identity_mappings(
                IdentityMappingsUpdateRequest(
                    mappings=[
                        EmployeeIdentityMapping(
                            employee_id="emp-1",
                            provider="github",
                            provider_username_or_id="gh-benrivera",
                        )
                    ]
                ),
                tenant,
                db,
            )
        )

    assert len(saved) == 1
    sync_mock.assert_awaited_once()
    assert sync_mock.await_args.args[1] == tenant.id
    assert sync_mock.await_args.args[2] == {"emp-1"}


def test_sync_employee_identities_to_cognee_pushes_single_person(db, tenant):
    add_employee(db, tenant.id, employee_id="emp-1", name="Ben", email="ben@acme.com")
    save_identity_mappings(
        db,
        tenant,
        [
            EmployeeIdentityMapping(
                employee_id="emp-1",
                provider="github",
                provider_username_or_id="gh-benrivera",
            )
        ],
    )

    with patch(
        "app.services.identity_cognee.tenant_add_data_points",
        new_callable=AsyncMock,
    ) as add_mock, patch(
        "app.services.identity_cognee.tenant_add_and_cognify",
        new_callable=AsyncMock,
    ) as cognify_mock:
        result = asyncio.run(
            sync_employee_identities_to_cognee(db, tenant.id, {"emp-1"})
        )

    assert result["synced"] == 1
    add_mock.assert_awaited_once()
    pushed = add_mock.await_args.args[1]
    assert len(pushed) == 1
    assert pushed[0].external_id == "emp-1"
    assert pushed[0].github_id == "gh-benrivera"
    cognify_mock.assert_awaited_once()

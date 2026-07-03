"""ERA Step 16 — exit handover bridge tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.schemas.era import EraEvidenceItem, EraMitigationItem
from app.services.exit_handover import (
    EraHandoverContext,
    _render_open_mitigations,
    build_handover_markdown,
)
from app.tenancy import TENANT_HEADER

from tests.conftest import add_employee


@pytest.fixture()
def client(db):
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_cognee_handover_search():
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
        yield


def test_handover_without_prefill_has_no_era_sections(client, db, tenant):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-exit-001",
        name="Exit Engineer",
        email="exit@acme.com",
    )
    response = client.get(
        f"/api/exit/handover?id={employee.id}",
        headers={TENANT_HEADER: str(tenant.id)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["prefill_from_era"] is False
    assert payload["era_sections_included"] == []
    assert "ERA risk assessment" not in payload["markdown"]
    assert "Employee Handover Blueprint:" in payload["markdown"]


def test_handover_prefill_era_includes_sections(client, db, tenant, monkeypatch):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-exit-002",
        name="Exit ERA Engineer",
        email="exit-era@acme.com",
    )
    ctx = EraHandoverContext(
        computed_at=datetime.now(UTC),
        demo_mode=False,
        excluded=False,
        risk_score=72.0,
        risk_level="high",
        evidence=[
            EraEvidenceItem(
                id="ev-handover-1",
                dimension="knowledge",
                title="SPOF on Payment Gateway",
                description="Single owner on tier-1 component.",
                severity="high",
                impact_points=18.0,
                sources=[],
            )
        ],
    )
    monkeypatch.setattr(
        "app.services.exit_handover._load_era_handover_context",
        lambda *_args, **_kwargs: ctx,
    )
    response = client.get(
        f"/api/exit/handover?id={employee.id}&prefill=era",
        headers={TENANT_HEADER: str(tenant.id)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["prefill_from_era"] is True
    assert payload["era_computed_at"] is not None
    assert payload["era_risk_score"] is not None
    assert len(payload["era_sections_included"]) >= 1
    markdown = payload["markdown"]
    assert "ERA risk assessment" in markdown
    assert "computed at" in markdown
    assert "## Critical Knowledge to Transfer" in markdown or "## ERA Risk Context" in markdown


def test_open_mitigations_render_as_checklist():
    items = [
        EraMitigationItem(
            evidence_id="ev-1",
            title="Add backup owner in CODEOWNERS",
            priority="critical",
            mitigation_status="open",
        ),
        EraMitigationItem(
            evidence_id="ev-2",
            title="Pair on next 2 PRs with backup engineer",
            priority="high",
            mitigation_status="in_progress",
        ),
    ]
    block, keys = _render_open_mitigations(items)
    assert keys == ["open_mitigations"]
    assert "- [ ] Add backup owner in CODEOWNERS" in block
    assert "- [ ] Pair on next 2 PRs with backup engineer _(in progress)_" in block


def test_handover_prefill_era_includes_open_mitigations(db, tenant, monkeypatch):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-exit-mit",
        name="Exit Mitigation Owner",
        email="exit-mit@acme.com",
    )
    ctx = EraHandoverContext(
        computed_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        demo_mode=False,
        excluded=False,
        risk_score=78.0,
        risk_level="high",
        mitigations=[
            EraMitigationItem(
                evidence_id="ev-mit-1",
                title="Add backup owner in CODEOWNERS",
                priority="critical",
                mitigation_status="open",
            )
        ],
    )
    monkeypatch.setattr(
        "app.services.exit_handover._load_era_handover_context",
        lambda *_args, **_kwargs: ctx,
    )

    response = asyncio.run(
        build_handover_markdown(
            db,
            employee.id,
            tenant,
            prefill_era=True,
        )
    )
    assert response.prefill_from_era is True
    assert "open_mitigations" in response.era_sections_included
    assert "- [ ] Add backup owner in CODEOWNERS" in response.markdown


def test_leadership_handover_skips_era_sections(db, tenant):
    employee = add_employee(
        db,
        tenant.id,
        employee_id="emp-leader",
        name="VP Engineering",
        email="vp@acme.com",
    )
    employee.role = "Engineering Manager"
    db.commit()

    response = asyncio.run(
        build_handover_markdown(
            db,
            employee.id,
            tenant,
            prefill_era=True,
        )
    )
    assert response.prefill_from_era is False
    assert response.era_sections_included == []
    assert "ERA risk assessment" not in response.markdown


def test_demo_mode_warning_in_era_header():
    ctx = EraHandoverContext(
        computed_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        demo_mode=True,
        excluded=False,
        risk_score=72.0,
        risk_level="high",
    )
    from app.services.exit_handover import _era_header_lines

    lines = _era_header_lines(ctx)
    assert any("Demo mode" in line for line in lines)
    assert any("ERA risk assessment" in line for line in lines)

"""Consolidate duplicate GitHub auto-provisioned components."""

from __future__ import annotations

from app.models.operational import Component
from app.services.component_management import consolidate_duplicate_components
from app.services.employee_ids import scope_component_id


def test_consolidate_merges_same_github_path_different_names(db, tenant):
    scoped_id = scope_component_id("comp-gh-aravind-kannan-empulse-notion-docs", tenant.id)
    db.add(
        Component(
            id=scoped_id,
            tenant_id=tenant.id,
            name="empulse / notion-docs",
            description="AUTO:github:Aravind-Kannan/empulse:notion-docs/",
        )
    )
    db.add(
        Component(
            id="comp-gh-aravind-kannan-empulse-notion-docs",
            tenant_id=tenant.id,
            name="Aravind-Kannan/empulse / Notion Docs",
            description="AUTO:github:Aravind-Kannan/empulse:notion-docs/",
        )
    )
    db.commit()

    removed = consolidate_duplicate_components(db, tenant.id)

    assert removed == 1
    remaining = db.query(Component).filter(Component.tenant_id == tenant.id).all()
    assert len(remaining) == 1
    assert remaining[0].id == scoped_id

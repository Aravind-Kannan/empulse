"""GitHub SPOF detection — shared ownership should not false-positive."""

from __future__ import annotations

from app.services.integration_telemetry import (
    SPOF_BACKUP_CONTRIBUTOR_MIN,
    is_github_spof_component,
    spof_components_from_telemetry,
)


def test_dominant_owner_is_spof():
    assert is_github_spof_component({"emp-a": 90.0, "emp-b": 10.0}) is True


def test_shared_ownership_bus_factor_one_not_spof():
    """empulse/backend-style split: three meaningful contributors."""
    contributors = {
        "emp-a": 49.6,
        "emp-b": 25.7,
        "emp-c": 24.7,
    }
    assert is_github_spof_component(contributors, bus_factor=1) is False


def test_two_meaningful_contributors_bus_factor_one_not_spof():
    assert is_github_spof_component({"emp-a": 60.0, "emp-b": 40.0}, bus_factor=1) is False


def test_bus_factor_one_single_meaning_contributor_is_spof():
    assert is_github_spof_component({"emp-a": 70.0, "emp-b": 15.0}, bus_factor=1) is True


def test_bus_factor_two_not_spof_without_dominant_owner():
    assert is_github_spof_component({"emp-a": 60.0, "emp-b": 40.0}, bus_factor=2) is False


def test_spof_components_from_telemetry_mixed():
    ownership = {
        "comp-shared": {"emp-a": 49.6, "emp-b": 25.7, "emp-c": 24.7},
        "comp-solo": {"emp-a": 70.0, "emp-b": 15.0},
        "comp-dominant": {"emp-a": 92.0, "emp-b": 8.0},
    }
    bus_factors = {
        "comp-shared": 1,
        "comp-solo": 1,
        "comp-dominant": 1,
    }
    spof = spof_components_from_telemetry(ownership, bus_factors)
    assert "comp-shared" not in spof
    assert "comp-solo" in spof
    assert "comp-dominant" in spof


def test_backup_contributor_min_threshold():
    just_below = SPOF_BACKUP_CONTRIBUTOR_MIN - 0.1
    assert (
        is_github_spof_component(
            {"emp-a": 80.0, "emp-b": just_below},
            bus_factor=1,
        )
        is True
    )
    assert (
        is_github_spof_component(
            {"emp-a": 60.0, "emp-b": SPOF_BACKUP_CONTRIBUTOR_MIN},
            bus_factor=1,
        )
        is False
    )

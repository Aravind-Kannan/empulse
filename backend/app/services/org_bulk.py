from __future__ import annotations

import re

from app.schemas.org import EmployeeSchema, OrgChartIngestRequest
from app.schemas.org_bulk import BulkCsvRow, BulkDiffEntry
from app.services.role_utils import is_leadership_role


def _slug_id(email: str) -> str:
    local = email.split("@")[0].lower()
    slug = re.sub(r"[^a-z0-9]+", "-", local).strip("-")
    return f"emp-{slug}"


def _resolve_manager_id(
    reports_to: str | None,
    employee_id: str,
    id_index: dict[str, str],
    email_index: dict[str, str],
) -> str | None:
    if not reports_to or not reports_to.strip():
        return None

    target = reports_to.strip()
    target_lower = target.lower()

    if target == employee_id:
        return None

    if target in id_index:
        return id_index[target]

    if target_lower in email_index:
        resolved = email_index[target_lower]
        return None if resolved == employee_id else resolved

    return None


def _detect_cycle(employees: list[EmployeeSchema]) -> list[str]:
    errors: list[str] = []
    by_id = {employee.id: employee for employee in employees}

    for employee in employees:
        if not employee.manager_id:
            continue
        visited: set[str] = set()
        current: str | None = employee.manager_id
        while current:
            if current == employee.id:
                errors.append(
                    f"Cyclical reporting line detected for '{employee.name}' ({employee.email}).",
                )
                break
            if current in visited:
                break
            visited.add(current)
            manager = by_id.get(current)
            current = manager.manager_id if manager else None

    return errors


def rows_to_employees(rows: list[BulkCsvRow]) -> tuple[list[EmployeeSchema], list[str]]:
    errors: list[str] = []

    if not rows:
        return [], ["CSV contains no employee rows."]

    id_index = {row.id.strip(): row.id.strip() for row in rows if row.id.strip()}
    email_index = {str(row.email).lower(): row.id.strip() for row in rows}

    employees: list[EmployeeSchema] = []
    seen_ids: set[str] = set()
    seen_emails: set[str] = set()

    for index, row in enumerate(rows, start=1):
        employee_id = row.id.strip() or _slug_id(str(row.email))
        email = str(row.email).lower()

        if employee_id in seen_ids:
            errors.append(f"Row {index}: duplicate id '{employee_id}'.")
            continue
        if email in seen_emails:
            errors.append(f"Row {index}: duplicate email '{row.email}'.")
            continue

        seen_ids.add(employee_id)
        seen_emails.add(email)

        manager_id = _resolve_manager_id(
            row.reports_to_email_or_id,
            employee_id,
            id_index,
            email_index,
        )

        if row.reports_to_email_or_id and row.reports_to_email_or_id.strip() and not manager_id:
            errors.append(
                f"Row {index}: unknown reports_to '{row.reports_to_email_or_id}' for '{row.name}'.",
            )

        team_name = row.team_name.strip() if row.team_name and row.team_name.strip() else None

        employees.append(
            EmployeeSchema(
                id=employee_id,
                name=row.name.strip(),
                role=row.dynamic_role.strip(),
                email=row.email,
                tenure_years=0,
                manager_id=manager_id,
                team_name=team_name,
            )
        )

    errors.extend(_detect_cycle(employees))
    return employees, errors


def merge_bulk_org(
    company: str,
    rows: list[BulkCsvRow],
    current_org: OrgChartIngestRequest | None,
) -> tuple[OrgChartIngestRequest | None, list[str], list[BulkDiffEntry]]:
    employees, errors = rows_to_employees(rows)
    if errors:
        return None, errors, []

    current = current_org
    current_employees = {employee.id: employee for employee in (current.employees if current else [])}
    next_ids = {employee.id for employee in employees}

    diff: list[BulkDiffEntry] = []

    for employee in employees:
        previous = current_employees.get(employee.id)
        if not previous:
            diff.append(
                BulkDiffEntry(
                    kind="added",
                    employee_id=employee.id,
                    name=employee.name,
                    changes=["New employee record"],
                )
            )
            continue

        changes: list[str] = []
        if previous.name != employee.name:
            changes.append(f"name: {previous.name} → {employee.name}")
        if previous.email != employee.email:
            changes.append(f"email: {previous.email} → {employee.email}")
        if previous.role != employee.role:
            changes.append(f"role: {previous.role} → {employee.role}")
        if (previous.team_name or "") != (employee.team_name or ""):
            changes.append(
                f"team: {previous.team_name or '—'} → {employee.team_name or '—'}",
            )
        if previous.manager_id != employee.manager_id:
            changes.append("reporting hierarchy updated")

        if changes:
            diff.append(
                BulkDiffEntry(
                    kind="modified",
                    employee_id=employee.id,
                    name=employee.name,
                    changes=changes,
                )
            )

    for employee_id, previous in current_employees.items():
        if employee_id not in next_ids:
            diff.append(
                BulkDiffEntry(
                    kind="removed",
                    employee_id=employee_id,
                    name=previous.name,
                    changes=["Removed from directory"],
                )
            )

    components = current.components if current else []
    assignments = [
        assignment
        for assignment in (current.assignments if current else [])
        if assignment.employee_id in next_ids
    ]

    merged = OrgChartIngestRequest(
        company=company,
        employees=employees,
        components=components,
        assignments=assignments,
    )

    return merged, [], diff


def build_bulk_reindex_narrative(org: OrgChartIngestRequest) -> str:
    lines = [
        f"Bulk organizational re-index for {org.company}.",
        f"Total employees: {len(org.employees)}.",
    ]
    leadership = [employee for employee in org.employees if is_leadership_role(employee.role)]
    if leadership:
        lines.append(f"Leadership nodes: {', '.join(employee.name for employee in leadership)}.")

    teams = sorted({employee.team_name for employee in org.employees if employee.team_name})
    if teams:
        lines.append(f"Team tags: {', '.join(teams)}.")

    for employee in org.employees:
        manager = next(
            (item.name for item in org.employees if item.id == employee.manager_id),
            None,
        )
        team = f", team={employee.team_name}" if employee.team_name else ""
        lines.append(
            f"{employee.name} ({employee.role}{team}) reports to {manager or 'no one'}.",
        )

    return "\n".join(lines)

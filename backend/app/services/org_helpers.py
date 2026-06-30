from app.schemas.org import EmployeeSchema


def would_create_cycle(
    employees: list[EmployeeSchema],
    employee_id: str,
    manager_id: str | None,
) -> bool:
    if manager_id is None or manager_id == employee_id:
        return manager_id == employee_id

    by_id = {employee.id: employee for employee in employees}
    current: str | None = manager_id
    visited: set[str] = set()

    while current:
        if current == employee_id:
            return True
        if current in visited:
            return False
        visited.add(current)
        manager = by_id.get(current)
        current = manager.manager_id if manager else None

    return False

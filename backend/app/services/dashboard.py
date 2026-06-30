from sqlalchemy.orm import Session

from app.models.operational import Employee
from app.schemas.exit import DashboardMetrics
from app.schemas.org import ACME_ORG_CHART
from app.services.investigation import list_incidents
from app.services.kra_analytics import get_kra_graph


def get_dashboard_metrics(db: Session) -> DashboardMetrics:
    employees = db.query(Employee).all()

    if not employees:
        employees_data = ACME_ORG_CHART.employees
        avg_tenure = sum(e.tenure_years for e in employees_data) / len(employees_data)
        employee_count = len(employees_data)
    else:
        avg_tenure = sum(e.tenure_years for e in employees) / len(employees)
        employee_count = len(employees)

    incidents = list_incidents().incidents
    open_incident_count = sum(
        1
        for incident in incidents
        if incident.status not in ("Resolved", "Closed")
    )

    kra = get_kra_graph(db)
    active_spof_count = sum(
        1 for node in kra.nodes if node.type == "component" and node.is_spof
    )

    return DashboardMetrics(
        average_attrition_rate=12.0,
        average_tenure_years=round(avg_tenure, 1),
        open_incident_count=open_incident_count,
        active_spof_count=active_spof_count,
        employee_count=employee_count,
    )

from sqlalchemy.orm import Session

from app.models.operational import Employee
from app.models.tenant import Tenant
from app.schemas.exit import DashboardMetrics
from app.services.investigation import list_incidents
from app.services.kra_analytics import get_kra_graph


def get_dashboard_metrics(db: Session, tenant: Tenant) -> DashboardMetrics:
    employees = db.query(Employee).filter(Employee.tenant_id == tenant.id).all()

    if not employees:
        employee_count = 0
        avg_tenure = 0.0
    else:
        avg_tenure = sum(e.tenure_years for e in employees) / len(employees)
        employee_count = len(employees)

    incidents = list_incidents(db, tenant).incidents
    open_incident_count = sum(
        1
        for incident in incidents
        if incident.status not in ("Resolved", "Closed")
    )

    kra = get_kra_graph(db, tenant)
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

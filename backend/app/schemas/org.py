from pydantic import BaseModel, EmailStr, Field


class EmployeeSchema(BaseModel):
    id: str
    name: str
    role: str
    email: EmailStr
    tenure_years: float = Field(ge=0)
    manager_id: str | None = None
    team_name: str | None = None


class ComponentSchema(BaseModel):
    id: str
    name: str
    description: str = ""
    tags: str = ""
    criticality: str = "tier2_core"
    open_tasks_count: int = Field(default=0, ge=0)
    unresolved_incidents: int = Field(default=0, ge=0)


class AssignmentSchema(BaseModel):
    employee_id: str
    component_id: str
    codebase_share_pct: float = Field(ge=0, le=100)


class OrgChartIngestRequest(BaseModel):
    company: str = "Acme Company"
    employees: list[EmployeeSchema]
    components: list[ComponentSchema] = Field(default_factory=list)
    assignments: list[AssignmentSchema] = Field(default_factory=list)


class OrgChartIngestResponse(BaseModel):
    company: str
    employees_persisted: int
    components_persisted: int
    assignments_persisted: int
    cognee_dataset: str
    graph_nodes_created: int
    graph_edges_created: int


ACME_ORG_CHART = OrgChartIngestRequest(
    company="Acme Company",
    employees=[
        EmployeeSchema(
            id="emp-manager-001",
            name="Alice Chen",
            role="Manager",
            email="alice.chen@acme.com",
            tenure_years=6.5,
            manager_id=None,
        ),
        EmployeeSchema(
            id="emp-eng-001",
            name="Ben Rivera",
            role="Engineer",
            email="ben.rivera@acme.com",
            tenure_years=3.2,
            manager_id="emp-manager-001",
        ),
        EmployeeSchema(
            id="emp-eng-002",
            name="Cara Patel",
            role="Engineer",
            email="cara.patel@acme.com",
            tenure_years=4.0,
            manager_id="emp-manager-001",
        ),
        EmployeeSchema(
            id="emp-eng-003",
            name="Diego Alvarez",
            role="Engineer",
            email="diego.alvarez@acme.com",
            tenure_years=2.1,
            manager_id="emp-manager-001",
        ),
        EmployeeSchema(
            id="emp-eng-004",
            name="Elena Kowalski",
            role="Engineer",
            email="elena.kowalski@acme.com",
            tenure_years=1.5,
            manager_id="emp-manager-001",
        ),
        EmployeeSchema(
            id="emp-support-001",
            name="Frank Osei",
            role="Support",
            email="frank.osei@acme.com",
            tenure_years=2.8,
            manager_id="emp-manager-001",
        ),
    ],
    components=[
        ComponentSchema(
            id="comp-payments",
            name="Payment Gateway",
            description="Handles checkout, refunds, and payment provider integrations.",
            open_tasks_count=7,
            unresolved_incidents=2,
        ),
        ComponentSchema(
            id="comp-auth",
            name="Auth Service",
            description="Identity, SSO, and session management.",
            open_tasks_count=4,
            unresolved_incidents=1,
        ),
        ComponentSchema(
            id="comp-notifications",
            name="Notification Hub",
            description="Email, Slack, and webhook delivery pipeline.",
            open_tasks_count=3,
            unresolved_incidents=0,
        ),
    ],
    assignments=[
        AssignmentSchema(
            employee_id="emp-eng-001",
            component_id="comp-payments",
            codebase_share_pct=45.0,
        ),
        AssignmentSchema(
            employee_id="emp-eng-002",
            component_id="comp-auth",
            codebase_share_pct=55.0,
        ),
        AssignmentSchema(
            employee_id="emp-eng-003",
            component_id="comp-payments",
            codebase_share_pct=35.0,
        ),
        AssignmentSchema(
            employee_id="emp-eng-004",
            component_id="comp-notifications",
            codebase_share_pct=60.0,
        ),
        AssignmentSchema(
            employee_id="emp-support-001",
            component_id="comp-notifications",
            codebase_share_pct=15.0,
        ),
    ],
)

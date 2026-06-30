import type { OrgChartPayload } from "./types";

export const ACME_ORG_CHART: OrgChartPayload = {
  company: "Acme Company",
  employees: [
    {
      id: "emp-manager-001",
      name: "Alice Chen",
      role: "Manager",
      email: "alice.chen@acme.com",
      tenure_years: 6.5,
      manager_id: null,
    },
    {
      id: "emp-eng-001",
      name: "Ben Rivera",
      role: "Engineer",
      email: "ben.rivera@acme.com",
      tenure_years: 3.2,
      manager_id: "emp-manager-001",
    },
    {
      id: "emp-eng-002",
      name: "Cara Patel",
      role: "Engineer",
      email: "cara.patel@acme.com",
      tenure_years: 4.0,
      manager_id: "emp-manager-001",
    },
    {
      id: "emp-eng-003",
      name: "Diego Alvarez",
      role: "Engineer",
      email: "diego.alvarez@acme.com",
      tenure_years: 2.1,
      manager_id: "emp-manager-001",
    },
    {
      id: "emp-eng-004",
      name: "Elena Kowalski",
      role: "Engineer",
      email: "elena.kowalski@acme.com",
      tenure_years: 1.5,
      manager_id: "emp-manager-001",
    },
    {
      id: "emp-support-001",
      name: "Frank Osei",
      role: "Support",
      email: "frank.osei@acme.com",
      tenure_years: 2.8,
      manager_id: "emp-manager-001",
    },
  ],
  components: [
    {
      id: "comp-payments",
      name: "Payment Gateway",
      description:
        "Handles checkout, refunds, and payment provider integrations.",
      open_tasks_count: 7,
      unresolved_incidents: 2,
    },
    {
      id: "comp-auth",
      name: "Auth Service",
      description: "Identity, SSO, and session management.",
      open_tasks_count: 4,
      unresolved_incidents: 1,
    },
    {
      id: "comp-notifications",
      name: "Notification Hub",
      description: "Email, Slack, and webhook delivery pipeline.",
      open_tasks_count: 3,
      unresolved_incidents: 0,
    },
  ],
  assignments: [
    {
      employee_id: "emp-eng-001",
      component_id: "comp-payments",
      codebase_share_pct: 45,
    },
    {
      employee_id: "emp-eng-002",
      component_id: "comp-auth",
      codebase_share_pct: 55,
    },
    {
      employee_id: "emp-eng-003",
      component_id: "comp-payments",
      codebase_share_pct: 35,
    },
    {
      employee_id: "emp-eng-004",
      component_id: "comp-notifications",
      codebase_share_pct: 60,
    },
    {
      employee_id: "emp-support-001",
      component_id: "comp-notifications",
      codebase_share_pct: 15,
    },
  ],
};

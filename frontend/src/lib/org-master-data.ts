import type { EmployeeMasterDataResponse, OrgChartPayload } from "./types";

export function masterDataToOrgChart(
  master: EmployeeMasterDataResponse,
  company: string,
): OrgChartPayload {
  return {
    company: company || master.company,
    employees: master.employees.map((employee) => ({
      id: employee.id,
      name: employee.name,
      email: employee.email,
      role: employee.role,
      tenure_years: employee.tenure_years,
      manager_id: employee.manager_id,
    })),
    components: [],
    assignments: [],
  };
}

export function collectOrgRoles(employees: OrgChartPayload["employees"]): string[] {
  return [...new Set(employees.map((employee) => employee.role).filter(Boolean))].sort();
}

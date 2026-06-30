import Papa from "papaparse";

import type { BulkCsvRow, OrgChartPayload } from "./types";

export const CSV_HEADERS = [
  "id",
  "name",
  "email",
  "dynamic_role",
  "team_name",
  "reports_to_email_or_id",
] as const;

export function exportOrgChartCsv(orgChart: OrgChartPayload): void {
  const rows: BulkCsvRow[] = orgChart.employees.map((employee) => {
    const manager = employee.manager_id
      ? orgChart.employees.find((item) => item.id === employee.manager_id)
      : null;

    return {
      id: employee.id,
      name: employee.name,
      email: employee.email,
      dynamic_role: employee.role,
      team_name: employee.team_name ?? "",
      reports_to_email_or_id: manager?.email ?? manager?.id ?? "",
    };
  });

  const csv = Papa.unparse(rows, { columns: [...CSV_HEADERS] });
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${orgChart.company.replace(/\s+/g, "_").toLowerCase()}_org_chart.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function normalizeHeader(header: string): string {
  return header.trim().toLowerCase().replace(/\s+/g, "_");
}

const HEADER_ALIASES: Record<string, keyof BulkCsvRow> = {
  id: "id",
  name: "name",
  email: "email",
  dynamic_role: "dynamic_role",
  role: "dynamic_role",
  title: "dynamic_role",
  team_name: "team_name",
  team: "team_name",
  reports_to_email_or_id: "reports_to_email_or_id",
  reports_to: "reports_to_email_or_id",
  manager: "reports_to_email_or_id",
};

export function parseOrgChartCsv(file: File): Promise<BulkCsvRow[]> {
  return new Promise((resolve, reject) => {
    Papa.parse<Record<string, string>>(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        if (results.errors.length > 0) {
          reject(new Error(results.errors[0]?.message ?? "CSV parse failed"));
          return;
        }

        const rows: BulkCsvRow[] = [];

        for (const raw of results.data) {
          const mapped: Partial<BulkCsvRow> = {};
          for (const [header, value] of Object.entries(raw)) {
            const key = HEADER_ALIASES[normalizeHeader(header)];
            if (key) {
              mapped[key] = String(value ?? "").trim();
            }
          }

          if (!mapped.email && !mapped.name) continue;

          rows.push({
            id: mapped.id ?? "",
            name: mapped.name ?? "",
            email: mapped.email ?? "",
            dynamic_role: mapped.dynamic_role ?? "Team Member",
            team_name: mapped.team_name ?? "",
            reports_to_email_or_id: mapped.reports_to_email_or_id ?? "",
          });
        }

        resolve(rows);
      },
      error: (error) => reject(error),
    });
  });
}

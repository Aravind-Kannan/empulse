import type { Employee } from "./types";

export function slugEmployeeId(email: string): string {
  const local = email.split("@")[0]?.toLowerCase() ?? "employee";
  const slug = local.replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `emp-${slug || "new"}`;
}

export function generateUniqueEmployeeId(
  email: string,
  existingEmployees: Employee[],
): string {
  const base = slugEmployeeId(email);
  const used = new Set(existingEmployees.map((employee) => employee.id));
  if (!used.has(base)) return base;

  let suffix = 2;
  while (used.has(`${base}-${suffix}`)) {
    suffix += 1;
  }
  return `${base}-${suffix}`;
}

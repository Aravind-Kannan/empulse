import Link from "next/link";

import type { EraDimensionKey, EraEmployeeMetrics, EraRiskHistoryPoint } from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";
import { EraDimensionDonut } from "./EraDimensionDonut";
import { EraRiskSparkline } from "./EraRiskSparkline";
import { dimensionValue } from "./era-utils";

interface EraTeamCompositionProps {
  employees: EraEmployeeMetrics[];
  topRiskDriver: EraDimensionKey;
  teamHistory?: EraRiskHistoryPoint[];
}

export function EraTeamComposition({
  employees,
  topRiskDriver,
  teamHistory = [],
}: EraTeamCompositionProps) {
  const active = employees.filter((employee) => !employee.excluded);
  const totals = DIMENSION_KEYS.reduce(
    (acc, key) => {
      acc[key] = active.reduce(
        (sum, employee) => sum + dimensionValue(employee, key),
        0,
      );
      return acc;
    },
    {} as Record<EraDimensionKey, number>,
  );

  const spofComponents = new Map<string, string>();
  const identityGaps: EraEmployeeMetrics[] = [];
  for (const employee of active) {
    if ((employee.data_completeness_pct ?? 100) < 80) {
      identityGaps.push(employee);
    }
    for (const component of employee.affected_components ?? []) {
      if (component.spof) {
        spofComponents.set(component.id, component.name);
      }
    }
  }

  const hideDonut = active.length <= 1;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
      <h2 className="text-sm font-medium text-zinc-200">Team composition</h2>
      <p className="mt-1 text-xs text-zinc-500">
        Top driver: {ERA_DIMENSION_COLORS[topRiskDriver].label}
      </p>

      {!hideDonut && (
        <div className="mt-3">
          <EraDimensionDonut totals={totals} />
        </div>
      )}

      <div className="mt-4 rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Avg risk trend (30d)
          </p>
          <EraRiskSparkline history={teamHistory} width={120} height={32} />
        </div>
      </div>

      <div className="mt-4">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
          Affected systems
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          {Array.from(spofComponents.entries()).map(([id, name]) => (
            <Link
              key={id}
              href="/kra?filter=spof"
              className="rounded-full border border-fuchsia-500/30 bg-fuchsia-500/10 px-2.5 py-1 text-xs text-fuchsia-300 hover:bg-fuchsia-500/20"
            >
              ● {name} (SPOF)
            </Link>
          ))}
          {spofComponents.size === 0 && (
            <span className="text-xs text-zinc-500">No SPOF components flagged</span>
          )}
        </div>
        <Link
          href="/kra"
          className="mt-2 inline-block text-xs text-violet-300 hover:text-violet-200"
        >
          → Open KRA
        </Link>
      </div>

      {identityGaps.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Identity gaps
          </p>
          <ul className="mt-2 space-y-1 text-xs text-amber-300">
            {identityGaps.slice(0, 4).map((employee) => (
              <li key={employee.employee_id}>
                {employee.name} — {employee.data_completeness_pct ?? 0}% complete
              </li>
            ))}
          </ul>
          <Link
            href="/settings/identity-mapping"
            className="mt-2 inline-block text-xs text-violet-300 hover:text-violet-200"
          >
            Fix mappings →
          </Link>
        </div>
      )}
    </div>
  );
}

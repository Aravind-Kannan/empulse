"use client";

import type { EraAffectedComponent, EraEmployeeMetrics } from "@/lib/types";

interface EraAffectedComponentsGraphProps {
  employee: EraEmployeeMetrics;
}

function layoutComponents(
  components: EraAffectedComponent[],
  centerX: number,
  centerY: number,
  radius: number,
) {
  const subset = components.slice(0, 8);
  return subset.map((component, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(subset.length, 1) - Math.PI / 2;
    return {
      ...component,
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius,
    };
  });
}

export function EraAffectedComponentsGraph({
  employee,
}: EraAffectedComponentsGraphProps) {
  const components = employee.affected_components ?? [];
  const width = 360;
  const height = 260;
  const centerX = width / 2;
  const centerY = height / 2;
  const positioned = layoutComponents(components, centerX, centerY, 90);

  if (components.length === 0) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
        <h3 className="text-sm font-medium text-zinc-200">Affected components</h3>
        <p className="mt-2 text-sm text-zinc-500">
          No owned components linked to continuity risk yet.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
      <h3 className="mb-3 text-sm font-medium text-zinc-200">Affected components</h3>
      <div className="overflow-hidden rounded-lg bg-zinc-950/50">
        <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full">
          {positioned.map((component) => (
            <line
              key={`line-${component.id}`}
              x1={centerX}
              y1={centerY}
              x2={component.x}
              y2={component.y}
              stroke="#3f3f46"
              strokeWidth="1.5"
            />
          ))}

          <circle cx={centerX} cy={centerY} r="28" fill="#27272a" stroke="#a78bfa" />
          <text
            x={centerX}
            y={centerY + 4}
            textAnchor="middle"
            className="fill-zinc-100 text-[10px] font-medium"
          >
            {employee.name.split(" ")[0]}
          </text>

          {positioned.map((component) => (
            <g key={component.id}>
              <a
                href={`/kra?highlight=${encodeURIComponent(component.id)}`}
                className="cursor-pointer"
              >
                <circle
                  cx={component.x}
                  cy={component.y}
                  r="22"
                  fill="#18181b"
                  stroke={component.spof ? "#f97316" : "#52525b"}
                  strokeWidth={component.spof ? 3 : 1.5}
                  className="transition hover:fill-zinc-900"
                />
                <text
                  x={component.x}
                  y={component.y + 3}
                  textAnchor="middle"
                  className="fill-zinc-200 text-[9px] font-medium pointer-events-none"
                >
                  {component.name.length > 10
                    ? `${component.name.slice(0, 9)}…`
                    : component.name}
                </text>
              </a>
            </g>
          ))}
        </svg>
      </div>
      <p className="mt-2 text-xs text-zinc-500">
        Click a component to open KRA. Orange ring = SPOF.
      </p>
    </section>
  );
}

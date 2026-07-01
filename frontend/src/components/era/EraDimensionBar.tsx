import type { EraDimensionKey } from "@/lib/types";

import { ERA_DIMENSION_COLORS } from "./era-colors";

interface EraDimensionBarProps {
  dimension: EraDimensionKey;
  value: number;
  partial?: boolean;
  className?: string;
}

export function EraDimensionBar({
  dimension,
  value,
  partial = false,
  className = "",
}: EraDimensionBarProps) {
  const width = Math.max(0, Math.min(100, value));
  return (
    <div
      className={`h-2 w-full min-w-[2.5rem] rounded-full bg-zinc-800 ${className}`}
      title={`${ERA_DIMENSION_COLORS[dimension].label}: ${Math.round(value)}%${partial ? " (partial data)" : ""}`}
    >
      <div
        className={`h-full rounded-full ${ERA_DIMENSION_COLORS[dimension].bar} ${
          partial ? "border border-dashed border-zinc-500" : ""
        }`}
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

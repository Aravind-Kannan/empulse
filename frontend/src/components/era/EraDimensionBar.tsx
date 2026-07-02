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
  showValue = false,
}: EraDimensionBarProps & { showValue?: boolean }) {
  const width = Math.max(0, Math.min(100, value));
  const rounded = Math.round(value);
  return (
    <div
      className={`flex min-w-[2.5rem] flex-col gap-0.5 ${className}`}
      title={`${ERA_DIMENSION_COLORS[dimension].label}: ${rounded}%${partial ? " (partial data)" : ""}`}
    >
      <div className="h-2 w-full rounded-full bg-zinc-800">
        <div
          className={`h-full rounded-full ${ERA_DIMENSION_COLORS[dimension].bar} ${
            partial ? "border border-dashed border-zinc-500" : ""
          }`}
          style={{ width: `${Math.max(width, value > 0 ? 4 : 0)}%` }}
        />
      </div>
      {showValue && (
        <span className="text-center text-[10px] tabular-nums text-zinc-500">
          {rounded}%
        </span>
      )}
    </div>
  );
}

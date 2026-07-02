import type { EraDimensionKey } from "@/lib/types";

export const ERA_DIMENSION_COLORS: Record<
  EraDimensionKey,
  { bar: string; text: string; label: string; stroke: string }
> = {
  knowledge: {
    bar: "bg-violet-400",
    text: "text-violet-300",
    label: "Knowledge",
    stroke: "#a78bfa",
  },
  operational: {
    bar: "bg-orange-400",
    text: "text-orange-300",
    label: "Operational",
    stroke: "#fb923c",
  },
  documentation: {
    bar: "bg-sky-400",
    text: "text-sky-300",
    label: "Documentation",
    stroke: "#38bdf8",
  },
  structural: {
    bar: "bg-fuchsia-400",
    text: "text-fuchsia-300",
    label: "Structural",
    stroke: "#e879f9",
  },
  burnout: {
    bar: "bg-rose-400",
    text: "text-rose-300",
    label: "Burnout",
    stroke: "#fb7185",
  },
};

export const DIMENSION_KEYS: EraDimensionKey[] = [
  "knowledge",
  "operational",
  "documentation",
  "structural",
  "burnout",
];

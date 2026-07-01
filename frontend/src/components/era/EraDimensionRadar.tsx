"use client";

import type { EraDimensions } from "@/lib/types";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";

interface EraDimensionRadarProps {
  dimensions: EraDimensions;
  size?: number;
}

export function EraDimensionRadar({ dimensions, size = 180 }: EraDimensionRadarProps) {
  const center = size / 2;
  const radius = size * 0.34;
  const points = DIMENSION_KEYS.map((key, index) => {
    const angle = (Math.PI * 2 * index) / DIMENSION_KEYS.length - Math.PI / 2;
    const value = Math.max(0, Math.min(100, dimensions[key])) / 100;
    const x = center + Math.cos(angle) * radius * value;
    const y = center + Math.sin(angle) * radius * value;
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg width={size} height={size} className="mx-auto">
      {[0.25, 0.5, 0.75, 1].map((scale) => (
        <polygon
          key={scale}
          points={DIMENSION_KEYS.map((_, index) => {
            const angle =
              (Math.PI * 2 * index) / DIMENSION_KEYS.length - Math.PI / 2;
            const x = center + Math.cos(angle) * radius * scale;
            const y = center + Math.sin(angle) * radius * scale;
            return `${x},${y}`;
          }).join(" ")}
          fill="none"
          stroke="#3f3f46"
          strokeWidth="1"
        />
      ))}
      <polygon points={points} fill="rgba(167,139,250,0.2)" stroke="#a78bfa" />
      {DIMENSION_KEYS.map((key, index) => {
        const angle = (Math.PI * 2 * index) / DIMENSION_KEYS.length - Math.PI / 2;
        const x = center + Math.cos(angle) * (radius + 14);
        const y = center + Math.sin(angle) * (radius + 14);
        return (
          <text
            key={key}
            x={x}
            y={y}
            textAnchor="middle"
            className={`fill-current text-[10px] ${ERA_DIMENSION_COLORS[key].text}`}
          >
            {ERA_DIMENSION_COLORS[key].label[0]}
          </text>
        );
      })}
    </svg>
  );
}

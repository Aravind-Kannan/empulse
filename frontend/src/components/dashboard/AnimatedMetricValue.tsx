"use client";

import { useEffect, useState } from "react";

import { useReducedMotion } from "@/hooks/useReducedMotion";

interface AnimatedMetricValueProps {
  value: number;
  decimals?: number;
  suffix?: string;
  className?: string;
  duration?: number;
}

export function AnimatedMetricValue({
  value,
  decimals = 0,
  suffix = "",
  className = "",
  duration = 1200,
}: AnimatedMetricValueProps) {
  const reducedMotion = useReducedMotion();
  const [display, setDisplay] = useState(reducedMotion ? value : 0);

  useEffect(() => {
    if (reducedMotion) {
      setDisplay(value);
      return;
    }

    let start: number | null = null;
    let frame = 0;

    const step = (timestamp: number) => {
      if (start === null) start = timestamp;
      const progress = Math.min((timestamp - start) / duration, 1);
      const eased = 1 - (1 - progress) ** 3;
      setDisplay(value * eased);
      if (progress < 1) frame = requestAnimationFrame(step);
    };

    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [value, duration, reducedMotion]);

  const formatted =
    decimals > 0 ? display.toFixed(decimals) : Math.round(display).toString();

  return (
    <span className={className}>
      {formatted}
      {suffix}
    </span>
  );
}

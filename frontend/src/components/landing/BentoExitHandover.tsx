"use client";

import { useEffect, useState } from "react";

const HANDOVER_LINES = [
  { text: "# Exit Handover — Diego Alvarez", heading: true },
  { text: "## Owned Components", heading: true },
  { text: "- Payment Gateway (primary, 68% graph share)", heading: false },
  { text: "- Checkout API (backup reviewer)", heading: false },
  { text: "## Open Incidents", heading: true },
  { text: "- PROJ-992: timeout spike — investigating", heading: false },
  { text: "## Recommended Successor", heading: true },
  { text: "- Cara Patel (KRA score: 82, adjacent ownership)", heading: false },
];

export function BentoExitHandover() {
  const [visibleCount, setVisibleCount] = useState(0);
  const [highlightIndex, setHighlightIndex] = useState(-1);

  // Type lines in once on mount — never remove them (prevents layout jump)
  useEffect(() => {
    if (visibleCount >= HANDOVER_LINES.length) return;
    const timer = window.setTimeout(
      () => setVisibleCount((c) => c + 1),
      700,
    );
    return () => window.clearTimeout(timer);
  }, [visibleCount]);

  // After full doc is shown, cycle a soft highlight — no resize
  useEffect(() => {
    if (visibleCount < HANDOVER_LINES.length) return;
    const timer = window.setInterval(() => {
      setHighlightIndex((prev) => (prev + 1) % HANDOVER_LINES.length);
    }, 1800);
    return () => window.clearInterval(timer);
  }, [visibleCount]);

  return (
    <div className="h-[148px] overflow-hidden rounded-lg border border-zinc-800 bg-black/60 p-3 font-mono text-[10px] leading-relaxed">
      {HANDOVER_LINES.map((line, index) => {
        const isVisible = index < visibleCount;
        const isHighlighted =
          visibleCount >= HANDOVER_LINES.length && index === highlightIndex;

        return (
          <p
            key={line.text}
            className={`min-h-[14px] transition-colors duration-500 ${
              line.heading ? "text-zinc-300" : "text-zinc-500"
            } ${isVisible ? "opacity-100" : "opacity-0"} ${
              isHighlighted ? "!text-sky-300" : ""
            }`}
          >
            {isVisible ? line.text : "\u00A0"}
            {isVisible &&
              index === visibleCount - 1 &&
              visibleCount < HANDOVER_LINES.length && (
                <span className="ml-0.5 inline-block h-3 w-1 animate-pulse bg-zinc-400" />
              )}
          </p>
        );
      })}
    </div>
  );
}

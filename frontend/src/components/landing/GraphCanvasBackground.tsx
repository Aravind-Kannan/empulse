"use client";

import { useRef } from "react";

import { useGraphCanvasMesh } from "@/hooks/useGraphCanvasMesh";
import { useReducedMotion } from "@/hooks/useReducedMotion";

export function GraphCanvasBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const reducedMotion = useReducedMotion();
  useGraphCanvasMesh(canvasRef, reducedMotion);

  if (reducedMotion) {
    return (
      <div
        className="pointer-events-none fixed inset-0 z-0"
        aria-hidden
        style={{
          background:
            "radial-gradient(ellipse 55% 45% at 50% 20%, rgba(99,102,241,0.14), transparent 70%)",
        }}
      />
    );
  }

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 z-0 opacity-[0.88]"
      aria-hidden
    />
  );
}

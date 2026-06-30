"use client";

import { useCallback, useRef } from "react";

export function useMouseSpotlight<T extends HTMLElement>() {
  const ref = useRef<T>(null);

  const onMouseMove = useCallback((event: React.MouseEvent<T>) => {
    const element = ref.current;
    if (!element) return;
    const rect = element.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    element.style.setProperty("--spotlight-x", `${x}px`);
    element.style.setProperty("--spotlight-y", `${y}px`);
  }, []);

  return { ref, onMouseMove };
}

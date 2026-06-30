"use client";

import { motion, useInView, useScroll, useTransform } from "framer-motion";
import { useRef, type ReactNode } from "react";

import { useReducedMotion } from "@/hooks/useReducedMotion";

export const REVEAL_EASE = [0.16, 1, 0.3, 1] as const;

export const revealHidden = {
  opacity: 0,
  y: 40,
  scale: 0.98,
} as const;

export const revealVisible = {
  opacity: 1,
  y: 0,
  scale: 1,
} as const;

export function revealTransition(delay = 0) {
  return {
    duration: 0.8,
    ease: REVEAL_EASE,
    delay,
  };
}

interface ScrollRevealProps {
  children: ReactNode;
  className?: string;
  delay?: number;
  amount?: number;
}

export function ScrollReveal({
  children,
  className = "",
  delay = 0,
  amount = 0.2,
}: ScrollRevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount });
  const reducedMotion = useReducedMotion();

  if (reducedMotion) {
    return (
      <div ref={ref} className={className}>
        {children}
      </div>
    );
  }

  return (
    <motion.div
      ref={ref}
      className={className}
      initial={revealHidden}
      animate={inView ? revealVisible : revealHidden}
      transition={revealTransition(delay)}
    >
      {children}
    </motion.div>
  );
}

interface ParallaxLayerProps {
  children: ReactNode;
  className?: string;
}

/** Scroll-linked parallax — background moves slower than foreground copy */
export function ParallaxLayer({ children, className = "" }: ParallaxLayerProps) {
  const ref = useRef<HTMLDivElement>(null);
  const reducedMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const y = useTransform(scrollYProgress, [0, 1], ["8%", "-8%"]);

  if (reducedMotion) {
    return (
      <div ref={ref} className={className}>
        {children}
      </div>
    );
  }

  return (
    <div ref={ref} className={`relative overflow-hidden ${className}`}>
      <motion.div style={{ y }} className="h-full w-full">
        {children}
      </motion.div>
    </div>
  );
}

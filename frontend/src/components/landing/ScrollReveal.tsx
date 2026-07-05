"use client";

import { motion, useInView, useScroll, useTransform } from "framer-motion";
import { useRef, type ReactNode } from "react";

import { useReducedMotion } from "@/hooks/useReducedMotion";

export const REVEAL_EASE = [0.16, 1, 0.3, 1] as const;

export type RevealVariant = "up" | "down" | "left" | "right" | "scale" | "blur";

const VARIANT_HIDDEN: Record<RevealVariant, Record<string, number>> = {
  up: { opacity: 0, y: 48, scale: 0.98 },
  down: { opacity: 0, y: -32, scale: 0.98 },
  left: { opacity: 0, x: -56, scale: 0.98 },
  right: { opacity: 0, x: 56, scale: 0.98 },
  scale: { opacity: 0, scale: 0.88 },
  blur: { opacity: 0, y: 24, filter: "blur(12px)" },
};

const VARIANT_VISIBLE: Record<RevealVariant, Record<string, number | string>> = {
  up: { opacity: 1, y: 0, scale: 1 },
  down: { opacity: 1, y: 0, scale: 1 },
  left: { opacity: 1, x: 0, scale: 1 },
  right: { opacity: 1, x: 0, scale: 1 },
  scale: { opacity: 1, scale: 1 },
  blur: { opacity: 1, y: 0, filter: "blur(0px)" },
};

export const revealHidden = VARIANT_HIDDEN.up;
export const revealVisible = VARIANT_VISIBLE.up;

export function revealTransition(delay = 0, duration = 0.85) {
  return {
    duration,
    ease: REVEAL_EASE,
    delay,
  };
}

interface ScrollRevealProps {
  children: ReactNode;
  className?: string;
  delay?: number;
  amount?: number;
  variant?: RevealVariant;
  duration?: number;
}

export function ScrollReveal({
  children,
  className = "",
  delay = 0,
  amount = 0.2,
  variant = "up",
  duration = 0.85,
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
      initial={VARIANT_HIDDEN[variant]}
      animate={inView ? VARIANT_VISIBLE[variant] : VARIANT_HIDDEN[variant]}
      transition={revealTransition(delay, duration)}
    >
      {children}
    </motion.div>
  );
}

interface StaggerRevealProps {
  children: ReactNode;
  className?: string;
  stagger?: number;
  amount?: number;
}

/** Staggers direct children as they scroll into view */
export function StaggerReveal({
  children,
  className = "",
  stagger = 0.12,
  amount = 0.15,
}: StaggerRevealProps) {
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
      initial="hidden"
      animate={inView ? "visible" : "hidden"}
      variants={{
        hidden: {},
        visible: {
          transition: { staggerChildren: stagger, delayChildren: 0.05 },
        },
      }}
    >
      {children}
    </motion.div>
  );
}

export const staggerChild = {
  hidden: { opacity: 0, y: 36, scale: 0.96 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.75, ease: REVEAL_EASE },
  },
};

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

interface ScrollScaleProps {
  children: ReactNode;
  className?: string;
}

/** Section that subtly scales and fades based on scroll position */
export function ScrollScale({ children, className = "" }: ScrollScaleProps) {
  const ref = useRef<HTMLDivElement>(null);
  const reducedMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const scale = useTransform(scrollYProgress, [0, 0.35, 0.65, 1], [0.94, 1, 1, 0.96]);
  const opacity = useTransform(scrollYProgress, [0, 0.2, 0.8, 1], [0.5, 1, 1, 0.6]);

  if (reducedMotion) {
    return (
      <div ref={ref} className={className}>
        {children}
      </div>
    );
  }

  return (
    <motion.div ref={ref} className={className} style={{ scale, opacity }}>
      {children}
    </motion.div>
  );
}

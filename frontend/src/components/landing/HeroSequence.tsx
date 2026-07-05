"use client";

import Link from "next/link";
import { motion, MotionConfig } from "framer-motion";

import { GlassCtaButton } from "@/components/landing/GlassCtaButton";
import { REVEAL_EASE } from "@/components/landing/ScrollReveal";

const item = {
  hidden: { opacity: 0, y: 40, filter: "blur(8px)" },
  show: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.9, ease: REVEAL_EASE },
  },
};

const headline = {
  hidden: { opacity: 0, y: 56, scale: 0.96 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 1, ease: REVEAL_EASE },
  },
};

interface HeroSequenceProps {
  onMouseMove: (event: React.MouseEvent<HTMLElement>) => void;
  heroRef: React.Ref<HTMLElement>;
}

function HeroCtas() {
  return (
    <div className="mt-10 flex flex-col items-center justify-center gap-3">
      <GlassCtaButton href="/signup">Get started</GlassCtaButton>
      <p className="text-sm text-zinc-500">
        Already have a workspace?{" "}
        <Link
          href="/login"
          className="text-zinc-300 underline-offset-4 transition hover:text-zinc-100 hover:underline"
        >
          Sign in
        </Link>
      </p>
    </div>
  );
}

export function HeroSequence({ onMouseMove, heroRef }: HeroSequenceProps) {
  return (
    <motion.section
      ref={heroRef}
      onMouseMove={onMouseMove}
      className="landing-hero-spotlight relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 pt-24"
      initial="hidden"
      animate="show"
      variants={{
        hidden: {},
        show: {
          transition: { staggerChildren: 0.2, delayChildren: 0.1 },
        },
      }}
    >
      <motion.div
        className="landing-hero-vignette pointer-events-none absolute inset-0"
        variants={{
          hidden: { opacity: 0 },
          show: { opacity: 1, transition: { duration: 1, ease: REVEAL_EASE } },
        }}
      />

      <div className="relative z-10 mx-auto max-w-4xl text-center">
        <motion.h1
          variants={headline}
          className="text-5xl font-semibold tracking-tight sm:text-6xl md:text-7xl"
        >
          Engineering Intelligence.
        </motion.h1>

        <motion.p
          variants={headline}
          className="landing-metallic-text mt-2 text-5xl font-semibold tracking-tight sm:text-6xl md:text-7xl"
        >
          Deciphered.
        </motion.p>

        <motion.p
          variants={item}
          className="mx-auto mt-8 max-w-xl text-lg leading-relaxed text-zinc-400"
        >
          Turn cross-tool data chaos into a unified graph of truth. 
          <span className="block text-zinc-500">
          Smarter engineering decisions for Managers, seamless offboarding for HR.
          </span>
        </motion.p>

        <motion.div variants={item}>
          <HeroCtas />
        </motion.div>
      </div>

      <motion.p
        variants={item}
        className="landing-scroll-hint absolute bottom-10 left-1/2 z-10 -translate-x-1/2 text-xs text-zinc-600"
      >
        Scroll to explore
      </motion.p>
    </motion.section>
  );
}

interface HeroShellProps extends HeroSequenceProps {
  reducedMotion: boolean;
}

function HeroStatic({ onMouseMove, heroRef }: HeroSequenceProps) {
  return (
    <section
      ref={heroRef}
      onMouseMove={onMouseMove}
      className="landing-hero-spotlight relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 pt-24"
    >
      <div className="landing-hero-vignette pointer-events-none absolute inset-0" />
      <div className="relative z-10 mx-auto max-w-4xl text-center">
        <h1 className="text-5xl font-semibold tracking-tight sm:text-6xl md:text-7xl">
          Engineering Intelligence.
        </h1>
        <p className="landing-metallic-text mt-2 text-5xl font-semibold tracking-tight sm:text-6xl md:text-7xl">
          Deciphered.
        </p>
        <p className="mx-auto mt-8 max-w-xl text-lg leading-relaxed text-zinc-400">
          See the risk. Keep the knowledge.
          <span className="block text-zinc-500">
            One live graph — built for managers and HR.
          </span>
        </p>
        <HeroCtas />
      </div>
    </section>
  );
}

export function HeroShell({
  onMouseMove,
  heroRef,
  reducedMotion,
}: HeroShellProps) {
  if (reducedMotion) {
    return <HeroStatic onMouseMove={onMouseMove} heroRef={heroRef} />;
  }

  return <HeroSequence onMouseMove={onMouseMove} heroRef={heroRef} />;
}

export function LandingMotionConfig({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

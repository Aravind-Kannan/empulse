"use client";

import Link from "next/link";
import { motion, MotionConfig } from "framer-motion";
import { Sparkles } from "lucide-react";

import { GlassCtaButton } from "@/components/landing/GlassCtaButton";
import { REVEAL_EASE } from "@/components/landing/ScrollReveal";

const item = {
  hidden: { opacity: 0, y: 32, scale: 0.98 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.8, ease: REVEAL_EASE },
  },
};

interface HeroSequenceProps {
  onMouseMove: (event: React.MouseEvent<HTMLElement>) => void;
  heroRef: React.Ref<HTMLElement>;
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
        <motion.div
          variants={item}
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs text-zinc-400 backdrop-blur-sm"
        >
          <Sparkles className="h-3.5 w-3.5 text-sky-400" />
          Cognee knowledge graph native
        </motion.div>

        <motion.h1
          variants={item}
          className="text-5xl font-semibold tracking-tight sm:text-6xl md:text-7xl"
        >
          Engineering Intelligence.
        </motion.h1>

        <motion.p
          variants={item}
          className="landing-metallic-text mt-2 text-5xl font-semibold tracking-tight sm:text-6xl md:text-7xl"
        >
          Deciphered.
        </motion.p>

        <motion.p
          variants={item}
          className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-zinc-400"
        >
          Unify org knowledge, incident response, risk analytics, and
          offboarding into one manager cockpit — built on a live engineering
          graph that thinks in relationships, not rows.
        </motion.p>

        <motion.div
          variants={item}
          className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row"
        >
          <GlassCtaButton href="/signup">Get Started</GlassCtaButton>
          <Link
            href="/login"
            className="group inline-flex items-center gap-1 text-sm text-zinc-400 transition hover:text-zinc-100"
          >
            Request a Demo
            <span className="transition-transform group-hover:translate-x-1">
              →
            </span>
          </Link>
        </motion.div>
      </div>

      <motion.p
        variants={item}
        className="landing-scroll-hint absolute bottom-10 left-1/2 -translate-x-1/2 text-xs text-zinc-600"
      >
        Scroll to explore
      </motion.p>
    </motion.section>
  );
}

interface HeroShellProps extends HeroSequenceProps {
  reducedMotion: boolean;
}

export function HeroShell({
  onMouseMove,
  heroRef,
  reducedMotion,
}: HeroShellProps) {
  if (reducedMotion) {
    return (
      <section
        ref={heroRef}
        onMouseMove={onMouseMove}
        className="landing-hero-spotlight relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 pt-24"
      >
        <div className="landing-hero-vignette pointer-events-none absolute inset-0" />
        <div className="relative z-10 mx-auto max-w-4xl text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs text-zinc-400 backdrop-blur-sm">
            <Sparkles className="h-3.5 w-3.5 text-sky-400" />
            Cognee knowledge graph native
          </div>
          <h1 className="text-5xl font-semibold tracking-tight sm:text-6xl md:text-7xl">
            Engineering Intelligence.
            <br />
            <span className="landing-metallic-text">Deciphered.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-zinc-400">
            Unify org knowledge, incident response, risk analytics, and
            offboarding into one manager cockpit — built on a live engineering
            graph that thinks in relationships, not rows.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <GlassCtaButton href="/signup">Get Started</GlassCtaButton>
            <Link
              href="/login"
              className="text-sm text-zinc-400 transition hover:text-zinc-100"
            >
              Request a Demo →
            </Link>
          </div>
        </div>
      </section>
    );
  }

  return <HeroSequence onMouseMove={onMouseMove} heroRef={heroRef} />;
}

export function LandingMotionConfig({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

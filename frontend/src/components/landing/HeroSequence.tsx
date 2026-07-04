"use client";

import Link from "next/link";
import { motion, MotionConfig } from "framer-motion";
import { BrainCircuit } from "lucide-react";

import { GlassCtaButton } from "@/components/landing/GlassCtaButton";
import { LandingHeroBackdrop } from "@/components/landing/LandingHeroBackdrop";
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
      className="landing-hero-spotlight relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-slate-950 px-6 pt-24"
      initial="hidden"
      animate="show"
      variants={{
        hidden: {},
        show: {
          transition: { staggerChildren: 0.2, delayChildren: 0.1 },
        },
      }}
    >
      <LandingHeroBackdrop />

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
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-zinc-800/80 bg-slate-900/40 px-4 py-1.5 text-xs text-zinc-400 backdrop-blur-md"
        >
          <BrainCircuit className="h-3.5 w-3.5 text-violet-400" />
          Cognee dual-DB · PostgreSQL + knowledge graph
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
          Engineering Intelligence Powered by Cognee: Unifying organization
          knowledge graphs, live triage, and automated offboarding into a single
          cockpit.
        </motion.p>

        <motion.p
          variants={item}
          className="mx-auto mt-3 max-w-xl text-sm text-zinc-500"
        >
          Cross-system multi-hop traversal across Slack threads, Jira tickets,
          and Notion documents — scoped per tenant with live GitHub ingestion.
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
      className="landing-hero-spotlight relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-slate-950 px-6 pt-24"
    >
      <LandingHeroBackdrop />
      <div className="landing-hero-vignette pointer-events-none absolute inset-0" />
      <div className="relative z-10 mx-auto max-w-4xl text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-zinc-800/80 bg-slate-900/40 px-4 py-1.5 text-xs text-zinc-400 backdrop-blur-md">
          <BrainCircuit className="h-3.5 w-3.5 text-violet-400" />
          Cognee dual-DB · PostgreSQL + knowledge graph
        </div>
        <h1 className="text-5xl font-semibold tracking-tight sm:text-6xl md:text-7xl">
          Engineering Intelligence.
        </h1>
        <p className="landing-metallic-text mt-2 text-5xl font-semibold tracking-tight sm:text-6xl md:text-7xl">
          Deciphered.
        </p>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-zinc-400">
          Engineering Intelligence Powered by Cognee: Unifying organization
          knowledge graphs, live triage, and automated offboarding into a single
          cockpit.
        </p>
        <p className="mx-auto mt-3 max-w-xl text-sm text-zinc-500">
          Cross-system multi-hop traversal across Slack threads, Jira tickets,
          and Notion documents — scoped per tenant with live GitHub ingestion.
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

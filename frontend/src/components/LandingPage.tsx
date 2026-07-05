"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  BrainCircuit,
  Search,
  Shield,
  Users,
} from "lucide-react";

import { BentoEraMetrics } from "@/components/landing/BentoEraMetrics";
import { BentoExitHandover } from "@/components/landing/BentoExitHandover";
import { BentoInvestigationWorkspace } from "@/components/landing/BentoInvestigationWorkspace";
import { BentoKraAlerts } from "@/components/landing/BentoKraAlerts";
import { GlassCtaButton } from "@/components/landing/GlassCtaButton";
import { GraphCanvasBackground } from "@/components/landing/GraphCanvasBackground";
import {
  HeroShell,
  LandingMotionConfig,
} from "@/components/landing/HeroSequence";
import { IntegrationsHub } from "@/components/landing/IntegrationsHub";
import { MinimalLandingNav } from "@/components/landing/MinimalLandingNav";
import { PostgresWarmupBanner } from "@/components/landing/PostgresWarmupBanner";
import {
  ParallaxLayer,
  ScrollReveal,
  ScrollScale,
  StaggerReveal,
  staggerChild,
} from "@/components/landing/ScrollReveal";
import { useMouseSpotlight } from "@/components/landing/useMouseSpotlight";
import { useReducedMotion } from "@/hooks/useReducedMotion";

function BentoCard({
  title,
  description,
  eyebrow,
  children,
  className = "",
}: {
  title: string;
  description: string;
  eyebrow?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`group flex h-full min-h-[260px] flex-col overflow-hidden rounded-3xl border border-zinc-800/60 bg-black/20 p-1 ring-1 ring-white/[0.03] backdrop-blur-md transition-all duration-500 hover:border-zinc-700/70 hover:bg-black/30 ${className}`}
    >
      <div className="flex h-full flex-col rounded-[1.35rem] bg-gradient-to-br from-zinc-950/70 to-black/80 p-5">
        {eyebrow ? (
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">
            {eyebrow}
          </p>
        ) : null}
        <h3 className="text-base font-medium tracking-tight text-zinc-100">
          {title}
        </h3>
        <p className="mt-1.5 mb-4 text-xs leading-relaxed text-zinc-500">
          {description}
        </p>
        <div className="mt-auto min-h-0 flex-1">{children}</div>
      </div>
    </div>
  );
}

const FEATURES = [
  {
    key: "triage",
    eyebrow: "01 · Triage",
    className: "md:col-span-2",
    title: "Live Cognee Graph Triage",
    description:
      "3-panel incident workspace — chat, diagnostics, SME context. Multi-hop [Jira] → MENTIONS → [Service] in seconds.",
    parallax: true,
    content: <BentoInvestigationWorkspace />,
  },
  {
    key: "kra",
    eyebrow: "02 · Knowledge",
    className: "",
    title: "Knowledge Risk Assessment",
    description:
      "SPOF detection, sole-ownership flags, and GitHub hotspot heatmaps.",
    content: <BentoKraAlerts />,
  },
  {
    key: "era",
    eyebrow: "03 · People",
    className: "",
    title: "Employee Risk Assessment",
    description:
      "Bottleneck scoring, on-call burnout signals, and attrition risk from graph breadth.",
    content: <BentoEraMetrics />,
  },
  {
    key: "exit",
    eyebrow: "04 · Offboarding",
    className: "md:col-span-2",
    title: "Employee Knowledge Handover",
    description:
      "Auto handover packs — ownership transfer, open Jira tasks, incident context, and doc gaps in one markdown export.",
    content: <BentoExitHandover />,
  },
] as const;

export function LandingPage() {
  const { ref: heroRef, onMouseMove } = useMouseSpotlight<HTMLElement>();
  const reducedMotion = useReducedMotion();
  const [bannerVisible, setBannerVisible] = useState(false);
  const navTopOffset = bannerVisible ? 44 : 0;

  return (
    <LandingMotionConfig>
      <div className="relative min-h-screen bg-[#050506] text-zinc-100">
        <GraphCanvasBackground />

        <div className="relative z-10">
          <PostgresWarmupBanner onVisibleChange={setBannerVisible} />
          <MinimalLandingNav topOffset={navTopOffset} />

          <HeroShell
            heroRef={heroRef}
            onMouseMove={onMouseMove}
            reducedMotion={reducedMotion}
          />

          {/* Feature bento — 2×2 with featured rows */}
          <section id="features" className="relative px-6 py-28">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_50%_30%_at_50%_0%,rgba(255,255,255,0.03),transparent_70%)]" />
            <ScrollScale className="relative mx-auto max-w-6xl">
              <ScrollReveal className="mb-16 max-w-xl" variant="blur">
                <p className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-600">
                  Intelligence engines
                </p>
                <h2 className="mt-3 text-3xl font-semibold tracking-tight text-zinc-100 sm:text-4xl">
                  Four workspaces.
                  <br />
                  <span className="text-zinc-500">One live graph.</span>
                </h2>
              </ScrollReveal>

              <StaggerReveal
                className="grid grid-cols-1 gap-5 md:grid-cols-2"
                stagger={0.14}
              >
                {FEATURES.map((item) => (
                  <motion.div
                    key={item.key}
                    variants={staggerChild}
                    className={`h-full ${item.className}`}
                  >
                    <BentoCard
                      eyebrow={item.eyebrow}
                      title={item.title}
                      description={item.description}
                      className={
                        item.key === "triage" ? "min-h-[340px]" : undefined
                      }
                    >
                      {"parallax" in item && item.parallax ? (
                        <ParallaxLayer>{item.content}</ParallaxLayer>
                      ) : (
                        item.content
                      )}
                    </BentoCard>
                  </motion.div>
                ))}
              </StaggerReveal>
            </ScrollScale>
          </section>

          {/* Integrations hub */}
          <section
            id="integrations"
            className="relative overflow-hidden border-t border-zinc-800/40 px-6 py-28"
          >
            <div
              className="pointer-events-none absolute inset-0"
              aria-hidden
              style={{
                background:
                  "radial-gradient(ellipse 45% 35% at 75% 50%, rgba(99,102,241,0.07), transparent 70%)",
              }}
            />
            <div className="relative mx-auto max-w-6xl">
              <div className="grid items-center gap-14 lg:grid-cols-2">
                <ScrollReveal variant="left">
                  <p className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-600">
                    Integrations
                  </p>
                  <h2 className="mt-3 text-3xl font-semibold tracking-tight text-zinc-100 sm:text-4xl">
                    Your stack,
                    <br />
                    <span className="text-zinc-500">wired to one graph.</span>
                  </h2>
                  <p className="mt-4 max-w-md text-sm leading-relaxed text-zinc-500">
                    GitHub commits, Jira tickets, Slack threads, and Notion pages
                    become traversable nodes — synced per tenant with job
                    tracking and retry.
                  </p>
                  <ul className="mt-6 space-y-2">
                    {[
                      "MENTIONS · OWNED_BY · THREAD_IN edges",
                      "Identity mapping across all sources",
                      "On-demand sync with live status",
                    ].map((line, i) => (
                      <ScrollReveal
                        key={line}
                        variant="up"
                        delay={0.1 + i * 0.08}
                      >
                        <li className="flex items-center gap-2 text-xs text-zinc-500">
                          <span className="h-1 w-1 rounded-full bg-violet-400/70" />
                          {line}
                        </li>
                      </ScrollReveal>
                    ))}
                  </ul>
                </ScrollReveal>

                <ScrollReveal variant="right" delay={0.15}>
                  <IntegrationsHub />
                </ScrollReveal>
              </div>
            </div>
          </section>

          {/* Capabilities */}
          <section className="border-t border-zinc-800/40 px-6 py-28">
            <div className="mx-auto max-w-6xl">
              <ScrollReveal className="mb-14 max-w-xl" variant="blur">
                <p className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-600">
                  Built for engineering managers
                </p>
                <h2 className="mt-3 text-3xl font-semibold tracking-tight text-zinc-100">
                  Not another dashboard — a queryable engineering graph
                </h2>
              </ScrollReveal>

              <StaggerReveal
                className="grid gap-4 sm:grid-cols-2"
                stagger={0.1}
              >
                {[
                  {
                    icon: Shield,
                    title: "ERA continuity signals",
                    copy: "Attrition risk, on-call burnout, undocumented incident resolutions, and sole-responder thread detection from Slack telemetry.",
                  },
                  {
                    icon: Users,
                    title: "Identity-aware graph",
                    copy: "Map GitHub handles, Jira emails, Slack IDs, and Notion users to employee records so Cognee merges nodes accurately.",
                  },
                  {
                    icon: Search,
                    title: "Incident investigation",
                    copy: "Jira + Slack incident feed with confidence scoring, root-cause synthesis, and historical reference search across integrated sources.",
                  },
                  {
                    icon: BrainCircuit,
                    title: "Knowledge loss prevention",
                    copy: "EKH handover packs compile ownership, open tasks, incident-channel context, and doc gaps — deliverable via Slack DM.",
                  },
                ].map((cap) => (
                  <motion.div key={cap.title} variants={staggerChild}>
                    <div className="flex h-full gap-4 rounded-2xl border border-zinc-800/60 bg-black/20 p-5 backdrop-blur-md transition duration-300 hover:border-zinc-700/60 hover:bg-black/30">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-zinc-800/60 bg-zinc-950/60">
                        <cap.icon className="h-5 w-5 text-zinc-400" />
                      </div>
                      <div>
                        <h3 className="font-medium text-zinc-100">
                          {cap.title}
                        </h3>
                        <p className="mt-1 text-sm leading-relaxed text-zinc-500">
                          {cap.copy}
                        </p>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </StaggerReveal>
            </div>
          </section>

          {/* Footer CTA */}
          <ScrollReveal
            className="border-t border-zinc-800/40 px-6 py-24"
            variant="scale"
          >
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-2xl font-semibold tracking-tight text-zinc-100 sm:text-3xl">
                Ready to unify your engineering intelligence?
              </h2>
              <p className="mt-3 text-zinc-500">
                Create a tenant workspace, ingest your org chart, and connect
                your first integration — your Cognee graph builds from day one.
              </p>
              <div className="mt-8 flex flex-col items-center justify-center gap-3">
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
            </div>
          </ScrollReveal>
        </div>
      </div>
    </LandingMotionConfig>
  );
}

"use client";

import { useState } from "react";
import Link from "next/link";
import {
  BrainCircuit,
  Database,
  GitBranch,
  Network,
  Search,
  Shield,
  Users,
  Zap,
} from "lucide-react";

import { BentoEraMetrics } from "@/components/landing/BentoEraMetrics";
import { BentoExitHandover } from "@/components/landing/BentoExitHandover";
import { BentoIntegrations } from "@/components/landing/BentoIntegrations";
import { BentoInvestigationWorkspace } from "@/components/landing/BentoInvestigationWorkspace";
import { BentoKraAlerts } from "@/components/landing/BentoKraAlerts";
import { BentoOrgPreview } from "@/components/landing/BentoOrgPreview";
import { GlassCtaButton } from "@/components/landing/GlassCtaButton";
import {
  HeroShell,
  LandingMotionConfig,
} from "@/components/landing/HeroSequence";
import { LandingLiveTicker } from "@/components/landing/LandingLiveTicker";
import { LandingNav } from "@/components/landing/LandingNav";
import { PostgresWarmupBanner } from "@/components/landing/PostgresWarmupBanner";
import { ParallaxLayer, ScrollReveal } from "@/components/landing/ScrollReveal";
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
      className={`group h-full overflow-hidden rounded-3xl border border-zinc-800/80 bg-slate-900/40 p-1 ring-1 ring-white/5 backdrop-blur-md transition-all duration-300 hover:border-zinc-700/80 hover:bg-slate-900/55 ${className}`}
    >
      <div className="h-full rounded-[1.35rem] bg-gradient-to-br from-slate-900/80 to-slate-950/90 p-5">
        {eyebrow ? (
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-violet-400/90">
            {eyebrow}
          </p>
        ) : null}
        <h3 className="text-base font-medium text-zinc-100">{title}</h3>
        <p className="mt-1 mb-4 text-xs leading-relaxed text-zinc-500">
          {description}
        </p>
        {children}
      </div>
    </div>
  );
}

const STATS = [
  { value: "Dual-DB", label: "PostgreSQL + Cognee graph per tenant" },
  { value: "4-way", label: "Jira · Slack · GitHub · Notion ingestion" },
  { value: "Multi-hop", label: "Cross-system graph traversal at triage time" },
  { value: "< 5 min", label: "Org chart to live operational graph" },
];

const PILLARS = [
  {
    key: "triage",
    eyebrow: "Pillar 01",
    className: "lg:col-span-2",
    title: "Live Cognee Graph Triage",
    description:
      "Incident Investigation workspace with 3-panel layout: chat assistant, diagnostics, and SME context. Multi-hop hops like [Jira Task] → MENTIONS → [Service Component] resolve in seconds.",
    parallax: true,
    content: <BentoInvestigationWorkspace />,
  },
  {
    key: "kra",
    eyebrow: "Pillar 02",
    className: "lg:col-span-1",
    title: "Knowledge Risk Assessment (KRA)",
    description:
      "Automated Single Point of Failure detection, sole-ownership flags, and codebase vulnerability heatmaps across GitHub hotspots.",
    content: <BentoKraAlerts />,
  },
  {
    key: "era",
    eyebrow: "Pillar 03",
    className: "lg:col-span-1",
    title: "Employee Risk Assessment (ERA)",
    description:
      "Developer bottleneck scoring, operational burnout signals from Slack on-call telemetry, and attrition risk from graph contribution breadth.",
    content: <BentoEraMetrics />,
  },
] as const;

const PLATFORM_ITEMS = [
  {
    key: "exit",
    title: "Employee Knowledge Handover (EKH)",
    description:
      "Automated knowledge-loss offboarding generators — ownership transfer, open Jira tasks, incident-channel context, and documentation gaps in one markdown pack.",
    content: <BentoExitHandover />,
  },
  {
    key: "org",
    title: "Org Chart Workspace",
    description:
      "Drag-and-drop hierarchy, component ownership, and identity mapping — persisted to PostgreSQL and re-indexed into Cognee on save.",
    content: <BentoOrgPreview />,
  },
] as const;

const ARCHITECTURE = [
  {
    icon: Database,
    title: "PostgreSQL operational layer",
    copy: "Employees, components, assignments, integration configs, and identity mappings — tenant-scoped with strict isolation headers.",
  },
  {
    icon: BrainCircuit,
    title: "Cognee knowledge graph",
    copy: "Slack threads, Jira tickets, Notion pages, and GitHub artifacts become traversable nodes with MENTIONS, OWNED_BY, and THREAD_IN edges.",
  },
  {
    icon: Network,
    title: "Unified ingestion streams",
    copy: "Connect once, sync on demand. Each integration writes structured metadata into your tenant dataset without cross-org leakage.",
  },
];

const STEPS = [
  {
    icon: GitBranch,
    title: "Ingest your org",
    copy: "Upload CSV or build hierarchy on the canvas. Reporting lines, team tags, and component assignments land in PostgreSQL and Cognee.",
  },
  {
    icon: Zap,
    title: "Connect your stack",
    copy: "Sync GitHub repos, Jira projects, Slack incident channels, and Notion runbooks. Identity mapping links handles to employee records.",
  },
  {
    icon: Search,
    title: "Act on intelligence",
    copy: "Run ERA, KRA, incident investigation, and EKH handover — every workspace queries the same live graph scoped to your tenant.",
  },
];

export function LandingPage() {
  const { ref: heroRef, onMouseMove } = useMouseSpotlight<HTMLElement>();
  const reducedMotion = useReducedMotion();
  const [bannerVisible, setBannerVisible] = useState(false);
  const navTopOffset = bannerVisible ? 44 : 0;

  return (
    <LandingMotionConfig>
      <div className="min-h-screen bg-slate-950 text-zinc-100">
        <PostgresWarmupBanner onVisibleChange={setBannerVisible} />
        <LandingNav topOffset={navTopOffset} />

        <HeroShell
          heroRef={heroRef}
          onMouseMove={onMouseMove}
          reducedMotion={reducedMotion}
        />

        {/* Stats strip */}
        <section className="border-b border-zinc-800/80 bg-slate-900/30 px-6 py-10 backdrop-blur-sm">
          <div className="mx-auto mb-8">
            <LandingLiveTicker />
          </div>
          <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 md:grid-cols-4">
            {STATS.map((stat, index) => (
              <ScrollReveal key={stat.label} delay={index * 0.08}>
                <div className="text-center md:text-left">
                  <p className="text-2xl font-semibold tracking-tight text-zinc-100">
                    {stat.value}
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-zinc-500">
                    {stat.label}
                  </p>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </section>

        {/* Core pillars */}
        <section id="pillars" className="relative px-6 py-24">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_60%_40%_at_50%_0%,rgba(99,102,241,0.08),transparent_70%)]" />
          <div className="relative mx-auto max-w-6xl">
            <ScrollReveal className="mb-14 text-center">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-500">
                Core pillars
              </p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-zinc-100 sm:text-4xl">
                Three intelligence engines. One graph.
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-zinc-500">
                Purpose-built workspaces for triage, knowledge risk, and people
                risk — each powered by the same Cognee traversal layer.
              </p>
            </ScrollReveal>

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              {PILLARS.map((item, index) => (
                <ScrollReveal
                  key={item.key}
                  className={item.className}
                  delay={index * 0.12}
                >
                  <BentoCard
                    eyebrow={item.eyebrow}
                    title={item.title}
                    description={item.description}
                  >
                    {"parallax" in item && item.parallax ? (
                      <ParallaxLayer>{item.content}</ParallaxLayer>
                    ) : (
                      item.content
                    )}
                  </BentoCard>
                </ScrollReveal>
              ))}
            </div>
          </div>
        </section>

        {/* Platform grid */}
        <section id="platform" className="border-t border-zinc-800/80 px-6 py-24">
          <div className="mx-auto max-w-6xl">
            <ScrollReveal className="mb-14 text-center">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-500">
                Platform
              </p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-zinc-100 sm:text-4xl">
                Every workspace shares one operational graph
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-zinc-500">
                Offboarding generators, org management, and integration sync —
                scroll-revealed like an Apple product story.
              </p>
            </ScrollReveal>

            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              {PLATFORM_ITEMS.map((item, index) => (
                <ScrollReveal key={item.key} delay={index * 0.1}>
                  <BentoCard title={item.title} description={item.description}>
                    {item.content}
                  </BentoCard>
                </ScrollReveal>
              ))}
            </div>

            <ScrollReveal delay={0.15} className="mt-5">
              <BentoCard
                title="Integration Sync Hub"
                description="Connect GitHub, Jira, Slack, and Notion — each sync writes structured edges into your tenant Cognee dataset with job tracking and retry."
              >
                <BentoIntegrations />
              </BentoCard>
            </ScrollReveal>
          </div>
        </section>

        {/* Architecture */}
        <section
          id="architecture"
          className="border-t border-zinc-800/80 bg-slate-900/20 px-6 py-24 backdrop-blur-sm"
        >
          <div className="mx-auto max-w-6xl">
            <ScrollReveal className="mb-14 text-center">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-500">
                Architecture
              </p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-zinc-100">
                Cognee dual-DB, tenant-isolated by design
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-zinc-500">
                PostgreSQL holds operational truth. Cognee holds relationship
                intelligence. Neither crosses tenant boundaries.
              </p>
            </ScrollReveal>

            <div className="grid gap-6 md:grid-cols-3">
              {ARCHITECTURE.map((item, index) => (
                <ScrollReveal key={item.title} delay={index * 0.1}>
                  <div className="h-full rounded-2xl border border-zinc-800/80 bg-slate-900/40 p-6 backdrop-blur-md">
                    <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl border border-zinc-800/80 bg-slate-950/60">
                      <item.icon className="h-5 w-5 text-violet-400" />
                    </div>
                    <h3 className="text-lg font-medium text-zinc-100">
                      {item.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-zinc-500">
                      {item.copy}
                    </p>
                  </div>
                </ScrollReveal>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section className="border-t border-zinc-800/80 px-6 py-24">
          <div className="mx-auto max-w-6xl">
            <ScrollReveal className="mb-14 text-center">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-500">
                How it works
              </p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-zinc-100">
                From org chart to operational graph in three steps
              </h2>
            </ScrollReveal>

            <div className="grid gap-8 md:grid-cols-3">
              {STEPS.map((step, index) => (
                <ScrollReveal key={step.title} delay={index * 0.1}>
                  <div className="rounded-2xl border border-zinc-800/80 bg-slate-900/40 p-6 backdrop-blur-md">
                    <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl border border-zinc-800/80 bg-slate-950/60">
                      <step.icon className="h-5 w-5 text-sky-400" />
                    </div>
                    <p className="mb-1 text-xs font-medium text-zinc-500">
                      Step {index + 1}
                    </p>
                    <h3 className="text-lg font-medium text-zinc-100">
                      {step.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-zinc-500">
                      {step.copy}
                    </p>
                  </div>
                </ScrollReveal>
              ))}
            </div>
          </div>
        </section>

        {/* Capabilities */}
        <section className="border-t border-zinc-800/80 px-6 py-24">
          <div className="mx-auto max-w-6xl">
            <ScrollReveal className="mb-14 text-center">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-500">
                Built for engineering managers
              </p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-zinc-100">
                Not another dashboard — a queryable engineering graph
              </h2>
            </ScrollReveal>

            <div className="grid gap-5 sm:grid-cols-2">
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
              ].map((cap, index) => (
                <ScrollReveal key={cap.title} delay={index * 0.08}>
                  <div className="flex gap-4 rounded-2xl border border-zinc-800/80 bg-slate-900/40 p-5 backdrop-blur-md">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-zinc-800/80 bg-slate-950/60">
                      <cap.icon className="h-5 w-5 text-zinc-300" />
                    </div>
                    <div>
                      <h3 className="font-medium text-zinc-100">{cap.title}</h3>
                      <p className="mt-1 text-sm leading-relaxed text-zinc-500">
                        {cap.copy}
                      </p>
                    </div>
                  </div>
                </ScrollReveal>
              ))}
            </div>
          </div>
        </section>

        {/* Footer CTA */}
        <ScrollReveal className="border-t border-zinc-800/80 px-6 py-20">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-2xl font-semibold tracking-tight text-zinc-100 sm:text-3xl">
              Ready to unify your engineering intelligence?
            </h2>
            <p className="mt-3 text-zinc-500">
              Create a tenant workspace, ingest your org chart, and connect your
              first integration — your Cognee graph builds from day one.
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
    </LandingMotionConfig>
  );
}

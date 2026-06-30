"use client";

import Link from "next/link";
import {
  BrainCircuit,
  GitBranch,
  Layers,
  Network,
  Shield,
  Users,
  Zap,
} from "lucide-react";

import { BentoEraMetrics } from "@/components/landing/BentoEraMetrics";
import { BentoExitHandover } from "@/components/landing/BentoExitHandover";
import { BentoIncidentGraph } from "@/components/landing/BentoIncidentGraph";
import { BentoIntegrations } from "@/components/landing/BentoIntegrations";
import { BentoKraAlerts } from "@/components/landing/BentoKraAlerts";
import { BentoOrgPreview } from "@/components/landing/BentoOrgPreview";
import { GlassCtaButton } from "@/components/landing/GlassCtaButton";
import {
  HeroShell,
  LandingMotionConfig,
} from "@/components/landing/HeroSequence";
import { LandingNav } from "@/components/landing/LandingNav";
import { ParallaxLayer, ScrollReveal } from "@/components/landing/ScrollReveal";
import { useMouseSpotlight } from "@/components/landing/useMouseSpotlight";
import { useReducedMotion } from "@/hooks/useReducedMotion";

function BentoCard({
  title,
  description,
  children,
  className = "",
}: {
  title: string;
  description: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`h-full overflow-hidden rounded-3xl border border-white/10 bg-zinc-900/30 p-1 ring-1 ring-white/5 transition-colors hover:border-white/15 ${className}`}
    >
      <div className="h-full rounded-[1.35rem] bg-gradient-to-br from-zinc-900/80 to-black/80 p-5">
        <h3 className="text-base font-medium text-zinc-100">{title}</h3>
        <p className="mt-1 mb-4 text-xs text-zinc-500">{description}</p>
        {children}
      </div>
    </div>
  );
}

const STATS = [
  { value: "6", label: "Integrated workspaces" },
  { value: "Multi-hop", label: "Cognee graph traversal" },
  { value: "Tenant-safe", label: "Isolated org data" },
  { value: "< 5 min", label: "Org chart to live graph" },
];

const STEPS = [
  {
    icon: GitBranch,
    title: "Ingest your org",
    copy: "Upload CSV or build your hierarchy on the canvas. Every employee, team, and component lands in PostgreSQL and Cognee.",
  },
  {
    icon: Network,
    title: "Connect your stack",
    copy: "Sync GitHub, Jira, Slack, and Notion. Activity feeds enrich the graph with ownership, incidents, and identity edges.",
  },
  {
    icon: BrainCircuit,
    title: "Act on intelligence",
    copy: "Run ERA, KRA, incident investigation, and exit handover — all scoped to your tenant's live knowledge graph.",
  },
];

const CAPABILITIES = [
  {
    icon: Shield,
    title: "Employee Risk Assessment",
    copy: "Attrition signals and tenure-weighted risk scores derived from graph breadth and integration telemetry.",
  },
  {
    icon: Users,
    title: "Dynamic role evolution",
    copy: "Track title changes over time and sync reporting relationships back into Cognee automatically.",
  },
  {
    icon: Layers,
    title: "Multi-tenant isolation",
    copy: "Each workspace gets its own PostgreSQL scope and Cognee dataset namespace — no cross-org leaks.",
  },
  {
    icon: Zap,
    title: "Real-time graph sync",
    copy: "Bulk CSV, employee edits, and integration webhooks all re-index the operational graph in one pass.",
  },
];

const BENTO_ITEMS = [
  {
    key: "incident",
    className: "md:col-span-2 md:row-span-1",
    title: "Multi-hop Incident Investigation",
    description:
      "Trace root cause across services, owners, and Jira tickets with live graph traversal.",
    parallax: true,
    content: <BentoIncidentGraph />,
  },
  {
    key: "kra",
    className: "md:col-span-1 md:row-span-1",
    title: "Knowledge Risk Assessment",
    description:
      "SPOF detection — severity colors shift in place without resizing the card.",
    content: <BentoKraAlerts />,
  },
  {
    key: "era",
    className: "md:col-span-1",
    title: "Employee Risk Scores",
    description: "ERA attrition signals ranked by graph contribution and tenure.",
    content: <BentoEraMetrics />,
  },
  {
    key: "org",
    className: "md:col-span-1",
    title: "Org Chart Workspace",
    description:
      "Drag-and-drop hierarchy with team tags and Cognee re-index on save.",
    content: <BentoOrgPreview />,
  },
  {
    key: "exit",
    className: "md:col-span-1",
    title: "Exit Handover Pack",
    description:
      "Auto-assembled docs from graph context — lines type in once, then highlight cycles.",
    content: <BentoExitHandover />,
  },
] as const;

export function LandingPage() {
  const { ref: heroRef, onMouseMove } = useMouseSpotlight<HTMLElement>();
  const reducedMotion = useReducedMotion();

  return (
    <LandingMotionConfig>
      <div className="min-h-screen bg-[#09090b] text-zinc-100">
        <LandingNav />

        <HeroShell
          heroRef={heroRef}
          onMouseMove={onMouseMove}
          reducedMotion={reducedMotion}
        />

        {/* Stats strip */}
        <section className="border-y border-white/5 bg-black/30 px-6 py-10">
          <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 md:grid-cols-4">
            {STATS.map((stat, index) => (
              <ScrollReveal key={stat.label} delay={index * 0.08}>
                <div className="text-center md:text-left">
                  <p className="text-2xl font-semibold tracking-tight text-zinc-100">
                    {stat.value}
                  </p>
                  <p className="mt-1 text-xs text-zinc-500">{stat.label}</p>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </section>

        {/* Bento Grid — each card reveals independently on scroll */}
        <section id="platform" className="relative px-6 py-24">
          <div className="mx-auto max-w-6xl">
            <ScrollReveal className="mb-14 text-center">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-500">
                Platform
              </p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-zinc-100 sm:text-4xl">
                Every signal. One graph.
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-zinc-500">
                Six purpose-built workspaces share a single Cognee knowledge
                graph. Cards reveal one-by-one as you scroll — like an Apple
                product story.
              </p>
            </ScrollReveal>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3 md:grid-rows-[360px_220px] md:gap-5">
              {BENTO_ITEMS.map((item, index) => (
                <ScrollReveal
                  key={item.key}
                  className={item.className}
                  delay={index * 0.12}
                >
                  <BentoCard title={item.title} description={item.description}>
                    {"parallax" in item && item.parallax ? (
                      <ParallaxLayer>{item.content}</ParallaxLayer>
                    ) : (
                      item.content
                    )}
                  </BentoCard>
                </ScrollReveal>
              ))}
            </div>

            <ScrollReveal delay={0.15} className="mt-5">
              <BentoCard
                title="Integration Sync Hub"
                description="Connect GitHub, Jira, Slack, and Notion — each sync writes structured edges into your tenant's Cognee dataset."
              >
                <BentoIntegrations />
              </BentoCard>
            </ScrollReveal>
          </div>
        </section>

        {/* How it works */}
        <section id="how-it-works" className="border-t border-white/5 px-6 py-24">
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
                  <div className="rounded-2xl border border-white/10 bg-zinc-900/20 p-6">
                    <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-white/5 ring-1 ring-white/10">
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
        <section id="capabilities" className="border-t border-white/5 px-6 py-24">
          <div className="mx-auto max-w-6xl">
            <ScrollReveal className="mb-14 text-center">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-500">
                Capabilities
              </p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-zinc-100">
                Built for engineering managers, not dashboards
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-zinc-500">
                Empulse connects people, components, and incidents in a graph
                you can query, traverse, and act on — not a spreadsheet with
                extra steps.
              </p>
            </ScrollReveal>

            <div className="grid gap-5 sm:grid-cols-2">
              {CAPABILITIES.map((cap, index) => (
                <ScrollReveal key={cap.title} delay={index * 0.08}>
                  <div className="flex gap-4 rounded-2xl border border-white/10 bg-zinc-900/20 p-5">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-zinc-800">
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
        <ScrollReveal className="border-t border-white/5 px-6 py-20">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-2xl font-semibold tracking-tight text-zinc-100 sm:text-3xl">
              Ready to decipher your engineering org?
            </h2>
            <p className="mt-3 text-zinc-500">
              Create a workspace, ingest your org chart, and connect your first
              integration — your Cognee graph builds from day one.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <GlassCtaButton href="/signup">Get Started</GlassCtaButton>
              <Link
                href="/login"
                className="text-sm text-zinc-400 transition hover:text-zinc-100"
              >
                Login to your workspace →
              </Link>
            </div>
          </div>
        </ScrollReveal>
      </div>
    </LandingMotionConfig>
  );
}

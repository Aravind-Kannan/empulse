import type { IntegrationDefinition } from "@/lib/integrations";

interface IntegrationDetailFallbackProps {
  app?: IntegrationDefinition;
}

export function IntegrationDetailFallback({ app }: IntegrationDetailFallbackProps) {
  return (
    <div className="space-y-6">
      <div className="h-5 w-48 animate-pulse rounded bg-zinc-900" />
      <div className="h-36 animate-pulse rounded-2xl border border-zinc-800 bg-zinc-900/40" />
      <div className="h-12 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/40" />
      <div className="h-64 animate-pulse rounded-2xl border border-zinc-800 bg-zinc-900/40" />
      {app && (
        <span className="sr-only">Loading {app.name} integration…</span>
      )}
    </div>
  );
}

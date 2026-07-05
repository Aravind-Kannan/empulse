"use client";

const INTEGRATIONS = [
  { name: "GitHub", synced: true },
  { name: "Jira", synced: true },
  { name: "Slack", synced: false },
  { name: "Notion", synced: false },
];

export function BentoIntegrations() {
  return (
    <div className="grid grid-cols-2 gap-3">
      {INTEGRATIONS.map((item) => (
        <div
          key={item.name}
          className="flex flex-col justify-center rounded-xl border border-zinc-800/80 bg-zinc-950/50 px-4 py-5 transition hover:border-zinc-700/80"
        >
          <p className="text-sm font-medium text-zinc-200">{item.name}</p>
          <p
            className={`mt-1.5 text-xs ${
              item.synced ? "text-emerald-400/90" : "text-zinc-600"
            }`}
          >
            {item.synced ? "Synced to graph" : "Connect"}
          </p>
        </div>
      ))}
    </div>
  );
}

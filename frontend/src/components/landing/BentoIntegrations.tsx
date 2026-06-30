"use client";

const INTEGRATIONS = [
  { name: "GitHub", synced: true },
  { name: "Jira", synced: true },
  { name: "Slack", synced: false },
  { name: "Notion", synced: false },
];

export function BentoIntegrations() {
  return (
    <div className="grid h-[148px] grid-cols-2 gap-2">
      {INTEGRATIONS.map((item) => (
        <div
          key={item.name}
          className="flex flex-col justify-center rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2"
        >
          <p className="text-xs font-medium text-zinc-300">{item.name}</p>
          <p
            className={`mt-1 text-[10px] ${
              item.synced ? "text-emerald-400" : "text-zinc-600"
            }`}
          >
            {item.synced ? "Synced to graph" : "Connect"}
          </p>
        </div>
      ))}
    </div>
  );
}

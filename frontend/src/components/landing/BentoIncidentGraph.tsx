"use client";

const NODES = [
  { id: "inc", x: 48, y: 52, label: "INC-992" },
  { id: "gw", x: 148, y: 28, label: "Gateway" },
  { id: "auth", x: 148, y: 88, label: "Auth" },
  { id: "db", x: 248, y: 52, label: "Postgres" },
  { id: "sme", x: 328, y: 72, label: "SME" },
];

const EDGES = [
  ["inc", "gw"],
  ["inc", "auth"],
  ["gw", "db"],
  ["auth", "db"],
  ["db", "sme"],
];

export function BentoIncidentGraph() {
  const nodeMap = Object.fromEntries(NODES.map((n) => [n.id, n]));

  return (
    <div className="h-[260px] w-full overflow-hidden rounded-2xl bg-zinc-950/80 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">
          Incident Investigation
        </p>
        <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] text-sky-300">
          Multi-hop live
        </span>
      </div>
      <svg
        viewBox="0 0 380 120"
        className="h-[200px] w-full"
        aria-hidden="true"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient id="edge-glow" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.1" />
            <stop offset="50%" stopColor="#38bdf8" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#818cf8" stopOpacity="0.2" />
          </linearGradient>
        </defs>
        {EDGES.map(([from, to], index) => {
          const a = nodeMap[from];
          const b = nodeMap[to];
          return (
            <g key={`${from}-${to}`}>
              <line
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke="url(#edge-glow)"
                strokeWidth="1.5"
                className="landing-graph-edge"
                style={{ animationDelay: `${index * 0.4}s` }}
              />
              <circle r="2.5" fill="#7dd3fc">
                <animateMotion
                  dur={`${2.4 + index * 0.3}s`}
                  repeatCount="indefinite"
                  path={`M${a.x},${a.y} L${b.x},${b.y}`}
                />
              </circle>
            </g>
          );
        })}
        {NODES.map((node) => (
          <g key={node.id}>
            <circle
              cx={node.x}
              cy={node.y}
              r="14"
              fill="#18181b"
              stroke="#52525b"
              strokeWidth="1"
            />
            <text
              x={node.x}
              y={node.y + 28}
              textAnchor="middle"
              className="fill-zinc-500 text-[8px]"
            >
              {node.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

"use client";

const TEAMS = ["Platform", "Payments", "Identity"];

export function BentoOrgPreview() {
  return (
    <div className="flex h-[148px] flex-col justify-center gap-2 px-1">
      <div className="flex justify-center">
        <div className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-[10px] text-zinc-300">
          CTO · Elena Kowalski
        </div>
      </div>
      <div className="mx-auto h-4 w-px bg-zinc-700" />
      <div className="flex justify-center gap-2">
        {TEAMS.map((team) => (
          <div
            key={team}
            className="rounded-lg border border-zinc-800 bg-zinc-950/80 px-2 py-1 text-[10px] text-zinc-400"
          >
            {team}
          </div>
        ))}
      </div>
      <p className="mt-1 text-center text-[10px] text-zinc-600">
        Drag-and-drop · live Cognee sync
      </p>
    </div>
  );
}

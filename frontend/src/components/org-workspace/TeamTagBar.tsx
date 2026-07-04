"use client";

import { Tag } from "lucide-react";
import { useState } from "react";

interface TeamTagBarProps {
  selectedCount: number;
  onAssign: (teamName: string) => void;
  onClearSelection: () => void;
  compact?: boolean;
}

export function TeamTagBar({
  selectedCount,
  onAssign,
  onClearSelection,
  compact = false,
}: TeamTagBarProps) {
  const [teamName, setTeamName] = useState("");

  function handleAssign() {
    if (!teamName.trim() || selectedCount === 0) return;
    onAssign(teamName.trim());
    setTeamName("");
  }

  return (
    <div
      className={`flex flex-wrap items-center gap-2.5 border border-violet-500/25 bg-zinc-950/90 shadow-lg shadow-black/30 backdrop-blur-md ${
        compact
          ? "rounded-xl px-3 py-2"
          : "rounded-2xl border-zinc-800/70 bg-zinc-950/40 px-4 py-3 backdrop-blur-sm"
      }`}
    >
      <div className="flex items-center gap-2 text-sm">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-violet-500/25 bg-violet-500/10">
          <Tag className="h-3.5 w-3.5 text-violet-300" />
        </span>
        <span className="text-zinc-400">
          <span className="font-medium text-violet-200">{selectedCount}</span>{" "}
          selected
        </span>
      </div>
      <input
        value={teamName}
        onChange={(e) => setTeamName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") handleAssign();
        }}
        placeholder="Team tag, e.g. Platform Reliability"
        className={`min-w-[10rem] flex-1 rounded-lg border border-zinc-800 bg-zinc-900/80 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-violet-500/40 focus:ring-1 focus:ring-violet-500/20 ${
          compact ? "px-2.5 py-1.5" : "rounded-xl px-3 py-2"
        }`}
      />
      <button
        type="button"
        onClick={handleAssign}
        disabled={selectedCount === 0 || !teamName.trim()}
        className={`rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 font-medium text-white shadow-md shadow-violet-900/20 transition hover:from-violet-500 hover:to-indigo-500 disabled:cursor-not-allowed disabled:opacity-40 ${
          compact ? "px-3 py-1.5 text-xs" : "rounded-xl px-4 py-2 text-sm"
        }`}
      >
        Assign team
      </button>
      <button
        type="button"
        onClick={onClearSelection}
        className={`rounded-lg border border-zinc-800 text-zinc-500 transition hover:border-zinc-700 hover:text-zinc-300 ${
          compact ? "px-2.5 py-1.5 text-xs" : "rounded-xl px-3 py-2 text-sm"
        }`}
      >
        Clear
      </button>
    </div>
  );
}

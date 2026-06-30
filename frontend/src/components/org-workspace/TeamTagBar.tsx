"use client";

import { Tag } from "lucide-react";
import { useState } from "react";

interface TeamTagBarProps {
  selectedCount: number;
  onAssign: (teamName: string) => void;
  onClearSelection: () => void;
}

export function TeamTagBar({
  selectedCount,
  onAssign,
  onClearSelection,
}: TeamTagBarProps) {
  const [teamName, setTeamName] = useState("");

  function handleAssign() {
    if (!teamName.trim() || selectedCount === 0) return;
    onAssign(teamName.trim());
    setTeamName("");
  }

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/50 px-4 py-3">
      <div className="flex items-center gap-2 text-sm text-zinc-400">
        <Tag className="h-4 w-4" />
        <span>
          {selectedCount > 0
            ? `${selectedCount} selected`
            : "Select employees to assign a team tag"}
        </span>
      </div>
      <input
        value={teamName}
        onChange={(e) => setTeamName(e.target.value)}
        placeholder="Platform Reliability Squad"
        className="min-w-[14rem] flex-1 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
      />
      <button
        type="button"
        onClick={handleAssign}
        disabled={selectedCount === 0 || !teamName.trim()}
        className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        Assign team
      </button>
      {selectedCount > 0 && (
        <button
          type="button"
          onClick={onClearSelection}
          className="rounded-lg border border-zinc-700 px-3 py-2 text-sm text-zinc-400 hover:bg-zinc-900"
        >
          Clear
        </button>
      )}
    </div>
  );
}

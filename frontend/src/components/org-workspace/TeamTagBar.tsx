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
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-zinc-800/70 bg-zinc-950/40 px-4 py-3 backdrop-blur-sm">
      <div className="flex items-center gap-2 text-sm">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-violet-500/25 bg-violet-500/10">
          <Tag className="h-4 w-4 text-violet-300" />
        </span>
        <span className="text-zinc-400">
          {selectedCount > 0 ? (
            <>
              <span className="font-medium text-violet-200">{selectedCount}</span>{" "}
              selected
            </>
          ) : (
            "Select people to assign a team tag"
          )}
        </span>
      </div>
      <input
        value={teamName}
        onChange={(e) => setTeamName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") handleAssign();
        }}
        placeholder="e.g. Platform Reliability"
        className="min-w-[14rem] flex-1 rounded-xl border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-violet-500/40 focus:ring-1 focus:ring-violet-500/20"
      />
      <button
        type="button"
        onClick={handleAssign}
        disabled={selectedCount === 0 || !teamName.trim()}
        className="rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-md shadow-violet-900/20 transition hover:from-violet-500 hover:to-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Assign team
      </button>
      {selectedCount > 0 && (
        <button
          type="button"
          onClick={onClearSelection}
          className="rounded-xl border border-zinc-800 px-3 py-2 text-sm text-zinc-500 transition hover:border-zinc-700 hover:text-zinc-300"
        >
          Clear
        </button>
      )}
    </div>
  );
}

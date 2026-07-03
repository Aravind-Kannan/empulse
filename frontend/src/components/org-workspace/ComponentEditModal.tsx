"use client";

import { useEffect, useState } from "react";
import { Loader2, Trash2, X } from "lucide-react";

import type { Component } from "@/lib/types";

interface ComponentEditModalProps {
  component: Component;
  onClose: () => void;
  onSave: (
    componentId: string,
    payload: {
      name: string;
      tags: string;
      criticality: "tier1_revenue" | "tier2_core" | "tier3_support";
    },
  ) => void | Promise<void>;
  onDelete?: (componentId: string) => void | Promise<void>;
  isSaving?: boolean;
  isDeleting?: boolean;
}

const CRITICALITY_OPTIONS = [
  { value: "tier1_revenue", label: "Tier 1 — Revenue critical" },
  { value: "tier2_core", label: "Tier 2 — Core" },
  { value: "tier3_support", label: "Tier 3 — Support" },
] as const;

export function ComponentEditModal({
  component,
  onClose,
  onSave,
  onDelete,
  isSaving = false,
  isDeleting = false,
}: ComponentEditModalProps) {
  const [name, setName] = useState(component.name);
  const [tags, setTags] = useState(component.tags ?? "");
  const [criticality, setCriticality] = useState<
    "tier1_revenue" | "tier2_core" | "tier3_support"
  >(component.criticality ?? "tier2_core");
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    setName(component.name);
    setTags(component.tags ?? "");
    setCriticality(component.criticality ?? "tier2_core");
    setConfirmDelete(false);
  }, [component]);

  async function handleSave() {
    await onSave(component.id, { name: name.trim(), tags: tags.trim(), criticality });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-lg rounded-xl border border-zinc-800 bg-zinc-950 shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <h2 className="text-lg font-semibold text-zinc-100">Edit component</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 px-5 py-4">
          <label className="block space-y-1.5">
            <span className="text-sm text-zinc-400">Name</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm text-zinc-400">Tags (comma-separated)</span>
            <input
              value={tags}
              onChange={(event) => setTags(event.target.value)}
              placeholder="backend, payments, platform"
              className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm text-zinc-400">Criticality tier</span>
            <select
              value={criticality}
              onChange={(event) =>
                setCriticality(
                  event.target.value as
                    | "tier1_revenue"
                    | "tier2_core"
                    | "tier3_support",
                )
              }
              className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
            >
              {CRITICALITY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <p className="font-mono text-xs text-zinc-600">{component.id}</p>
        </div>

        <div className="flex flex-col gap-3 border-t border-zinc-800 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          {onDelete ? (
            confirmDelete ? (
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void onDelete(component.id)}
                  disabled={isDeleting || isSaving}
                  className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-3 py-2 text-sm text-white hover:bg-red-500 disabled:opacity-50"
                >
                  {isDeleting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                  Confirm delete
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmDelete(false)}
                  className="rounded-lg border border-zinc-700 px-3 py-2 text-sm text-zinc-300"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                className="inline-flex items-center gap-2 rounded-lg border border-red-500/40 px-3 py-2 text-sm text-red-300 hover:bg-red-500/10"
              >
                <Trash2 className="h-4 w-4" />
                Delete component
              </button>
            )
          ) : (
            <span />
          )}

          <div className="flex gap-2 sm:ml-auto">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={isSaving || isDeleting || !name.trim()}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
            >
              {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

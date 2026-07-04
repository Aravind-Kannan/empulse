"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { BrainCircuit, Loader2 } from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { updateWorkspaceName } from "@/lib/auth";

const INPUT_CLASS =
  "w-full rounded-xl border border-zinc-700/80 bg-black/40 px-4 py-2.5 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-sky-500/60 focus:ring-2 focus:ring-sky-500/20";

export function WorkspaceNameStep() {
  const router = useRouter();
  const { user, refreshSession } = useAuth();
  const [workspaceName, setWorkspaceName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const suggestedName = user?.name
    ? `${user.name.split(/\s+/)[0]}'s workspace`
    : "My workspace";

  async function handleContinue(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = workspaceName.trim();
    if (!trimmed) {
      setError("Workspace name is required.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await updateWorkspaceName(trimmed);
      await refreshSession();
      router.replace("/onboarding");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save workspace name.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="border-b border-zinc-800 px-6 py-5">
        <div className="mx-auto flex max-w-lg items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-800">
            <BrainCircuit className="h-5 w-5 text-zinc-100" />
          </div>
          <div>
            <p className="text-sm font-semibold text-zinc-100">Empulse</p>
            <p className="text-xs text-zinc-500">Workspace setup</p>
          </div>
        </div>
      </header>

      <main className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-lg items-center px-6 py-10">
        <form onSubmit={(event) => void handleContinue(event)} className="w-full">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-50">
            Name your workspace
          </h1>
          <p className="mt-2 text-sm text-zinc-500">
            This is how your organization will appear across Empulse.
          </p>

          <div className="mt-8">
            <label className="mb-1.5 block text-xs font-medium text-zinc-400">
              Workspace name
            </label>
            <input
              value={workspaceName}
              onChange={(event) => {
                setWorkspaceName(event.target.value);
                setError(null);
              }}
              placeholder={suggestedName}
              autoComplete="organization"
              autoFocus
              className={INPUT_CLASS}
            />
          </div>

          {error ? (
            <p className="mt-3 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={submitting}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-zinc-100 px-4 py-3 text-sm font-medium text-black transition hover:bg-white disabled:opacity-60"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Continue
          </button>
        </form>
      </main>
    </div>
  );
}

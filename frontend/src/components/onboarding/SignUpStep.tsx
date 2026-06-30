"use client";

import { useEffect } from "react";
import { BrainCircuit } from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { useOnboarding } from "@/context/OnboardingContext";

export function SignUpStep() {
  const { session } = useAuth();
  const { signUp, updateSignUp, setStep } = useOnboarding();

  useEffect(() => {
    if (session) {
      updateSignUp({
        name: session.name,
        email: session.email,
        company: session.company,
      });
    }
  }, [session, updateSignUp]);

  const canContinue =
    signUp.name.trim().length > 0 && signUp.email.trim().length > 0;

  return (
    <div className="mx-auto w-full max-w-md space-y-8">
      <div className="text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-800">
          <BrainCircuit className="h-6 w-6 text-zinc-100" />
        </div>
        <h1 className="text-2xl font-semibold text-zinc-100">
          Welcome to Empulse
        </h1>
        <p className="mt-2 text-sm text-zinc-400">
          Set up your engineering intelligence workspace in a few steps.
        </p>
      </div>

      <div className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
        <div>
          <label className="mb-1.5 block text-sm text-zinc-400">
            Full name
          </label>
          <input
            type="text"
            value={signUp.name}
            onChange={(e) => updateSignUp({ name: e.target.value })}
            placeholder="Alice Chen"
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm text-zinc-400">
            Work email
          </label>
          <input
            type="email"
            value={signUp.email}
            onChange={(e) => updateSignUp({ email: e.target.value })}
            placeholder="alice@acme.com"
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm text-zinc-400">Company</label>
          <input
            type="text"
            value={signUp.company}
            onChange={(e) => updateSignUp({ company: e.target.value })}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
          />
        </div>
      </div>

      <button
        type="button"
        disabled={!canContinue}
        onClick={() => setStep(2)}
        className="w-full rounded-lg bg-zinc-100 px-4 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
      >
        Continue to Integrations
      </button>
    </div>
  );
}

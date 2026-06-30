"use client";

import { BrainCircuit } from "lucide-react";

import { StepIndicator } from "./StepIndicator";

interface OnboardingShellProps {
  currentStep: 1 | 2 | 3;
  children: React.ReactNode;
  wide?: boolean;
}

export function OnboardingShell({
  currentStep,
  children,
  wide = false,
}: OnboardingShellProps) {
  return (
    <div className="min-h-screen bg-slate-950">
      <header className="border-b border-zinc-800 px-6 py-5">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-800">
              <BrainCircuit className="h-5 w-5 text-zinc-100" />
            </div>
            <div>
              <p className="text-sm font-semibold text-zinc-100">Empulse</p>
              <p className="text-xs text-zinc-500">Workspace setup</p>
            </div>
          </div>
          <StepIndicator currentStep={currentStep} />
        </div>
      </header>

      <main
        className={`px-6 py-10 ${wide ? "mx-auto max-w-6xl" : "mx-auto max-w-5xl"}`}
      >
        {children}
      </main>
    </div>
  );
}

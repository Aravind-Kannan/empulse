"use client";

import { BrainCircuit } from "lucide-react";

import { useOnboarding } from "@/context/OnboardingContext";

import { IntegrationsStep } from "./IntegrationsStep";
import { OrgChartStep } from "./OrgChartStep";
import { SignUpStep } from "./SignUpStep";
import { StepIndicator } from "./StepIndicator";

export function OnboardingWizard() {
  const { step } = useOnboarding();

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="border-b border-zinc-800 px-6 py-5">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-800">
              <BrainCircuit className="h-5 w-5 text-zinc-100" />
            </div>
            <div>
              <p className="text-sm font-semibold text-zinc-100">Empulse</p>
              <p className="text-xs text-zinc-500">Onboarding</p>
            </div>
          </div>
          <StepIndicator currentStep={step} />
        </div>
      </header>

      <main className="px-6 py-10">
        {step === 1 && <SignUpStep />}
        {step === 2 && <IntegrationsStep />}
        {step === 3 && <OrgChartStep />}
      </main>
    </div>
  );
}

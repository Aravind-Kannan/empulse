const steps = [
  { number: 1, label: "Integrations" },
  { number: 2, label: "Org chart" },
  { number: 3, label: "Graph sync" },
] as const;

export function StepIndicator({ currentStep }: { currentStep: number }) {
  return (
    <ol className="flex items-center justify-center gap-3 sm:gap-6">
      {steps.map((step, index) => {
        const isActive = currentStep === step.number;
        const isComplete = currentStep > step.number;

        return (
          <li key={step.number} className="flex items-center gap-3 sm:gap-6">
            <div className="flex items-center gap-2">
              <span
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                  isActive
                    ? "bg-zinc-100 text-slate-950"
                    : isComplete
                      ? "bg-emerald-600 text-white"
                      : "bg-zinc-800 text-zinc-400"
                }`}
              >
                {step.number}
              </span>
              <span
                className={`hidden text-sm sm:inline ${
                  isActive ? "text-zinc-100" : "text-zinc-500"
                }`}
              >
                {step.label}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div
                className={`h-px w-8 sm:w-16 ${
                  isComplete ? "bg-emerald-600" : "bg-zinc-800"
                }`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

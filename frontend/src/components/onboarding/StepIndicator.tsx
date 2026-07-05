const steps = [
  { number: 1, label: "Integrations" },
  { number: 2, label: "Org chart" },
] as const;

export function StepIndicator({
  currentStep,
  onStepClick,
}: {
  currentStep: number;
  onStepClick?: (step: number) => void;
}) {
  return (
    <ol className="flex items-center justify-center gap-3 sm:gap-6">
      {steps.map((step, index) => {
        const isActive = currentStep === step.number;
        const isComplete = currentStep > step.number;
        const isNavigable = isComplete && onStepClick;

        return (
          <li key={step.number} className="flex items-center gap-3 sm:gap-6">
            {isNavigable ? (
              <button
                type="button"
                onClick={() => onStepClick(step.number)}
                className="flex items-center gap-2 rounded-lg transition hover:bg-zinc-900/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/50"
                aria-label={`Go back to ${step.label}`}
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-600 text-sm font-medium text-white">
                  {step.number}
                </span>
                <span className="hidden text-sm text-zinc-400 hover:text-zinc-200 sm:inline">
                  {step.label}
                </span>
              </button>
            ) : (
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
            )}
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

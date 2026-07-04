"use client";

import { Toaster } from "sonner";

export function AppToaster() {
  return (
    <Toaster
      theme="dark"
      position="top-right"
      richColors
      closeButton
      expand={false}
      visibleToasts={4}
      duration={6_000}
      offset={16}
      toastOptions={{
        classNames: {
          toast:
            "group rounded-xl border border-zinc-700/80 bg-zinc-900 text-zinc-100 shadow-2xl",
          title: "text-sm font-medium",
          description: "text-sm text-zinc-400",
          actionButton:
            "rounded-lg bg-zinc-100 px-3 py-1.5 text-xs font-medium text-slate-950",
          cancelButton:
            "rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300",
          closeButton:
            "border-zinc-700 bg-zinc-900 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100",
          success: "border-emerald-500/40 bg-emerald-950 text-emerald-50",
          error: "border-red-500/40 bg-red-950 text-red-50",
          info: "border-sky-500/40 bg-sky-950 text-sky-50",
        },
      }}
    />
  );
}

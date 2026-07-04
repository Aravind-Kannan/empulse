"use client";

import { useEffect, type ReactNode } from "react";

import { AppToaster } from "@/components/ui/AppToaster";
import { registerToastErrorReporter } from "@/lib/toast-bus";
import { showToast, type ToastKind } from "@/lib/toast";

export type { ToastKind };

export function ToastProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    registerToastErrorReporter((message) => showToast(message, "error"));
    return () => registerToastErrorReporter(null);
  }, []);

  return (
    <>
      {children}
      <AppToaster />
    </>
  );
}

/** Thin wrapper so feature code can keep using pushToast(). */
export function useToast() {
  return {
    pushToast: showToast,
    dismissToast: () => {
      // Sonner dismisses individual toasts via close button / timeout.
    },
  };
}

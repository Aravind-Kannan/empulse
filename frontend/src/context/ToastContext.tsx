"use client";

import {
  createContext,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

import { registerToastErrorReporter } from "@/lib/toast-bus";

export type ToastKind = "error" | "success" | "info";

export interface ToastItem {
  id: string;
  message: string;
  kind: ToastKind;
}

interface ToastContextValue {
  pushToast: (message: string, kind?: ToastKind) => void;
  dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TOAST_TTL_MS = 6_000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [mounted, setMounted] = useState(false);

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const pushToast = useCallback(
    (message: string, kind: ToastKind = "error") => {
      const trimmed = message.trim();
      if (!trimmed) return;
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      setToasts((current) => [...current.slice(-4), { id, message: trimmed, kind }]);
      window.setTimeout(() => dismissToast(id), TOAST_TTL_MS);
    },
    [dismissToast],
  );

  useLayoutEffect(() => {
    setMounted(true);
    registerToastErrorReporter((message) => pushToast(message, "error"));
    return () => registerToastErrorReporter(null);
  }, [pushToast]);

  const value = useMemo(
    () => ({ pushToast, dismissToast }),
    [pushToast, dismissToast],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      {mounted
        ? createPortal(
            <ToastHost toasts={toasts} onDismiss={dismissToast} />,
            document.body,
          )
        : null}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
}

function ToastHost({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) return null;

  return (
    <div
      className="pointer-events-none fixed inset-x-4 top-4 z-[9999] flex flex-col items-end gap-2 sm:inset-x-auto sm:right-4"
      aria-live="assertive"
      aria-label="Notifications"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="alert"
          className={`pointer-events-auto w-full max-w-sm animate-toast-in rounded-xl border px-4 py-3 shadow-2xl backdrop-blur-md ${
            toast.kind === "error"
              ? "border-red-500/50 bg-red-950/95 text-red-50"
              : toast.kind === "success"
                ? "border-emerald-500/50 bg-emerald-950/95 text-emerald-50"
                : "border-zinc-600/50 bg-zinc-950/95 text-zinc-100"
          }`}
        >
          <div className="flex items-start gap-3">
            <p className="flex-1 text-sm leading-snug">{toast.message}</p>
            <button
              type="button"
              onClick={() => onDismiss(toast.id)}
              className="shrink-0 rounded-md px-1.5 py-0.5 text-xs opacity-70 transition hover:bg-white/10 hover:opacity-100"
              aria-label="Dismiss notification"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

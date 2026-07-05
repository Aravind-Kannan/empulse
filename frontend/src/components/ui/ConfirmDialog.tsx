"use client";

import type { ReactNode } from "react";
import { AlertTriangle, X } from "lucide-react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  secondaryConfirmLabel?: string;
  wide?: boolean;
  onConfirm: () => void;
  onSecondaryConfirm?: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  secondaryConfirmLabel,
  wide = false,
  onConfirm,
  onSecondaryConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close dialog"
        onClick={onCancel}
        className="absolute inset-0 bg-black/55 backdrop-blur-[2px]"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        className={`relative w-full overflow-hidden rounded-2xl border border-zinc-700/90 bg-zinc-950 shadow-2xl shadow-black/50 ring-1 ring-white/5 ${wide ? "max-w-lg" : "max-w-md"}`}
      >
        <div className="flex items-start gap-3 border-b border-zinc-800/80 px-5 py-4">
          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-amber-500/30 bg-amber-500/10">
            <AlertTriangle className="h-4 w-4 text-amber-300" />
          </span>
          <div className="min-w-0 flex-1 pr-6">
            <h3
              id="confirm-dialog-title"
              className="text-base font-semibold text-zinc-50"
            >
              {title}
            </h3>
            <div className="mt-1.5 text-sm leading-relaxed text-zinc-400">
              {description}
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="absolute right-3 top-3 rounded-lg p-1.5 text-zinc-500 transition hover:bg-zinc-900 hover:text-zinc-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex flex-col-reverse gap-2 px-5 py-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-xl border border-zinc-800 bg-zinc-900/60 px-4 py-2.5 text-sm font-medium text-zinc-300 transition hover:border-zinc-700 hover:bg-zinc-900 hover:text-zinc-100"
          >
            {cancelLabel}
          </button>
          {secondaryConfirmLabel && onSecondaryConfirm ? (
            <button
              type="button"
              onClick={onSecondaryConfirm}
              className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-sm font-medium text-emerald-100 transition hover:border-emerald-500/40 hover:bg-emerald-500/15"
            >
              {secondaryConfirmLabel}
            </button>
          ) : null}
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 px-4 py-2.5 text-sm font-medium text-white shadow-md shadow-amber-900/25 transition hover:from-amber-500 hover:to-orange-500"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

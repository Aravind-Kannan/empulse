"use client";

import { createPortal } from "react-dom";
import type { ReactNode, RefObject } from "react";
import { PanelRightOpen, X } from "lucide-react";

interface EraSidePanelProps {
  open: boolean;
  visible: boolean;
  onClose: () => void;
  eyebrow: string;
  title: string;
  subtitle?: string;
  ariaLabel: string;
  closeButtonRef?: RefObject<HTMLButtonElement | null>;
  maxWidth?: "md" | "lg";
  footer?: ReactNode;
  children: ReactNode;
}

const MAX_WIDTH_CLASS = {
  md: "max-w-md",
  lg: "max-w-lg",
} as const;

export function EraSidePanel({
  open,
  visible,
  onClose,
  eyebrow,
  title,
  subtitle,
  ariaLabel,
  closeButtonRef,
  maxWidth = "lg",
  footer,
  children,
}: EraSidePanelProps) {
  if (!open) return null;

  const content = (
    <>
      <button
        type="button"
        aria-label="Close panel"
        className="fixed inset-0 z-40 bg-black/55 backdrop-blur-[1px]"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        className={`fixed right-0 top-0 z-50 flex h-full w-full ${MAX_WIDTH_CLASS[maxWidth]} flex-col border-l border-zinc-800 bg-zinc-950 shadow-2xl transition-transform duration-200 ease-out ${
          visible ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="border-b border-zinc-800/80 bg-zinc-900/40 px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">
                  {eyebrow}
                </p>
                <span className="inline-flex items-center gap-1 rounded border border-zinc-700/80 bg-zinc-950/60 px-1.5 py-0.5 text-[9px] text-zinc-500">
                  <PanelRightOpen className="h-3 w-3" aria-hidden />
                  Side panel
                </span>
              </div>
              <h2 className="mt-0.5 text-base font-semibold text-zinc-100">{title}</h2>
              {subtitle ? (
                <p className="mt-0.5 text-[11px] text-zinc-500">{subtitle}</p>
              ) : null}
            </div>
            <button
              ref={closeButtonRef}
              type="button"
              onClick={onClose}
              className="shrink-0 rounded-md border border-zinc-800 bg-zinc-900/60 p-1.5 text-zinc-400 transition hover:border-zinc-700 hover:text-zinc-200"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">{children}</div>

        {footer ? (
          <div className="border-t border-zinc-800/80 bg-zinc-900/30 px-4 py-3">
            {footer}
          </div>
        ) : null}
      </aside>
    </>
  );

  return createPortal(content, document.body);
}

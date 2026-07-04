"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

import type { IntegrationDefinition } from "@/lib/integrations";

import { IntegrationConfigPanel } from "./IntegrationConfigPanel";
import { IntegrationLogo } from "./IntegrationLogos";

interface IntegrationConfigDrawerProps {
  app: IntegrationDefinition;
  onClose: () => void;
}

/** Legacy drawer shell — prefer `/settings/integrations/[id]` detail page. */
export function IntegrationConfigDrawer({
  app,
  onClose,
}: IntegrationConfigDrawerProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  const drawer = (
    <>
      <button
        type="button"
        aria-label="Close configuration"
        className="fixed inset-0 z-[100] bg-black/50"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="integration-drawer-title"
        className="fixed inset-y-0 right-0 z-[101] flex w-full max-w-md flex-col border-l border-zinc-800 bg-slate-950 shadow-2xl"
      >
        <div className="flex shrink-0 items-center justify-between border-b border-zinc-800 px-5 py-5">
          <div className="flex min-w-0 items-center gap-3">
            <div
              className={`flex h-11 w-11 items-center justify-center rounded-xl ${app.accentBg}`}
            >
              <IntegrationLogo
                id={app.id}
                className={`h-6 w-6 ${app.iconClassName}`}
              />
            </div>
            <div className="min-w-0">
              <h2
                id="integration-drawer-title"
                className="text-lg font-semibold text-zinc-100"
              >
                {app.name}
              </h2>
              <p className="text-xs text-zinc-500">{app.description}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="ml-3 shrink-0 rounded-lg p-1.5 text-zinc-500 transition hover:bg-zinc-900 hover:text-zinc-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
          <IntegrationConfigPanel
            app={app}
            variant="drawer"
            onDisconnectComplete={onClose}
          />
        </div>
      </aside>
    </>
  );

  if (!mounted) {
    return null;
  }

  return createPortal(drawer, document.body);
}

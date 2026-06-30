"use client";

import { Building2, Check, ChevronDown } from "lucide-react";
import { useState } from "react";

import { useAuth } from "@/context/AuthContext";

export function TenantSwitcher() {
  const { linkedTenants, activeTenant, switchTenant } = useAuth();
  const [open, setOpen] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (linkedTenants.length <= 1) {
    return null;
  }

  async function handleSelect(tenantId: string) {
    if (tenantId === activeTenant?.id) {
      setOpen(false);
      return;
    }
    setSwitching(true);
    setError(null);
    try {
      await switchTenant(tenantId);
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to switch workspace.");
    } finally {
      setSwitching(false);
    }
  }

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="mb-3 flex items-center gap-2">
        <Building2 className="h-4 w-4 text-zinc-400" />
        <div>
          <p className="text-sm font-medium text-zinc-100">Workspace accounts</p>
          <p className="text-xs text-zinc-500">
            Switch between linked organizational workspaces.
          </p>
        </div>
      </div>

      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          disabled={switching}
          className="flex w-full items-center justify-between rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-left text-sm text-zinc-100 transition hover:border-zinc-600 disabled:opacity-60"
        >
          <span>{activeTenant?.companyName ?? "Select workspace"}</span>
          <ChevronDown className="h-4 w-4 text-zinc-500" />
        </button>

        {open && (
          <div className="absolute z-20 mt-2 w-full overflow-hidden rounded-lg border border-zinc-700 bg-zinc-950 shadow-xl">
            {linkedTenants.map((tenant) => (
              <button
                key={tenant.id}
                type="button"
                onClick={() => handleSelect(tenant.id)}
                className="flex w-full items-center justify-between px-3 py-2.5 text-left text-sm text-zinc-200 transition hover:bg-zinc-900"
              >
                <span>{tenant.companyName}</span>
                {tenant.isActive && (
                  <Check className="h-4 w-4 text-emerald-400" />
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {error && <p className="mt-2 text-xs text-red-300">{error}</p>}
    </section>
  );
}

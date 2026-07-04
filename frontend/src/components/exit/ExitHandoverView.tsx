"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Download, FileText, Loader2, Send, UserRound } from "lucide-react";

import { PanelDataLoader } from "@/components/ui/PanelDataLoader";

import { EmployeeSearchCombobox } from "@/components/exit/EmployeeSearchCombobox";
import { HandoverMarkdownPreview } from "@/components/exit/HandoverMarkdownPreview";
import { useToast } from "@/context/ToastContext";
import { fetchExitEmployees, fetchHandover, sendHandoverSlack } from "@/lib/api";
import { formatLocalDateTime } from "@/lib/datetime";
import type { EmployeeOption, HandoverResponse } from "@/lib/types";

function handoverBaseFilename(employeeName: string): string {
  const safe = employeeName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
  return `handover_${safe || "employee"}`;
}

function handoverMarkdownContent(handover: HandoverResponse): string {
  return handover.markdown_content ?? handover.markdown;
}

function ExitHandoverContent() {
  const searchParams = useSearchParams();
  const employeeParam = searchParams.get("employee");
  const prefillEra = searchParams.get("prefill") === "era";

  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [handover, setHandover] = useState<HandoverResponse | null>(null);
  const [loadingEmployees, setLoadingEmployees] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [sendingSlack, setSendingSlack] = useState(false);
  const { pushToast } = useToast();

  useEffect(() => {
    fetchExitEmployees()
      .then((data) => {
        setEmployees(data);
        if (employeeParam && data.some((emp) => emp.id === employeeParam)) {
          setSelectedId(employeeParam);
        }
      })
      .catch(() => {
        setEmployees([]);
      })
      .finally(() => setLoadingEmployees(false));
  }, [employeeParam]);

  useEffect(() => {
    if (!selectedId) {
      setHandover(null);
      return;
    }

    let cancelled = false;
    setHandover(null);
    setGenerating(true);

    fetchHandover(selectedId, { prefillEra })
      .then((data) => {
        if (!cancelled) setHandover(data);
      })
      .catch(() => {
        if (!cancelled) setHandover(null);
      })
      .finally(() => {
        if (!cancelled) setGenerating(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedId, prefillEra]);

  const selectedEmployee = useMemo(
    () => employees.find((emp) => emp.id === selectedId) ?? null,
    [employees, selectedId],
  );

  function handleDownload() {
    if (!handover) return;
    const content = handoverMarkdownContent(handover);
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    const base =
      handover.filename?.replace(/\.md$/i, "") ??
      handoverBaseFilename(handover.employee_name);
    anchor.download = `${base}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function handleSendSlack() {
    if (!handover || !selectedId) return;
    setSendingSlack(true);
    try {
      const result = await sendHandoverSlack(selectedId, {
        prefillEra,
        markdown: handoverMarkdownContent(handover),
        filename: handover.filename,
      });
      pushToast(result.message, "success");
    } catch (error) {
      pushToast(
        error instanceof Error
          ? error.message
          : "Failed to send handover to Slack",
        "error",
      );
    } finally {
      setSendingSlack(false);
    }
  }

  if (loadingEmployees) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">
            Employee Knowledge Handover
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Generate and deliver knowledge handover documentation for departing engineers.
          </p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40">
          <PanelDataLoader
            icon={FileText}
            label="Loading employee roster…"
            sublabel="Fetching engineers available for handover compilation."
            steps={[
              "Loading org roster",
              "Checking integration coverage",
              "Preparing handover workspace",
            ]}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">
          Employee Knowledge Handover
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Generate and deliver knowledge handover documentation for departing engineers.
        </p>
      </div>

      {prefillEra ? (
        <div className="rounded-lg border border-violet-500/40 bg-violet-500/10 p-4 text-sm text-violet-100">
          <p className="font-medium">Pre-filled from ERA risk assessment</p>
          {handover?.era_computed_at ? (
            <p className="mt-1 text-xs text-violet-200/80">
              Risk data computed at{" "}
              {formatLocalDateTime(handover.era_computed_at)}
              {handover.era_risk_score != null
                ? ` — score ${Math.round(handover.era_risk_score)}%`
                : ""}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
        <label
          htmlFor="exit-employee-search"
          className="mb-2 block text-sm text-zinc-400"
        >
          Select engineer
        </label>
        <EmployeeSearchCombobox
          employees={employees}
          selectedId={selectedId}
          onSelect={setSelectedId}
          disabled={generating}
        />
      </div>

      <section className="relative min-h-[28rem] overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/40">
        <div className="flex flex-col gap-3 border-b border-zinc-800 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950/60">
              <FileText className="h-4 w-4 text-zinc-400" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-zinc-100">
                {handover
                  ? `Handover blueprint — ${handover.employee_name}`
                  : "Handover document preview"}
              </p>
              <p className="truncate text-xs text-zinc-500">
                {generating
                  ? "Compiling handover document…"
                  : handover
                    ? handover.filename
                    : selectedEmployee
                      ? `Ready to generate for ${selectedEmployee.name}`
                      : "No engineer selected"}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleSendSlack}
              disabled={!handover || generating || sendingSlack}
              className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {sendingSlack ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
              Send to Slack DM
            </button>
            <button
              type="button"
              onClick={handleDownload}
              disabled={!handover || generating || sendingSlack}
              className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Download className="h-4 w-4" />
              Download Asset Pack
            </button>
          </div>
        </div>

        <div className="relative max-h-[calc(100vh-20rem)] min-h-[24rem] overflow-auto p-6 md:p-8">
          {!selectedId ? (
            <div className="flex h-full min-h-[20rem] flex-col items-center justify-center rounded-lg border border-dashed border-zinc-800 bg-zinc-950/30 px-6 text-center">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-900/50">
                <UserRound className="h-7 w-7 text-zinc-500" />
              </div>
              <p className="text-base font-medium text-zinc-200">
                Select an engineer to begin
              </p>
              <p className="mt-2 max-w-md text-sm text-zinc-500">
                Search for a departing team member above. Empulse will compile
                ownership, open tasks, operational context, and documentation
                gaps into a downloadable handover pack.
              </p>
            </div>
          ) : handover ? (
            <HandoverMarkdownPreview markdown={handoverMarkdownContent(handover)} />
          ) : selectedId ? (
            <div className="min-h-[20rem]" />
          ) : null}
        </div>

        {generating ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-slate-950/60 backdrop-blur-[2px]">
            <div className="w-full max-w-md rounded-xl border border-zinc-800 bg-zinc-950/95 px-2 py-2 shadow-xl">
              <PanelDataLoader
                icon={FileText}
                label="Generating handover pack…"
                sublabel="Compiling ownership, tasks, Slack context, and documentation gaps."
                steps={[
                  "Querying knowledge graph",
                  "Gathering open Jira tasks",
                  "Assembling handover document",
                ]}
              />
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function ExitHandoverFallback() {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40">
      <PanelDataLoader
        icon={FileText}
        label="Loading knowledge handover…"
        sublabel="Preparing the handover workspace."
      />
    </div>
  );
}

export function ExitHandoverView() {
  return (
    <Suspense fallback={<ExitHandoverFallback />}>
      <ExitHandoverContent />
    </Suspense>
  );
}

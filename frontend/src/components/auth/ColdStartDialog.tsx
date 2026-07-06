"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Database, Radio, Server, X } from "lucide-react";

import { useReducedMotion } from "@/hooks/useReducedMotion";
import { notifyBackendServicesReady, probeBackendServicesStatus } from "@/lib/backend-warmup";
import { SUPPORT_GITHUB_ISSUES_URL } from "@/lib/support";

const POLL_INTERVAL_MS = 6_000;
const PING_TIMEOUT_MS = 4_000;
const MAX_WARMUP_ATTEMPTS = 10;

type DialogState = "probing" | "ready" | "exhausted";
type PingPhase = "pinging" | "waiting";

interface ColdStartDialogProps {
  open: boolean;
  onCancel: () => void;
  onReady: () => void;
}

export function ColdStartDialog({ open, onCancel, onReady }: ColdStartDialogProps) {
  const reducedMotion = useReducedMotion();
  const [dialogState, setDialogState] = useState<DialogState>("probing");
  const [apiReached, setApiReached] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [pingPhase, setPingPhase] = useState<PingPhase>("waiting");
  const [probeSession, setProbeSession] = useState(0);
  const readyRef = useRef(false);
  const onReadyRef = useRef(onReady);

  useEffect(() => {
    onReadyRef.current = onReady;
  }, [onReady]);

  const resetProbing = useCallback(() => {
    readyRef.current = false;
    setDialogState("probing");
    setApiReached(false);
    setAttempt(0);
    setPingPhase("waiting");
  }, []);

  const handleRetry = useCallback(() => {
    resetProbing();
    setProbeSession((session) => session + 1);
  }, [resetProbing]);

  useEffect(() => {
    if (!open) {
      readyRef.current = false;
      setDialogState("probing");
      setApiReached(false);
      setAttempt(0);
      setPingPhase("waiting");
      return;
    }

    let cancelled = false;
    let attempts = 0;
    let probing = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const stopPolling = () => {
      if (timer !== null) {
        clearInterval(timer);
        timer = null;
      }
    };

    const runPing = async () => {
      if (probing || readyRef.current || cancelled) return;

      attempts += 1;
      setAttempt(attempts);
      setPingPhase("pinging");
      setApiReached(false);

      probing = true;
      try {
        const status = await probeBackendServicesStatus(PING_TIMEOUT_MS);
        if (cancelled || readyRef.current) return;

        setApiReached(status.api);

        if (status.api && status.database) {
          readyRef.current = true;
          stopPolling();
          setPingPhase("waiting");
          setDialogState("ready");
          notifyBackendServicesReady();
          window.setTimeout(() => {
            if (!cancelled) onReadyRef.current();
          }, 450);
          return;
        }

        setPingPhase("waiting");

        if (attempts >= MAX_WARMUP_ATTEMPTS) {
          stopPolling();
          setDialogState("exhausted");
        }
      } finally {
        probing = false;
      }
    };

    void runPing();
    timer = setInterval(() => {
      if (!readyRef.current && attempts < MAX_WARMUP_ATTEMPTS) {
        void runPing();
      } else if (attempts >= MAX_WARMUP_ATTEMPTS && !readyRef.current) {
        stopPolling();
        setDialogState("exhausted");
      } else {
        stopPolling();
      }
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [open, probeSession]);

  const statusText =
    dialogState === "ready"
      ? "Backend is awake — continuing…"
      : dialogState === "exhausted"
        ? `No response after ${MAX_WARMUP_ATTEMPTS} attempts.`
        : apiReached
          ? "Render API responded — waking Postgres…"
          : "Pinging Render API services…";

  const isExhausted = dialogState === "exhausted";
  const isReady = dialogState === "ready";
  const progressPct = Math.min(100, (attempt / MAX_WARMUP_ATTEMPTS) * 100);
  const statusKey = `${attempt}-${apiReached ? "db" : "api"}-${pingPhase}`;

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[70] flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
        >
          <button
            type="button"
            aria-label="Close dialog"
            onClick={onCancel}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="cold-start-title"
            initial={{ opacity: 0, scale: 0.94, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ type: "spring", stiffness: 420, damping: 30 }}
            className="relative w-full max-w-md overflow-hidden rounded-2xl border border-zinc-700/90 bg-zinc-950 shadow-2xl shadow-black/50 ring-1 ring-white/5"
          >
            <button
              type="button"
              onClick={onCancel}
              className="absolute right-3 top-3 z-10 rounded-lg p-1.5 text-zinc-500 transition hover:bg-zinc-900 hover:text-zinc-300"
            >
              <X className="h-4 w-4" />
            </button>

            <div className="relative px-6 pb-6 pt-8">
              <div
                className={`pointer-events-none absolute inset-x-0 top-0 h-28 ${
                  isExhausted
                    ? "bg-[radial-gradient(ellipse_70%_80%_at_50%_0%,rgba(251,191,36,0.12),transparent)]"
                    : "bg-[radial-gradient(ellipse_70%_80%_at_50%_0%,rgba(56,189,248,0.14),transparent)]"
                }`}
              />

              <div className="relative mx-auto mb-5 flex h-24 w-24 items-center justify-center">
                {!isExhausted && !reducedMotion ? (
                  <>
                    <motion.span
                      className="absolute inset-0 rounded-full border border-sky-500/25"
                      animate={{ scale: [1, 1.45, 1], opacity: [0.55, 0, 0.55] }}
                      transition={{
                        duration: 2.2,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                    />
                    <motion.span
                      className="absolute inset-2 rounded-full border border-sky-400/20"
                      animate={{ scale: [1, 1.3, 1], opacity: [0.45, 0.08, 0.45] }}
                      transition={{
                        duration: 2.2,
                        repeat: Infinity,
                        ease: "easeInOut",
                        delay: 0.35,
                      }}
                    />
                    {pingPhase === "pinging" ? (
                      <motion.span
                        key={`ping-burst-${attempt}`}
                        className="absolute inset-0 rounded-full bg-sky-400/20"
                        initial={{ scale: 0.85, opacity: 0.7 }}
                        animate={{ scale: 1.35, opacity: 0 }}
                        transition={{ duration: 0.75, ease: "easeOut" }}
                      />
                    ) : null}
                  </>
                ) : null}
                <motion.div
                  animate={
                    reducedMotion || isExhausted
                      ? undefined
                      : pingPhase === "pinging"
                        ? { scale: [1, 1.06, 1] }
                        : { scale: 1 }
                  }
                  transition={{ duration: 0.45 }}
                  className={`relative flex h-14 w-14 items-center justify-center rounded-2xl border ${
                    isExhausted
                      ? "border-amber-500/30 bg-amber-500/10"
                      : "border-sky-500/30 bg-sky-500/10"
                  }`}
                >
                  {isExhausted ? (
                    <AlertTriangle className="h-6 w-6 text-amber-300" />
                  ) : (
                    <Server className="h-6 w-6 text-sky-300" />
                  )}
                </motion.div>
              </div>

              <h3
                id="cold-start-title"
                className="text-center text-lg font-semibold text-zinc-50"
              >
                {isExhausted
                  ? "Servers still asleep"
                  : "Waking up free-tier servers"}
              </h3>

              {isExhausted ? (
                <p className="mt-3 text-center text-sm leading-relaxed text-zinc-400">
                  We pinged Render {MAX_WARMUP_ATTEMPTS} times and couldn&apos;t
                  reach the backend. Want to try waking it again, or{" "}
                  <Link
                    href={SUPPORT_GITHUB_ISSUES_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-sky-400 underline-offset-2 hover:text-sky-300 hover:underline"
                  >
                    report it on GitHub
                  </Link>
                  ?
                </p>
              ) : (
                <p className="mt-3 text-center text-sm leading-relaxed text-zinc-400">
                  Empulse runs on free Render hosting that sleeps when idle.
                  We&apos;re pinging your backend services now so you can sign in
                  — this usually takes under a minute on first visit.
                </p>
              )}

              <div className="mt-5 rounded-xl border border-zinc-800/80 bg-black/30 px-4 py-3">
                <div className="flex items-start gap-2 text-sm text-zinc-300">
                  {!isExhausted ? (
                    <motion.span
                      animate={{ rotate: isReady ? 0 : 360 }}
                      transition={{
                        duration: 1.1,
                        repeat: isReady || reducedMotion ? 0 : Infinity,
                        ease: "linear",
                      }}
                      className="mt-0.5 inline-flex shrink-0"
                    >
                      <Radio
                        className={`h-4 w-4 ${isReady ? "text-emerald-400" : "text-sky-400"}`}
                      />
                    </motion.span>
                  ) : (
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
                  )}
                  <div className="min-w-0 flex-1">
                    <AnimatePresence mode="wait">
                      <motion.span
                        key={isExhausted ? "exhausted" : statusKey}
                        initial={reducedMotion ? false : { opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={reducedMotion ? undefined : { opacity: 0, y: -8 }}
                        transition={{ duration: 0.22 }}
                        className="block"
                      >
                        {statusText}
                      </motion.span>
                    </AnimatePresence>
                  </div>
                </div>

                {!isExhausted ? (
                  <>
                    <div className="mt-3 flex items-center gap-3 text-xs text-zinc-500">
                      <motion.span
                        animate={{
                          color: apiReached
                            ? "rgba(56,189,248,0.85)"
                            : "rgba(113,113,122,1)",
                        }}
                        className="inline-flex items-center gap-1"
                      >
                        <Server className="h-3.5 w-3.5" />
                        Render API
                      </motion.span>
                      <span className="text-zinc-700">→</span>
                      <motion.span
                        animate={{
                          color: apiReached
                            ? "rgba(56,189,248,0.85)"
                            : "rgba(113,113,122,1)",
                        }}
                        className="inline-flex items-center gap-1"
                      >
                        <Database className="h-3.5 w-3.5" />
                        Postgres
                      </motion.span>
                    </div>

                    <div className="mt-3">
                      <div className="mb-1.5 flex items-center justify-between text-xs text-zinc-600">
                        <span>
                          Attempt {attempt} of {MAX_WARMUP_ATTEMPTS}
                        </span>
                        <span>
                          {pingPhase === "pinging" ? "Pinging…" : "Next ping soon…"}
                        </span>
                      </div>
                      <div className="relative h-2 overflow-hidden rounded-full bg-zinc-800/90">
                        <motion.div
                          className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-sky-600 via-sky-400 to-cyan-300"
                          initial={false}
                          animate={{ width: `${progressPct}%` }}
                          transition={
                            reducedMotion
                              ? { duration: 0 }
                              : { type: "spring", stiffness: 320, damping: 30 }
                          }
                        />
                        {pingPhase === "waiting" &&
                        attempt > 0 &&
                        attempt < MAX_WARMUP_ATTEMPTS &&
                        !reducedMotion ? (
                          <motion.div
                            className="absolute inset-y-0 w-1/3 rounded-full bg-white/25"
                            initial={{ x: "-100%" }}
                            animate={{ x: "400%" }}
                            transition={{
                              duration: 1.4,
                              repeat: Infinity,
                              ease: "easeInOut",
                            }}
                          />
                        ) : null}
                      </div>
                    </div>
                  </>
                ) : null}
              </div>

              {isExhausted ? (
                <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                  <button
                    type="button"
                    onClick={onCancel}
                    className="rounded-xl border border-zinc-800 bg-zinc-900/60 px-4 py-2.5 text-sm font-medium text-zinc-300 transition hover:border-zinc-700 hover:bg-zinc-900 hover:text-zinc-100"
                  >
                    Close
                  </button>
                  <button
                    type="button"
                    onClick={handleRetry}
                    className="rounded-xl bg-gradient-to-r from-sky-600 to-cyan-600 px-4 py-2.5 text-sm font-medium text-white shadow-md shadow-sky-900/30 transition hover:from-sky-500 hover:to-cyan-500"
                  >
                    Try again
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={onCancel}
                  className="mt-5 w-full rounded-xl border border-zinc-800 bg-zinc-900/60 px-4 py-2.5 text-sm font-medium text-zinc-300 transition hover:border-zinc-700 hover:bg-zinc-900 hover:text-zinc-100"
                >
                  Cancel
                </button>
              )}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

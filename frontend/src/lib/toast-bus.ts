/**
 * Global error toast bus for api-client (decoupled from React context).
 */

import { isBackendWarmupActive } from "./backend-warmup-state";

type ToastErrorReporter = (message: string) => void;

let toastErrorReporter: ToastErrorReporter | null = null;
const pendingToastErrors: string[] = [];

export function registerToastErrorReporter(reporter: ToastErrorReporter | null) {
  toastErrorReporter = reporter;
  if (!reporter) return;
  while (pendingToastErrors.length > 0) {
    const message = pendingToastErrors.shift();
    if (message) reporter(message);
  }
}

export function reportToastError(message: string, skip = false) {
  if (skip || !message.trim() || isBackendWarmupActive()) return;
  if (toastErrorReporter) {
    toastErrorReporter(message);
    return;
  }
  pendingToastErrors.push(message);
  if (pendingToastErrors.length > 8) {
    pendingToastErrors.shift();
  }
}

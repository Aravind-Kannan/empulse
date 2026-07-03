/**
 * Lightweight global error toast bus (decoupled from api-client bundling).
 */

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
  if (skip || !message.trim()) return;
  if (toastErrorReporter) {
    toastErrorReporter(message);
    return;
  }
  pendingToastErrors.push(message);
  if (pendingToastErrors.length > 8) {
    pendingToastErrors.shift();
  }
}

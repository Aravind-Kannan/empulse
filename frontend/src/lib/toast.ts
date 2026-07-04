import { toast } from "sonner";

export type ToastKind = "error" | "success" | "info";

const TOAST_DURATION_MS = 6_000;

export function showToast(message: string, kind: ToastKind = "error") {
  const trimmed = message.trim();
  if (!trimmed) return;

  const options = { duration: TOAST_DURATION_MS };

  switch (kind) {
    case "success":
      toast.success(trimmed, options);
      break;
    case "info":
      toast.info(trimmed, options);
      break;
    default:
      toast.error(trimmed, options);
      break;
  }
}

export function showErrorToast(message: string) {
  showToast(message, "error");
}

export function showSuccessToast(message: string) {
  showToast(message, "success");
}

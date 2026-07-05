const HAS_TIMEZONE_SUFFIX = /(?:[zZ]|[+-]\d{2}:\d{2})$/;
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Parse API datetimes for display/math. Backend stores UTC; naive ISO strings
 * (no Z) are treated as UTC, then shown in the browser's local timezone.
 */
export function parseApiDateTime(value: string | null | undefined): Date | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;

  if (DATE_ONLY.test(trimmed)) {
    const date = new Date(`${trimmed}T00:00:00`);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  const normalized = HAS_TIMEZONE_SUFFIX.test(trimmed) ? trimmed : `${trimmed}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function apiDateToEpochMs(value: string | null | undefined): number {
  return parseApiDateTime(value)?.getTime() ?? 0;
}

/** Full date + time in the user's locale and local timezone. */
export function formatLocalDateTime(
  value: string | null | undefined,
  options?: Intl.DateTimeFormatOptions,
): string {
  const date = parseApiDateTime(value);
  if (!date) return "—";
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    ...options,
  });
}

/** Calendar date in the user's locale and local timezone. */
export function formatLocalDate(
  value: string | null | undefined,
  options?: Intl.DateTimeFormatOptions,
): string {
  const date = parseApiDateTime(value);
  if (!date) return "—";
  return date.toLocaleDateString(undefined, options);
}

/** Compact relative time for recent activity (e.g. "2h ago"). */
export function formatRelativeTime(value: string | null | undefined): string {
  const date = parseApiDateTime(value);
  if (!date) return "—";

  const diffSec = Math.round((date.getTime() - Date.now()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

  const absSec = Math.abs(diffSec);
  if (absSec < 60) return rtf.format(diffSec, "second");

  const diffMin = Math.round(diffSec / 60);
  if (Math.abs(diffMin) < 60) return rtf.format(diffMin, "minute");

  const diffHr = Math.round(diffMin / 60);
  if (Math.abs(diffHr) < 24) return rtf.format(diffHr, "hour");

  const diffDay = Math.round(diffHr / 24);
  if (Math.abs(diffDay) < 30) return rtf.format(diffDay, "day");

  return formatLocalDate(value);
}

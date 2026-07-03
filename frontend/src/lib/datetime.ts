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

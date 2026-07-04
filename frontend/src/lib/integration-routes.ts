import type { IntegrationId } from "@/lib/integrations";

export type IntegrationDetailTab =
  | "overview"
  | "configuration"
  | "runs"
  | "repositories";

const INTEGRATION_IDS: IntegrationId[] = ["slack", "notion", "github", "jira"];

export function parseIntegrationId(value: string): IntegrationId | null {
  return INTEGRATION_IDS.includes(value as IntegrationId)
    ? (value as IntegrationId)
    : null;
}

export function parseIntegrationDetailTab(
  value: string | null,
): IntegrationDetailTab {
  if (
    value === "configuration" ||
    value === "runs" ||
    value === "repositories"
  ) {
    return value;
  }
  return "overview";
}

export function integrationDetailPath(
  id: IntegrationId,
  options?: { tab?: IntegrationDetailTab; returnTo?: string },
): string {
  const params = new URLSearchParams();
  if (options?.tab && options.tab !== "overview") {
    params.set("tab", options.tab);
  }
  if (options?.returnTo) {
    params.set("returnTo", options.returnTo);
  }
  const query = params.toString();
  return query
    ? `/settings/integrations/${id}?${query}`
    : `/settings/integrations/${id}`;
}

export function integrationListPath(returnTo?: string): string {
  if (!returnTo) {
    return "/settings/integrations";
  }
  return `/settings/integrations?returnTo=${encodeURIComponent(returnTo)}`;
}

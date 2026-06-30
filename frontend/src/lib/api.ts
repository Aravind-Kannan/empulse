import type {
  DashboardMetrics,
  EmployeeOption,
  EraAnalyticsResponse,
  GlobalSyncResult,
  HandoverResponse,
  IncidentStatus,
  IncidentSummary,
  IntegrationSyncResult,
  InvestigationDiagnostics,
  KraAnalyticsResponse,
  KraBackupAssignmentResponse,
  OrgChartIngestResponse,
  OrgChartPayload,
  NotionSimulationRequest,
  SimulationStreamEvent,
  IdentityReconciliationResponse,
  EmployeeIdentityMapping,
  IdentityProvider,
  EmployeeMasterDataResponse,
  BulkCsvRow,
  BulkUploadResponse,
  EmployeeUpdateResponse,
} from "./types";
import type { IntegrationConfigMap, IntegrationId } from "./integrations";
import { API_BASE, apiFetch } from "./api-client";

export async function fetchOrgChart(): Promise<OrgChartPayload> {
  const response = await apiFetch(`${API_BASE}/api/ingest/org-chart`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load org chart (${response.status})`);
  }
  return response.json();
}

export async function fetchOrgRoles(): Promise<string[]> {
  const response = await apiFetch(`${API_BASE}/api/org/roles`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load org roles (${response.status})`);
  }
  return response.json();
}

export async function updateOrgEmployee(
  employeeId: string,
  payload: {
    name?: string;
    role?: string;
    email?: string;
    tenure_years?: number;
    manager_id?: string | null;
    team_name?: string | null;
    assignment?: {
      component_id: string | null;
      codebase_share_pct?: number;
    } | null;
    assignments?: { component_ids: string[] } | null;
  },
): Promise<EmployeeUpdateResponse> {
  const response = await apiFetch(`${API_BASE}/api/org/employees/${employeeId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Employee update failed"));
  }
  return response.json();
}

export async function validateBulkOrgUpload(payload: {
  company: string;
  rows: BulkCsvRow[];
  current_org: OrgChartPayload;
}): Promise<BulkUploadResponse> {
  const response = await apiFetch(`${API_BASE}/api/org/bulk-upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, dry_run: true }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Bulk upload validation failed"));
  }
  return response.json();
}

export async function applyBulkOrgUpload(payload: {
  company: string;
  rows: BulkCsvRow[];
  current_org: OrgChartPayload;
}): Promise<BulkUploadResponse> {
  const response = await apiFetch(`${API_BASE}/api/org/bulk-upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, dry_run: false }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Bulk upload apply failed"));
  }
  return response.json();
}

export async function ingestOrgChart(
  payload: OrgChartPayload,
): Promise<OrgChartIngestResponse> {
  const response = await apiFetch(`${API_BASE}/api/ingest/org-chart`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const detail =
      typeof errorBody?.detail === "string"
        ? errorBody.detail
        : `Ingest failed (${response.status})`;
    throw new Error(detail);
  }

  return response.json();
}

export async function fetchEraMetrics(): Promise<EraAnalyticsResponse> {
  const response = await apiFetch(`${API_BASE}/api/analytics/era`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to load ERA metrics (${response.status})`);
  }

  return response.json();
}

export async function fetchKraGraph(): Promise<KraAnalyticsResponse> {
  const response = await apiFetch(`${API_BASE}/api/analytics/kra`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to load KRA graph (${response.status})`);
  }

  return response.json();
}

export async function assignKraBackup(payload: {
  component_id: string;
  employee_id: string;
  codebase_share_pct?: number;
}): Promise<KraBackupAssignmentResponse> {
  const response = await apiFetch(`${API_BASE}/api/analytics/kra/assign-backup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const detail =
      typeof errorBody?.detail === "string"
        ? errorBody.detail
        : `Backup assignment failed (${response.status})`;
    throw new Error(detail);
  }

  return response.json();
}

export async function fetchIncidents(
  status?: IncidentStatus,
): Promise<IncidentSummary[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const response = await apiFetch(`${API_BASE}/api/investigation/incidents${query}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load incidents (${response.status})`);
  }
  const data = await response.json();
  return data.incidents;
}

export async function updateIncidentStatus(
  incidentId: string,
  status: IncidentStatus,
): Promise<IncidentSummary> {
  const response = await apiFetch(
    `${API_BASE}/api/investigation/incidents/${incidentId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to update incident (${response.status})`);
  }
  return response.json();
}

export async function streamInvestigationChat(
  message: string,
  incidentId: string | null,
  onToken: (token: string) => void,
  onDiagnostics: (diagnostics: InvestigationDiagnostics) => void,
): Promise<void> {
  const response = await apiFetch(`${API_BASE}/api/investigation/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, incident_id: incidentId }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat stream failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = JSON.parse(line.slice(6)) as {
        type: string;
        content?: string;
        diagnostics?: InvestigationDiagnostics;
      };
      if (payload.type === "token" && payload.content) {
        onToken(payload.content);
      } else if (payload.type === "diagnostics" && payload.diagnostics) {
        onDiagnostics(payload.diagnostics);
      }
    }
  }
}

export async function fetchDashboardMetrics(): Promise<DashboardMetrics> {
  const response = await apiFetch(`${API_BASE}/api/dashboard/metrics`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load dashboard metrics (${response.status})`);
  }
  return response.json();
}

export async function fetchExitEmployees(): Promise<EmployeeOption[]> {
  const response = await apiFetch(`${API_BASE}/api/exit/employees`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load employees (${response.status})`);
  }
  return response.json();
}

export async function fetchHandover(employeeId: string): Promise<HandoverResponse> {
  const response = await apiFetch(
    `${API_BASE}/api/exit/handover?id=${encodeURIComponent(employeeId)}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Failed to generate handover (${response.status})`);
  }
  return response.json();
}

async function parseApiError(response: Response, fallback: string): Promise<string> {
  const errorBody = await response.json().catch(() => null);
  return typeof errorBody?.detail === "string"
    ? errorBody.detail
    : `${fallback} (${response.status})`;
}

export async function validateNotionIntegration(
  integrationToken: string,
): Promise<string> {
  const response = await apiFetch(`${API_BASE}/api/integrations/notion/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ integration_token: integrationToken }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Notion token validation failed"));
  }
  const data = (await response.json()) as { message: string };
  return data.message;
}

export async function validateSlackIntegration(
  botToken: string,
): Promise<string> {
  const response = await apiFetch(`${API_BASE}/api/integrations/slack/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bot_token: botToken }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Slack token validation failed"));
  }
  const data = (await response.json()) as { message: string };
  return data.message;
}

export async function saveGitHubIntegrationConfig(
  config: IntegrationConfigMap["github"],
): Promise<void> {
  const response = await apiFetch(`${API_BASE}/api/integrations/github/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repository_url: config.repositoryUrl,
      branch_target: config.branchTarget,
      personal_access_token: config.personalAccessToken,
      oauth_connected: config.oauthConnected,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "GitHub config save failed"));
  }
}

export async function saveJiraIntegrationConfig(
  config: IntegrationConfigMap["jira"],
): Promise<void> {
  const response = await apiFetch(`${API_BASE}/api/integrations/jira/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      site_url: config.siteUrl,
      project_keys: config.projectKeys,
      api_token: config.apiToken,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Jira config save failed"));
  }
}

export async function syncIntegrationSource(
  source: "github" | "jira",
): Promise<IntegrationSyncResult> {
  const response = await apiFetch(`${API_BASE}/api/integrations/sync/${source}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, `${source} sync failed`));
  }
  return response.json();
}

export async function syncAllIntegrations(): Promise<GlobalSyncResult> {
  const response = await apiFetch(`${API_BASE}/api/integrations/sync`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Global sync failed"));
  }
  return response.json();
}

export async function saveAndSyncIntegration(
  id: IntegrationId,
  config: IntegrationConfigMap,
): Promise<IntegrationSyncResult | null> {
  if (id === "github") {
    await saveGitHubIntegrationConfig(config.github);
    return syncIntegrationSource("github");
  }
  if (id === "jira") {
    await saveJiraIntegrationConfig(config.jira);
    return syncIntegrationSource("jira");
  }
  return null;
}

export async function streamNotionSimulation(
  payload: NotionSimulationRequest,
  onEvent: (event: SimulationStreamEvent) => void,
): Promise<void> {
  const response = await apiFetch(`${API_BASE}/api/test/run-simulation/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      notion_integration_token: payload.notion_integration_token ?? "",
      notion_database_id: payload.notion_database_id ?? "",
      ollama_model: payload.ollama_model ?? "llama3.2",
    }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Simulation stream failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const event = JSON.parse(line.slice(6)) as SimulationStreamEvent;
      onEvent(event);
    }
  }
}

export async function fetchEmployeeMasterData(
  sources: IntegrationId[],
  company?: string,
  integrationConfig?: IntegrationConfigMap,
): Promise<EmployeeMasterDataResponse> {
  const response = await apiFetch(`${API_BASE}/api/integrations/fetch-users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sources,
      company: company ?? "My Company",
      flat_hierarchy: false,
      slack_bot_token: integrationConfig?.slack.botToken ?? null,
      notion_integration_token: integrationConfig?.notion.integrationToken ?? null,
      notion_database_ids: integrationConfig?.notion.databaseIds ?? null,
      github_repository_url: integrationConfig?.github.repositoryUrl ?? null,
      github_personal_access_token:
        integrationConfig?.github.personalAccessToken ?? null,
      jira_site_url: integrationConfig?.jira.siteUrl ?? null,
      jira_api_token: integrationConfig?.jira.apiToken ?? null,
    }),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Employee master data fetch failed"));
  }
  return response.json();
}

export async function fetchIdentityReconciliation(
  connectedProviders: IdentityProvider[],
): Promise<IdentityReconciliationResponse> {
  const params = new URLSearchParams();
  for (const provider of connectedProviders) {
    params.append("connected", provider);
  }
  const query = params.toString();
  const response = await apiFetch(
    `${API_BASE}/api/identity/reconciliation${query ? `?${query}` : ""}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Failed to load identity reconciliation (${response.status})`);
  }
  return response.json();
}

export async function saveIdentityMappings(
  mappings: EmployeeIdentityMapping[],
): Promise<void> {
  const response = await apiFetch(`${API_BASE}/api/identity/mappings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mappings }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Identity mapping save failed"));
  }
}

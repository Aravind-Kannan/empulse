import type {
  DashboardMetrics,
  EmployeeOption,
  EraAnalyticsResponse,
  EraEmployeeDetailResponse,
  EraHotspotsResponse,
  EraReviewNetworkResponse,
  EraTeamRiskyChangesResponse,
  GlobalSyncResult,
  HandoverResponse,
  IncidentStatus,
  IncidentSummary,
  IntegrationSyncResult,
  InvestigationDiagnostics,
  KraAnalyticsResponse,
  KraBackupAssignmentResponse,
  KraFileRiskResponse,
  OrgChartIngestResponse,
  OrgChartPayload,
  IngestJobAcceptedResponse,
  IngestJobStatusResponse,
  NotionSimulationRequest,
  SimulationStreamEvent,
  IdentityReconciliationResponse,
  EmployeeIdentityMapping,
  IdentityProvider,
  EmployeeMasterDataResponse,
  MemberRosterSyncResult,
  BulkCsvRow,
  BulkUploadResponse,
  EmployeeUpdateResponse,
} from "./types";
import {
  DEFAULT_INTEGRATION_CONFIG,
  type IntegrationConfigMap,
  type IntegrationId,
} from "./integrations";
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

export async function fetchIngestJobStatus(
  jobId: string,
): Promise<IngestJobStatusResponse> {
  const response = await apiFetch(`${API_BASE}/api/ingest/jobs/${jobId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load ingest job (${response.status})`);
  }
  return response.json();
}

const INGEST_POLL_INTERVAL_MS = 1000;
const INGEST_POLL_TIMEOUT_MS = 5 * 60 * 1000;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function pollIngestJob(
  jobId: string,
  onStatus?: (status: IngestJobStatusResponse) => void,
): Promise<OrgChartIngestResponse> {
  const started = Date.now();

  while (true) {
    const status = await fetchIngestJobStatus(jobId);
    onStatus?.(status);

    if (status.status === "completed") {
      if (!status.result) {
        throw new Error("Ingest completed without a result payload.");
      }
      return status.result;
    }

    if (status.status === "failed") {
      throw new Error(status.error ?? "Cognee ingest job failed.");
    }

    if (Date.now() - started > INGEST_POLL_TIMEOUT_MS) {
      throw new Error("Cognee ingest timed out. Try again in a moment.");
    }

    await sleep(INGEST_POLL_INTERVAL_MS);
  }
}

export async function ingestOrgChart(
  payload: OrgChartPayload,
  options?: {
    onStatus?: (status: IngestJobStatusResponse) => void;
  },
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

  if (response.status === 202) {
    const accepted = (await response.json()) as IngestJobAcceptedResponse;
    options?.onStatus?.({
      job_id: accepted.job_id,
      status: accepted.status,
      job_type: "org_chart",
      company: payload.company,
      employees_persisted: payload.employees.length,
      components_persisted: payload.components.length,
      assignments_persisted: payload.assignments.length,
      error: null,
      result: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      completed_at: null,
    });
    return pollIngestJob(accepted.job_id, options?.onStatus);
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

export async function fetchEraEmployeeHotspots(
  employeeId: string,
): Promise<EraHotspotsResponse> {
  const response = await apiFetch(
    `${API_BASE}/api/analytics/era/${encodeURIComponent(employeeId)}/hotspots`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Failed to load ERA hotspots (${response.status})`);
  }
  return response.json();
}

export async function fetchKraFileRisk(
  componentId?: string,
): Promise<KraFileRiskResponse> {
  const params = new URLSearchParams();
  if (componentId) params.set("component_id", componentId);
  const query = params.toString();
  const response = await apiFetch(
    `${API_BASE}/api/analytics/kra/file-risk${query ? `?${query}` : ""}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Failed to load file risk matrix (${response.status})`);
  }
  return response.json();
}

export async function fetchEraEmployeeDetail(
  employeeId: string,
  options?: { limit?: number; offset?: number },
): Promise<EraEmployeeDetailResponse> {
  const params = new URLSearchParams();
  if (options?.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  if (options?.offset !== undefined) {
    params.set("offset", String(options.offset));
  }
  const query = params.toString();
  const response = await apiFetch(
    `${API_BASE}/api/analytics/era/${encodeURIComponent(employeeId)}${query ? `?${query}` : ""}`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    throw new Error(`Failed to load ERA employee detail (${response.status})`);
  }

  return response.json();
}

export async function fetchEraReviewNetwork(
  employeeId: string,
): Promise<EraReviewNetworkResponse> {
  const response = await apiFetch(
    `${API_BASE}/api/analytics/era/${encodeURIComponent(employeeId)}/review-network`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Failed to load review network (${response.status})`);
  }
  return response.json();
}

export async function fetchEraTeamRiskyChanges(
  since = "90d",
): Promise<EraTeamRiskyChangesResponse> {
  const response = await apiFetch(
    `${API_BASE}/api/analytics/team/risky-changes?since=${encodeURIComponent(since)}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Failed to load risky changes (${response.status})`);
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

type StoredIntegrationsConfig = {
  slack: {
    workspace_url: string;
    bot_token: string;
    channel_ids: string;
    validated?: boolean;
    previously_connected?: boolean;
  };
  notion: {
    integration_token: string;
    database_ids: string;
    validated?: boolean;
    previously_connected?: boolean;
  };
  github: {
    repository_url: string;
    branch_target: string;
    personal_access_token: string;
    oauth_connected: boolean;
    validated?: boolean;
    previously_connected?: boolean;
  };
  jira: {
    site_url: string;
    project_keys: string;
    api_token: string;
    account_email: string;
    validated?: boolean;
    previously_connected?: boolean;
  };
};

function mapStoredIntegrationConfig(
  stored: StoredIntegrationsConfig,
): IntegrationConfigMap {
  return {
    slack: {
      workspaceUrl: stored.slack.workspace_url ?? "",
      botToken: stored.slack.bot_token ?? "",
      channelIds: stored.slack.channel_ids ?? "",
      validated: Boolean(stored.slack.validated),
      previouslyConnected: Boolean(stored.slack.previously_connected),
    },
    notion: {
      integrationToken: stored.notion.integration_token ?? "",
      databaseIds: stored.notion.database_ids ?? "",
      validated: Boolean(stored.notion.validated),
      previouslyConnected: Boolean(stored.notion.previously_connected),
    },
    github: {
      repositoryUrl: stored.github.repository_url ?? "",
      branchTarget: stored.github.branch_target ?? "main",
      personalAccessToken: stored.github.personal_access_token ?? "",
      oauthConnected: Boolean(stored.github.oauth_connected),
      validated: Boolean(stored.github.validated),
      previouslyConnected: Boolean(stored.github.previously_connected),
    },
    jira: {
      siteUrl: stored.jira.site_url ?? "",
      projectKeys: stored.jira.project_keys ?? "",
      apiToken: stored.jira.api_token ?? "",
      accountEmail: stored.jira.account_email ?? "",
      validated: Boolean(stored.jira.validated),
      previouslyConnected: Boolean(stored.jira.previously_connected),
    },
  };
}

export async function fetchIntegrationConfig(): Promise<IntegrationConfigMap> {
  const response = await apiFetch(`${API_BASE}/api/integrations/config`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Failed to load integration config"));
  }
  const stored = (await response.json()) as StoredIntegrationsConfig;
  return mapStoredIntegrationConfig(stored);
}

export async function saveSlackIntegrationConfig(
  config: IntegrationConfigMap["slack"],
): Promise<void> {
  const response = await apiFetch(`${API_BASE}/api/integrations/slack/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      workspace_url: config.workspaceUrl,
      bot_token: config.botToken,
      channel_ids: config.channelIds,
      validated: config.validated ?? false,
      previously_connected: config.previouslyConnected ?? false,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Slack config save failed"));
  }
}

export async function saveNotionIntegrationConfig(
  config: IntegrationConfigMap["notion"],
): Promise<void> {
  const response = await apiFetch(`${API_BASE}/api/integrations/notion/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      integration_token: config.integrationToken,
      database_ids: config.databaseIds,
      validated: config.validated ?? false,
      previously_connected: config.previouslyConnected ?? false,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Notion config save failed"));
  }
}

export async function deleteIntegrationConfig(source: IntegrationId): Promise<void> {
  const response = await apiFetch(`${API_BASE}/api/integrations/${source}/config`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, `${source} disconnect failed`));
  }
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

export async function validateJiraIntegration(
  config: IntegrationConfigMap["jira"],
): Promise<string> {
  const response = await apiFetch(`${API_BASE}/api/integrations/jira/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jira_domain: config.siteUrl,
      auth_email: config.authEmail,
      api_token: config.apiToken,
      account_email: config.accountEmail,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Jira credential validation failed"));
  }
  const data = (await response.json()) as { message: string };
  return data.message;
}

export async function connectJiraIntegration(
  config: IntegrationConfigMap["jira"],
): Promise<void> {
  const response = await apiFetch(`${API_BASE}/api/integrations/jira/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jira_domain: config.siteUrl,
      auth_email: config.authEmail,
      api_token: config.apiToken,
      project_keys: config.projectKeys,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Jira connect failed"));
  }
}

export async function saveJiraIntegrationConfig(
  config: IntegrationConfigMap["jira"],
): Promise<void> {
  await connectJiraIntegration(config);
}

export async function syncIntegrationSource(
  source: "github" | "jira" | "notion" | "slack",
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
    await connectJiraIntegration(config.jira);
    return syncIntegrationSource("jira");
  }
  if (id === "notion") {
    await saveNotionIntegrationConfig(config.notion);
    return syncIntegrationSource("notion");
  }
  if (id === "slack") {
    await saveSlackIntegrationConfig(config.slack);
    return syncIntegrationSource("slack");
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
      jira_auth_email: integrationConfig?.jira.authEmail ?? null,
      jira_api_token: integrationConfig?.jira.apiToken ?? null,
      jira_account_email: integrationConfig?.jira.accountEmail ?? null,
      jira_project_keys: integrationConfig?.jira.projectKeys ?? null,
    }),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Employee master data fetch failed"));
  }
  return response.json();
}

function memberSyncRequestBody(
  sources: IntegrationId[],
  company: string,
  integrationConfig: IntegrationConfigMap,
) {
  return {
    sources,
    company,
    flat_hierarchy: false,
    slack_bot_token: integrationConfig.slack.botToken.trim() || null,
    notion_integration_token: integrationConfig.notion.integrationToken.trim() || null,
    notion_database_ids: integrationConfig.notion.databaseIds.trim() || null,
    github_repository_url: integrationConfig.github.repositoryUrl.trim() || null,
    github_personal_access_token:
      integrationConfig.github.personalAccessToken.trim() || null,
    jira_site_url: integrationConfig.jira.siteUrl.trim() || null,
    jira_auth_email: integrationConfig.jira.authEmail.trim() || null,
    jira_api_token: integrationConfig.jira.apiToken.trim() || null,
    jira_project_keys: integrationConfig.jira.projectKeys.trim() || null,
  };
}

export async function syncMemberRoster(
  sources: IntegrationId[],
  company: string,
  integrationConfig: IntegrationConfigMap,
): Promise<MemberRosterSyncResult> {
  const response = await apiFetch(`${API_BASE}/api/integrations/sync-members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      memberSyncRequestBody(sources, company, integrationConfig),
    ),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Member roster sync failed"));
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
    throw new Error(
      await parseApiError(response, "Failed to load identity reconciliation"),
    );
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

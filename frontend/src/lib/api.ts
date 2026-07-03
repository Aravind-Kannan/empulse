import type {
  DashboardMetrics,
  EmployeeOption,
  EraAnalyticsResponse,
  EraEmployeeDetailResponse,
  EraHotspotsResponse,
  EraReviewNetworkResponse,
  EraManagerRollupResponse,
  EraMitigationItem,
  EraAlertItem,
  EraAlertsResponse,
  EraReviewCadenceResponse,
  EraSettings,
  EraTeamReviewItem,
  EraTeamRiskyChangesResponse,
  GlobalSyncResult,
  HandoverResponse,
  IncidentListResult,
  IncidentStatus,
  IncidentSummary,
  IntegrationSyncJobAcceptedResponse,
  IntegrationSyncJobListResponse,
  IntegrationSyncJobStatusResponse,
  IntegrationSyncJobsAcceptedResponse,
  IntegrationSyncResult,
  InvestigationAnalysisStatus,
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
  EmployeeDeleteResponse,
} from "./types";
import {
  DEFAULT_INTEGRATION_CONFIG,
  normalizeJiraSiteUrl,
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

export async function deleteOrgEmployee(
  employeeId: string,
): Promise<EmployeeDeleteResponse> {
  const response = await apiFetch(`${API_BASE}/api/org/employees/${employeeId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Employee delete failed"));
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

export async function fetchEraAlerts(
  options?: { unacknowledged?: boolean },
): Promise<EraAlertsResponse> {
  const params = new URLSearchParams();
  if (options?.unacknowledged) {
    params.set("unacknowledged", "true");
  }
  const query = params.toString();
  const response = await apiFetch(
    `${API_BASE}/api/analytics/era/alerts${query ? `?${query}` : ""}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Failed to load ERA alerts (${response.status})`);
  }
  return response.json();
}

export async function acknowledgeEraAlert(
  alertId: number,
  body?: { acknowledged_by?: string | null },
): Promise<EraAlertItem> {
  const response = await apiFetch(
    `${API_BASE}/api/analytics/era/alerts/${alertId}/acknowledge`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to acknowledge alert (${response.status})`);
  }
  return response.json();
}

export async function fetchEraReviewCadence(): Promise<EraReviewCadenceResponse> {
  const response = await apiFetch(`${API_BASE}/api/analytics/era/review-cadence`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load ERA review cadence (${response.status})`);
  }
  return response.json();
}

export async function recordEraTeamReview(body?: {
  notes?: string | null;
  reviewer_user_id?: string | null;
}): Promise<EraTeamReviewItem> {
  const response = await apiFetch(`${API_BASE}/api/analytics/era/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!response.ok) {
    throw new Error(`Failed to record ERA review (${response.status})`);
  }
  return response.json();
}

export async function fetchEraSettings(): Promise<EraSettings> {
  const response = await apiFetch(`${API_BASE}/api/analytics/era/settings`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load ERA settings (${response.status})`);
  }
  return response.json();
}

export async function updateEraSettings(
  patch: Partial<EraSettings>,
): Promise<EraSettings> {
  const response = await apiFetch(`${API_BASE}/api/analytics/era/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!response.ok) {
    throw new Error(`Failed to update ERA settings (${response.status})`);
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

export async function patchEraEvidenceMitigation(
  evidenceId: string,
  body: {
    employee_id: string;
    mitigation_status: EraMitigationItem["mitigation_status"];
    assignee_id?: string | null;
    due_date?: string | null;
    notes?: string | null;
  },
): Promise<{
  evidence_id: string;
  employee_id: string;
  mitigation_status: string;
  updated_at: string;
}> {
  const response = await apiFetch(
    `${API_BASE}/api/analytics/era/evidence/${encodeURIComponent(evidenceId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to update mitigation (${response.status})`);
  }
  return response.json();
}

export async function fetchEraManagerRollup(
  managerId: string,
): Promise<EraManagerRollupResponse> {
  const params = new URLSearchParams({ manager_id: managerId });
  const response = await apiFetch(
    `${API_BASE}/api/analytics/era/rollup?${params.toString()}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Failed to load manager rollup (${response.status})`);
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
): Promise<IncidentListResult> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const response = await apiFetch(`${API_BASE}/api/investigation/incidents${query}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load incidents (${response.status})`);
  }
  return response.json();
}

export async function updateIncidentStatus(
  incidentId: string,
  status: IncidentStatus,
  resolutionNote?: string,
): Promise<IncidentSummary> {
  const response = await apiFetch(
    `${API_BASE}/api/investigation/incidents/${incidentId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status,
        resolution_note: resolutionNote?.trim() || undefined,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to update incident (${response.status})`);
  }
  return response.json();
}

type InvestigationStreamPayload = {
  type: string;
  content?: string;
  phase?: InvestigationAnalysisStatus["phase"];
  message?: string;
  diagnostics?: InvestigationDiagnostics;
};

async function readInvestigationSseStream(
  response: Response,
  handlers: {
    onStatus?: (status: InvestigationAnalysisStatus) => void;
    onToken?: (token: string) => void;
    onDiagnostics?: (diagnostics: InvestigationDiagnostics) => void;
  },
): Promise<void> {
  if (!response.body) {
    throw new Error("Stream body missing");
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
      const payload = JSON.parse(line.slice(6)) as InvestigationStreamPayload;
      if (payload.type === "status" && payload.phase && payload.message) {
        handlers.onStatus?.({ phase: payload.phase, message: payload.message });
      } else if (payload.type === "token" && payload.content) {
        handlers.onToken?.(payload.content);
      } else if (payload.type === "diagnostics" && payload.diagnostics) {
        handlers.onDiagnostics?.(payload.diagnostics);
      } else if (payload.type === "error" && payload.message) {
        throw new Error(payload.message);
      }
    }
  }
}

export async function streamIncidentBriefing(
  incidentId: string,
  onStatus: (status: InvestigationAnalysisStatus) => void,
  onDiagnostics: (diagnostics: InvestigationDiagnostics) => void,
): Promise<void> {
  const response = await apiFetch(
    `${API_BASE}/api/investigation/incidents/${encodeURIComponent(incidentId)}/briefing/stream`,
    {
      method: "POST",
    },
  );

  if (!response.ok) {
    throw new Error(`Incident briefing failed (${response.status})`);
  }

  await readInvestigationSseStream(response, { onStatus, onDiagnostics });
}

export async function streamInvestigationChat(
  message: string,
  incidentId: string | null,
  onToken: (token: string) => void,
  onStatus?: (status: InvestigationAnalysisStatus) => void,
): Promise<void> {
  const response = await apiFetch(`${API_BASE}/api/investigation/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, incident_id: incidentId }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat stream failed (${response.status})`);
  }

  await readInvestigationSseStream(response, { onStatus, onToken });
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

export async function fetchHandover(
  employeeId: string,
  options?: { prefillEra?: boolean },
): Promise<HandoverResponse> {
  const params = new URLSearchParams({ id: employeeId });
  if (options?.prefillEra) {
    params.set("prefill", "era");
  }
  const response = await apiFetch(
    `${API_BASE}/api/exit/handover?${params.toString()}`,
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

export async function validateGitHubIntegration(
  config: IntegrationConfigMap["github"],
): Promise<string> {
  const response = await apiFetch(`${API_BASE}/api/integrations/github/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      personal_access_token: config.personalAccessToken,
      repository_url: config.repositoryUrl,
      repository_urls: config.repositoryUrls,
      branch_target: config.branchTarget,
      branch_targets: config.branchTargets,
      sync_all_branches: config.syncAllBranches,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "GitHub validation failed"));
  }
  const data = (await response.json()) as { message: string };
  return data.message;
}

export interface GitHubDiscoveredRepo {
  full_name: string;
  html_url: string;
  default_branch: string;
  private: boolean;
  description: string | null;
}

export async function discoverGitHubRepositories(
  personalAccessToken: string,
): Promise<{ repositories: GitHubDiscoveredRepo[]; message: string }> {
  const response = await apiFetch(`${API_BASE}/api/integrations/github/discover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ personal_access_token: personalAccessToken }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "GitHub repository discovery failed"));
  }
  return response.json();
}

export async function listGitHubRepositoryBranches(
  personalAccessToken: string,
  repositoryUrl: string,
): Promise<{ default_branch: string; branches: string[] }> {
  const response = await apiFetch(`${API_BASE}/api/integrations/github/branches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      personal_access_token: personalAccessToken,
      repository_url: repositoryUrl,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "GitHub branch listing failed"));
  }
  return response.json();
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
    repository_urls: string[];
    branch_target: string;
    branch_targets: string[];
    sync_all_branches: boolean;
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
      repositoryUrls:
        (stored.github.repository_urls?.length ?? 0) > 0
          ? stored.github.repository_urls
          : stored.github.repository_url
            ? [stored.github.repository_url]
            : [],
      branchTarget: stored.github.branch_target ?? "main",
      branchTargets:
        (stored.github.branch_targets?.length ?? 0) > 0
          ? stored.github.branch_targets
          : stored.github.branch_target
            ? [stored.github.branch_target]
            : [],
      syncAllBranches: Boolean(stored.github.sync_all_branches),
      personalAccessToken: stored.github.personal_access_token ?? "",
      oauthConnected: Boolean(stored.github.oauth_connected),
      validated: Boolean(stored.github.validated),
      previouslyConnected: Boolean(stored.github.previously_connected),
    },
    jira: {
      siteUrl: stored.jira.site_url ?? "",
      authEmail: stored.jira.account_email ?? "",
      projectKeys: stored.jira.project_keys ?? "",
      apiToken: stored.jira.api_token ?? "",
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
): Promise<string> {
  const response = await apiFetch(`${API_BASE}/api/integrations/github/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repository_url: config.repositoryUrls[0] ?? config.repositoryUrl,
      repository_urls: config.repositoryUrls,
      branch_target: config.branchTargets[0] ?? config.branchTarget,
      branch_targets: config.branchTargets,
      sync_all_branches: config.syncAllBranches,
      personal_access_token: config.personalAccessToken,
      oauth_connected: config.oauthConnected,
      validated: config.validated ?? false,
      previously_connected: config.previouslyConnected ?? false,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "GitHub config save failed"));
  }
  const data = (await response.json()) as { message?: string };
  return data.message ?? "GitHub configuration saved.";
}

export interface JiraDiscoveredProject {
  key: string;
  name: string;
  project_type: string | null;
}

export async function discoverJiraProjects(
  config: IntegrationConfigMap["jira"],
): Promise<{ projects: JiraDiscoveredProject[]; message: string }> {
  const response = await apiFetch(`${API_BASE}/api/integrations/jira/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jira_domain: normalizeJiraSiteUrl(config.siteUrl),
      auth_email: config.authEmail,
      api_token: config.apiToken,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Jira project discovery failed"));
  }
  return response.json();
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
  const response = await apiFetch(`${API_BASE}/api/integrations/jira/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      site_url: normalizeJiraSiteUrl(config.siteUrl),
      project_keys: config.projectKeys,
      api_token: config.apiToken,
      account_email: config.authEmail,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Jira config save failed"));
  }
}

export async function syncIntegrationSource(
  source: "github" | "jira" | "notion" | "slack",
): Promise<IntegrationSyncJobAcceptedResponse> {
  const response = await apiFetch(`${API_BASE}/api/integrations/sync/${source}`, {
    method: "POST",
    timeoutMs: 45_000,
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, `${source} sync failed`));
  }
  return response.json();
}

export async function syncGitHubRepository(
  repositoryUrl: string,
): Promise<IntegrationSyncJobAcceptedResponse> {
  const response = await apiFetch(`${API_BASE}/api/integrations/github/repos/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repository_url: repositoryUrl }),
    timeoutMs: 45_000,
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "GitHub repository sync failed"));
  }
  return response.json();
}

export async function syncAllIntegrations(): Promise<IntegrationSyncJobsAcceptedResponse> {
  const response = await apiFetch(`${API_BASE}/api/integrations/sync`, {
    method: "POST",
    timeoutMs: 45_000,
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Global sync failed"));
  }
  return response.json();
}

export async function fetchIntegrationSyncJobs(options?: {
  activeOnly?: boolean;
  limit?: number;
}): Promise<IntegrationSyncJobListResponse> {
  const params = new URLSearchParams();
  if (options?.activeOnly) params.set("active_only", "true");
  if (options?.limit) params.set("limit", String(options.limit));
  const query = params.toString();
  const response = await apiFetch(
    `${API_BASE}/api/integrations/sync/jobs${query ? `?${query}` : ""}`,
    { cache: "no-store", timeoutMs: 15_000 },
  );
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Failed to load sync jobs"));
  }
  return response.json();
}

export async function fetchIntegrationSyncJobStatus(
  jobId: string,
): Promise<IntegrationSyncJobStatusResponse> {
  const response = await apiFetch(`${API_BASE}/api/integrations/sync/jobs/${jobId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Failed to load sync job"));
  }
  return response.json();
}

export async function cancelIntegrationSyncJob(
  jobId: string,
): Promise<IntegrationSyncJobStatusResponse> {
  const response = await apiFetch(
    `${API_BASE}/api/integrations/sync/jobs/${jobId}/cancel`,
    { method: "POST", timeoutMs: 15_000 },
  );
  if (!response.ok) {
    throw new Error(await parseApiError(response, "Failed to cancel sync job"));
  }
  return response.json();
}

export async function saveAndSyncIntegration(
  id: IntegrationId,
  config: IntegrationConfigMap,
): Promise<IntegrationSyncJobAcceptedResponse | null> {
  if (id === "github") {
    await saveGitHubIntegrationConfig(config.github);
    return syncIntegrationSource("github");
  }
  if (id === "jira") {
    await saveJiraIntegrationConfig(config.jira);
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
      github_repository_url:
        integrationConfig?.github.repositoryUrls[0] ??
        integrationConfig?.github.repositoryUrl ??
        null,
      github_personal_access_token:
        integrationConfig?.github.personalAccessToken ?? null,
      jira_site_url: integrationConfig?.jira.siteUrl ?? null,
      jira_auth_email: integrationConfig?.jira.authEmail ?? null,
      jira_api_token: integrationConfig?.jira.apiToken ?? null,
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
    github_repository_url:
      integrationConfig.github.repositoryUrls[0]?.trim() ||
      integrationConfig.github.repositoryUrl.trim() ||
      null,
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

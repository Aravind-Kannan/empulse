export interface Employee {
  id: string;
  name: string;
  role: string;
  email: string;
  tenure_years: number;
  manager_id: string | null;
  team_name?: string | null;
}

export interface Component {
  id: string;
  name: string;
  description: string;
  open_tasks_count: number;
  unresolved_incidents: number;
}

export interface Assignment {
  employee_id: string;
  component_id: string;
  codebase_share_pct: number;
}

export interface OrgChartPayload {
  company: string;
  employees: Employee[];
  components: Component[];
  assignments: Assignment[];
}

export interface SignUpData {
  name: string;
  email: string;
  company: string;
}

export interface MasterDataEmployee {
  id: string;
  name: string;
  email: string;
  role: string;
  manager_id: string | null;
  manager_email: string | null;
  tenure_years: number;
  source_providers: string[];
}

export interface EmployeeMasterDataResponse {
  company: string;
  employees: MasterDataEmployee[];
  sources_queried: string[];
  roles_discovered: string[];
  records_merged: number;
  hierarchy_mode?: "flat" | "structured";
}

export interface BulkCsvRow {
  id: string;
  name: string;
  email: string;
  dynamic_role: string;
  team_name: string;
  reports_to_email_or_id: string;
}

export interface BulkDiffEntry {
  kind: "added" | "removed" | "modified";
  employee_id: string;
  name: string;
  changes: string[];
}

export interface BulkUploadResponse {
  valid: boolean;
  errors: string[];
  diff: BulkDiffEntry[];
  merged_org: OrgChartPayload | null;
  sync_result: OrgChartIngestResponse | null;
}

export interface RoleHistoryRecord {
  id: number;
  employee_id: string;
  old_role: string;
  new_role: string;
  changed_at: string;
}

export interface EmployeeUpdateResponse {
  employee_id: string;
  role_changed: boolean;
  role_history_entry: RoleHistoryRecord | null;
  cognee_dataset: string;
  graph_nodes_created: number;
  graph_edges_created: number;
}

export interface OrgChartIngestResponse {
  company: string;
  employees_persisted: number;
  components_persisted: number;
  assignments_persisted: number;
  cognee_dataset: string;
  graph_nodes_created: number;
  graph_edges_created: number;
}

export type IngestJobStatus = "queued" | "running" | "completed" | "failed";

export interface IngestJobAcceptedResponse {
  job_id: string;
  status: IngestJobStatus;
  poll_url: string;
  message: string;
}

export interface IngestJobStatusResponse {
  job_id: string;
  status: IngestJobStatus;
  job_type: string;
  company: string;
  employees_persisted: number;
  components_persisted: number;
  assignments_persisted: number;
  error: string | null;
  result: OrgChartIngestResponse | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface EraEmployeeMetrics {
  employee_id: string;
  name: string;
  role: string;
  email: string;
  unresolved_issues: number;
  open_tasks: number;
  undocumented_solved_incidents: number;
  codebase_share_pct: number;
  risk_factor_score: number;
  risk_level: "low" | "medium" | "high";
  jira_backlog_boost?: number;
}

export interface EraAnalyticsResponse {
  employees: EraEmployeeMetrics[];
}

export interface KraNode {
  id: string;
  label: string;
  type: "engineer" | "component";
  role?: string | null;
  description?: string | null;
  documentation_sources: string[];
  is_spof: boolean;
  github_verified_spof?: boolean;
}

export interface KraLink {
  source: string;
  target: string;
  relationship: string;
  codebase_share_pct?: number | null;
}

export interface KraAnalyticsResponse {
  nodes: KraNode[];
  links: KraLink[];
}

export interface KraBackupAssignmentResponse {
  component_id: string;
  employee_id: string;
  codebase_share_pct: number;
  is_spof_resolved: boolean;
}

export type IncidentStatus =
  | "Open"
  | "Investigating"
  | "Waiting for Input"
  | "Resolved"
  | "Closed";

export interface IncidentSummary {
  id: string;
  title: string;
  status: IncidentStatus;
  system_scope: string;
  jira_id: string;
  updated_at: string;
}

export interface SmeRecommendation {
  employee_id: string;
  name: string;
  role: string;
  compatibility_score: number;
  status: "online" | "away" | "offline";
}

export interface InvestigationReference {
  id: string;
  type: "slack" | "notion" | "postmortem";
  title: string;
  url: string;
  snippet: string;
}

export interface InvestigationDiagnostics {
  probable_root_cause: string;
  confidence_score: number;
  workaround: string;
  smes: SmeRecommendation[];
  references: InvestigationReference[];
  graph_hops: string[];
}

export interface EmployeeOption {
  id: string;
  name: string;
  role: string;
}

export interface HandoverResponse {
  employee_id: string;
  employee_name: string;
  markdown: string;
  filename: string;
}

export interface DashboardMetrics {
  average_attrition_rate: number;
  average_tenure_years: number;
  open_incident_count: number;
  active_spof_count: number;
  employee_count: number;
}

export interface DigestSettings {
  enabled: boolean;
  cron: string;
}

export interface IntegrationSyncResult {
  source: string;
  cognee_dataset: string;
  documents_ingested: number;
  graph_nodes_created: number;
  graph_edges_created: number;
  narrative_preview: string;
}

export interface GlobalSyncResult {
  results: IntegrationSyncResult[];
  total_nodes_created: number;
  total_edges_created: number;
}

export interface SimulationGraphNode {
  id: string;
  label: string;
  type: string;
}

export interface SimulationGraphEdge {
  source: string;
  target: string;
  relationship: string;
}

export interface SimulationLogEntry {
  type: "log";
  message: string;
  status: string;
}

export interface SimulationGraphResult {
  nodes: SimulationGraphNode[];
  edges: SimulationGraphEdge[];
  cognee_dataset: string;
  documents_generated: number;
  notion_pages_written: number;
  success: boolean;
}

export type SimulationStreamEvent =
  | SimulationLogEntry
  | ({ type: "result" } & SimulationGraphResult);

export interface NotionSimulationRequest {
  notion_integration_token?: string;
  notion_database_id?: string;
  ollama_model?: string;
}

export type IdentityProvider = "github" | "jira" | "slack" | "notion";

export interface ProviderMember {
  id: string;
  label: string;
  email: string | null;
}

export interface EmployeeIdentityMapping {
  employee_id: string;
  provider: IdentityProvider;
  provider_username_or_id: string;
}

export interface EmployeeIdentityRow {
  employee_id: string;
  name: string;
  email: string;
  role: string;
  mappings: Partial<Record<IdentityProvider, string | null>>;
}

export interface IdentityReconciliationResponse {
  employees: EmployeeIdentityRow[];
  provider_members: Partial<Record<IdentityProvider, ProviderMember[]>>;
  connected_providers: IdentityProvider[];
}

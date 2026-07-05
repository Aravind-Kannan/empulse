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
  tags?: string;
  criticality?: "tier1_revenue" | "tier2_core" | "tier3_support";
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

export interface MemberRosterSyncResult {
  sources: string[];
  employees_imported: number;
  employees_added: number;
  employees_updated: number;
  employees_persisted: number;
  hierarchy_mode: string;
  cognee_dataset: string;
  graph_nodes_created: number;
  graph_edges_created: number;
  source_errors?: string[];
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

export interface EmployeeDeleteResponse {
  employee_id: string;
  direct_reports_reparented: number;
  cognee_dataset: string;
  graph_nodes_created: number;
  graph_edges_created: number;
}

export interface ComponentUpdateResponse {
  component_id: string;
  cognee_dataset: string;
  graph_nodes_created: number;
  graph_edges_created: number;
}

export interface ComponentDeleteResponse {
  component_id: string;
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

export type EraDimensionKey =
  | "knowledge"
  | "operational"
  | "documentation"
  | "structural"
  | "burnout";

export type IdentityCoverageLevel = "confirmed" | "high" | "medium" | "missing";

export type IntegrationId = "github" | "jira" | "slack" | "notion";

export interface EraDimensions {
  knowledge: number;
  operational: number;
  documentation: number;
  structural: number;
  burnout: number;
  partial?: Partial<Record<EraDimensionKey, boolean>>;
}

export interface EraEvidenceSource {
  provider: string;
  label: string;
  url: string | null;
}

export interface EraEvidenceItem {
  id: string;
  dimension: EraDimensionKey;
  severity: "high" | "medium" | "low";
  title: string;
  description: string;
  impact_points: number;
  sources: EraEvidenceSource[];
  synthetic?: boolean;
  mitigation_status?: "open" | "in_progress" | "done" | "dismissed";
  suggested_mitigation?: string | null;
  mitigation_assignee_id?: string | null;
  mitigation_due_date?: string | null;
  mitigation_notes?: string | null;
}

export interface EraMitigationItem {
  evidence_id: string;
  title: string;
  priority: string;
  link?: string | null;
  suggested_mitigation?: string | null;
  mitigation_status: "open" | "in_progress" | "done" | "dismissed";
  mitigation_assignee_id?: string | null;
  mitigation_due_date?: string | null;
  mitigation_notes?: string | null;
}

export interface EraAlertItem {
  id: number;
  rule_id: string;
  severity: string;
  title: string;
  description: string;
  employee_id?: string | null;
  component_id?: string | null;
  evidence_id?: string | null;
  created_at: string;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
}

export interface EraAlertsResponse {
  computed_at: string;
  alerts: EraAlertItem[];
  unacknowledged_count: number;
}

export interface EraOpenP1IssueItem {
  issue_key: string;
  summary: string;
  priority: string;
  status: string;
  project_key: string;
  issue_type: string;
  issue_url?: string | null;
  updated_at?: string | null;
  assignee_employee_id?: string | null;
  assignee_name?: string | null;
  assignee_unmapped: boolean;
  component_id?: string | null;
  component_name?: string | null;
}

export interface EraOpenP1IssuesResponse {
  computed_at: string;
  jira_synced: boolean;
  total_count: number;
  issues: EraOpenP1IssueItem[];
  filters_note: string;
}

export interface EraTeamReviewItem {
  id: number;
  reviewed_at: string;
  reviewer_user_id?: string | null;
  notes?: string | null;
  snapshot_avg_risk: number;
  delta_since_last?: number | null;
}

export interface EraTeamReviewsResponse {
  computed_at: string;
  reviews: EraTeamReviewItem[];
}

export interface EraReviewCadenceResponse {
  computed_at: string;
  last_reviewed_at?: string | null;
  days_since_last_review?: number | null;
  review_overdue: boolean;
  review_cadence_days: number;
  snapshot_avg_risk?: number | null;
}

export interface EraSettings {
  slack_webhook_url: string;
  slack_webhook_enabled: boolean;
  unmapped_threshold: number;
  review_cadence_days: number;
}

export interface EraAffectedComponent {
  id: string;
  name: string;
  spof: boolean;
  criticality: "tier1_revenue" | "tier2_core" | "tier3_support";
  ownership_pct?: number | null;
}

export interface EraRecoveryEstimate {
  min: number;
  max: number;
}

export interface EraUnmappedActivityCount {
  provider: IntegrationId;
  count: number;
}

export interface EraTeamSummary {
  avg_risk_score: number;
  avg_risk_trend_7d?: number | null;
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
  spof_component_count: number;
  open_p1_count: number;
  undocumented_incident_count: number;
  top_risk_driver: EraDimensionKey;
  estimated_recovery_weeks: EraRecoveryEstimate;
  data_health_pct: number;
  org_health_score?: number;
  orphan_file_count?: number;
  orphan_delta_90d?: number;
  org_health_caution?: boolean;
  critical_hotspot_count?: number;
  last_risk_review_at?: string | null;
  unacknowledged_alert_count?: number;
}

export interface EraDimensionFactorSummary {
  key: string;
  label: string;
  value: number;
  impact_points: number;
  provider: string;
  synthetic: boolean;
}

export interface EraDimensionSummary {
  score: number;
  partial: boolean;
  headline: string;
  top_factors: EraDimensionFactorSummary[];
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
  dimensions?: EraDimensions | null;
  dimension_summaries?: Partial<Record<EraDimensionKey, EraDimensionSummary>>;
  evidence?: EraEvidenceItem[];
  evidence_total_count?: number;
  affected_components?: EraAffectedComponent[];
  identity_coverage?: Partial<Record<IntegrationId, IdentityCoverageLevel>>;
  data_completeness_pct?: number;
  recovery_estimate_weeks?: EraRecoveryEstimate;
  departure_watchlist?: boolean;
  trend_7d?: number | null;
  excluded?: boolean;
  exclusion_reason?: string | null;
  identity_warning?: boolean;
}

export interface EraRiskHistoryPoint {
  snapshot_date: string;
  risk_factor_score: number;
  org_health_score?: number | null;
  orphan_file_count?: number | null;
  dimensions?: EraDimensions | null;
}

export interface EraManagerRollupReport {
  employee_id: string;
  name: string;
  role: string;
  risk_factor_score: number;
  risk_level: string;
  trend_7d?: number | null;
}

export interface EraManagerRollupResponse {
  computed_at: string;
  manager_id: string;
  manager_name: string;
  team_avg_risk: number;
  high_risk_report_count: number;
  manager_exposure_bonus: number;
  reports: EraManagerRollupReport[];
}

export interface EraAnalyticsResponse {
  computed_at: string;
  demo_mode: boolean;
  warnings: string[];
  team_summary: EraTeamSummary;
  employees: EraEmployeeMetrics[];
  unmapped_activity: EraUnmappedActivityCount[];
  sync_freshness: Partial<Record<IntegrationId, string | null>>;
  team_risk_history_30d?: EraRiskHistoryPoint[];
  team_evidence?: EraEvidenceItem[];
}

export interface EraEmployeeDetailResponse {
  computed_at: string;
  employee: EraEmployeeMetrics;
  evidence: EraEvidenceItem[];
  evidence_total_count: number;
  limit: number;
  offset: number;
  backup_candidates: EraBackupCandidate[];
  warnings: string[];
  blast_radius_narrative?: string | null;
  identity_mappings?: Partial<Record<IntegrationId, EraIdentityMapping>>;
  risk_history_30d?: EraRiskHistoryPoint[];
  mitigations?: EraMitigationItem[];
  open_mitigations_count?: number;
}

export interface EraIdentityMapping {
  level: IdentityCoverageLevel;
  display_label?: string | null;
}

export interface EraBackupCandidate {
  employee_id: string;
  name: string;
  component_id: string;
  component_name: string;
  ownership_pct: number;
  review_count: number;
  recent_commits: number;
  score: number;
  label: "ramping" | "secondary" | string;
}

export interface EraReviewNetworkEdge {
  reviewer_employee_id: string;
  author_employee_id: string;
  review_count: number;
  reviewer_login: string;
  author_login: string;
}

export interface EraReviewNetworkMetrics {
  employee_id: string;
  review_concentration_pct: number;
  reviews_given_count: number;
  reviews_received_count: number;
  sole_reviewer_count: number;
  unique_reviewers_on_prs: number;
  isolation_score: number;
  backup_review_score: number;
  recent_pr_count: number;
  no_backup_pr_urls: string[];
  top_reviewer_employee_id?: string | null;
  top_reviewer_login?: string | null;
}

export interface EraReviewNetworkResponse {
  computed_at: string;
  employee_id: string;
  window_days: number;
  metrics: EraReviewNetworkMetrics | null;
  incoming_reviewers: EraReviewNetworkEdge[];
}

export interface EraRiskyChangeItem {
  pr_number: number;
  pr_url: string;
  author_employee_id?: string | null;
  author_login: string;
  author_name?: string | null;
  severity: string;
  rule: string;
  title: string;
  description: string;
  merged_at?: string | null;
  impact_points: number;
}

export interface EraTeamRiskyChangesResponse {
  computed_at: string;
  window_days: number;
  items: EraRiskyChangeItem[];
}


export interface KraSpofReason {
  kind: "single_owner" | "dominant_owner" | "low_bus_factor";
  title: string;
  detail: string;
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
  bus_factor?: number | null;
  spof_reasons?: KraSpofReason[];
}

export interface KraLink {
  source: string;
  target: string;
  relationship: string;
  codebase_share_pct?: number | null;
  ownership_source?: "github" | "org_chart" | null;
}

export interface KraAnalyticsResponse {
  nodes: KraNode[];
  links: KraLink[];
}

export interface KraMetricCoverage {
  github: "confirmed" | "partial" | "missing";
  notion: "confirmed" | "partial" | "missing";
  is_partial: boolean;
}

export interface CriticalSpofComponent {
  component_id: string;
  component_name: string;
  bus_factor: number | null;
  owner_count: number;
  owner_names: string[];
  github_verified: boolean;
  criticality: string;
}

export interface CriticalSpofResult {
  count: number;
  components: CriticalSpofComponent[];
  data_completeness: KraMetricCoverage;
}

export interface DocumentationGapComponent {
  component_id: string;
  component_name: string;
  gap_reason: "missing" | "stale";
  last_doc_edit: string | null;
  notion_sources: string[];
  notion_page_urls: string[];
  days_since_activity: number | null;
}

export interface DocumentationCoveredComponent {
  component_id: string;
  component_name: string;
  last_doc_edit: string | null;
  notion_sources: string[];
  notion_page_urls: string[];
}

export interface DocumentationCoverageResult {
  coverage_pct: number | null;
  active_component_count: number;
  covered_count: number;
  covered_components: DocumentationCoveredComponent[];
  gap_components: DocumentationGapComponent[];
  data_completeness: KraMetricCoverage;
}

export interface KraSummaryResponse {
  critical_spof: CriticalSpofResult;
  documentation_coverage: DocumentationCoverageResult;
}

export type FileRiskQuadrant =
  | "critical"
  | "stable_niche"
  | "active_shared"
  | "healthy";

export interface FileRiskItem {
  component_id: string;
  component_name: string;
  repo_path: string;
  file_path: string;
  churn_score: number;
  contributor_count: number;
  bus_factor: number;
  quadrant: FileRiskQuadrant;
  primary_owner_employee_id?: string | null;
  primary_owner_name?: string | null;
  primary_owner_doa_pct?: number | null;
  github_url?: string | null;
  computed_at: string;
}

export interface KraFileRiskResponse {
  component_id: string | null;
  component_name: string | null;
  team_size?: number | null;
  files: FileRiskItem[];
  quadrant_counts: Record<string, number>;
  cross_training_priority: FileRiskItem[];
}

export interface EraHotspotsResponse {
  employee_id: string;
  critical_count: number;
  files: FileRiskItem[];
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
  source: "jira" | "slack";
  priority?: string | null;
  channel_name?: string | null;
}

export interface IncidentListResult {
  incidents: IncidentSummary[];
  suggestions: string[];
  sources_connected: Record<string, boolean>;
  warnings: string[];
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
  type: "slack" | "notion" | "postmortem" | "jira";
  title: string;
  url: string;
  snippet: string;
}

export interface InvestigationGraphHop {
  from_node: string;
  edge: string;
  to: string;
}

export interface InvestigationAssignmentRecord {
  employee_id: string;
  employee_name: string;
  component_id: string;
  component_name: string;
  codebase_share_pct: number;
}

export interface InvestigationBaseMetadata {
  incident: IncidentSummary;
  assignments: InvestigationAssignmentRecord[];
  scope_owners: SmeRecommendation[];
}

export interface InvestigationDiagnostics {
  probable_root_cause: string;
  confidence_score: number;
  workaround: string;
  workaround_available?: boolean;
  smes: SmeRecommendation[];
  references: InvestigationReference[];
  slack_threads: InvestigationReference[];
  jira_tickets: InvestigationReference[];
  notion_pages: InvestigationReference[];
  graph_hops?: InvestigationGraphHop[];
}

export interface CachedInvestigationData {
  chatHistory: Array<{
    id: string;
    role: "user" | "assistant";
    content: string;
  }>;
  diagnostics: InvestigationDiagnostics | null;
  baseMetadata: InvestigationBaseMetadata | null;
}

export type InvestigationAnalysisPhase =
  | "searching"
  | "matching"
  | "summarizing";

export interface InvestigationAnalysisStatus {
  phase: InvestigationAnalysisPhase;
  message: string;
}

export interface IncidentInvestigationCacheEntry {
  diagnostics: InvestigationDiagnostics;
  chatMessages: Array<{
    id: string;
    role: "user" | "assistant";
    content: string;
  }>;
  incidentUpdatedAt: string;
  cachedAt: number;
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
  /** API alias mirroring markdown for asset-pack consumers */
  markdown_content?: string;
  filename: string;
  era_risk_score?: number | null;
  era_sections_included?: string[];
  era_computed_at?: string | null;
  prefill_from_era?: boolean;
}

export interface HandoverSlackSendResponse {
  employee_id: string;
  employee_name: string;
  slack_user_id: string;
  channel_id: string;
  filename: string;
  file_id?: string | null;
  message: string;
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
  items_fetched?: number;
  items_new?: number;
  items_updated?: number;
  items_skipped?: number;
  skipped_preview?: string[];
  already_synced_note?: string;
  repository_url?: string;
  branch?: string;
  ref?: string;
  files_discovered?: number;
  files_mapped_to_components?: number;
  branches_synced?: string[];
  branches_total?: number;
}

export interface IntegrationSyncProgressStats {
  branches_total?: number;
  branches_completed?: number;
  current_branch?: string;
  files_total?: number;
  files_completed?: number;
}

export type IntegrationSyncJobStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type IntegrationSyncPhase =
  | "fetching"
  | "building_graph"
  | "cognifying"
  | "finalizing";

export interface IntegrationSyncJobAcceptedResponse {
  job_id: string;
  source: string;
  status: IntegrationSyncJobStatus;
  poll_url: string;
  message: string;
  job_kind?: string;
  repository_url?: string | null;
}

export interface IntegrationSyncJobsAcceptedResponse {
  jobs: IntegrationSyncJobAcceptedResponse[];
  message: string;
}

export interface IntegrationSyncJobStatusResponse {
  job_id: string;
  source: string;
  status: IntegrationSyncJobStatus;
  phase: IntegrationSyncPhase | null;
  progress_message: string | null;
  progress_stats?: IntegrationSyncProgressStats | null;
  error: string | null;
  result: IntegrationSyncResult | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  duration_seconds?: number | null;
  job_kind?: string;
  repository_url?: string | null;
}

export interface IntegrationSyncJobListResponse {
  jobs: IntegrationSyncJobStatusResponse[];
}

export interface CogneeDatasetResetRequest {
  memory_only?: boolean;
  clear_ledger?: boolean;
  clear_telemetry?: boolean;
}

export interface CogneeDatasetResetResponse {
  dataset: string;
  mode: string;
  memory_only: boolean;
  forget_summary: Record<string, unknown>;
  graph_purge: Record<string, unknown>;
  ledger_rows_removed: number;
  telemetry_cleared: boolean;
  message: string;
}

export interface GlobalSyncResult {
  results: IntegrationSyncResult[];
  total_nodes_created: number;
  total_edges_created: number;
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
  provider_display_label?: string | null;
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
  provider_warnings?: Partial<Record<IdentityProvider, string>>;
}

export interface ProviderMembersBundleResponse {
  provider_members: Partial<Record<IdentityProvider, ProviderMember[]>>;
  provider_warnings?: Partial<Record<IdentityProvider, string>>;
}

export interface ProviderIdentitySyncResult {
  provider: IdentityProvider;
  members_fetched: number;
  mappings_created: number;
  warning: string | null;
}

export interface IdentitySyncRequest {
  providers?: IdentityProvider[];
  import_roster?: boolean;
  company?: string | null;
}

export interface IdentitySyncResponse {
  providers: ProviderIdentitySyncResult[];
  total_mappings_created: number;
  roster: MemberRosterSyncResult | null;
}

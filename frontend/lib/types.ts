export type Repository = {
  id: number;
  name: string;
  owner: { username?: string; login?: string; full_name?: string };
  full_name?: string;
  private?: boolean;
  permissions?: { admin?: boolean; push?: boolean; pull?: boolean };
  is_active?: boolean;
};

export type Repo = Repository;

export type PublicConfig = {
  gitea_url: string;
  bot_username?: string | null;
  debug: boolean;
  oauth_enabled?: boolean;
};

export type Actor = {
  id: number;
  external_provider: string;
  external_username: string;
  display_name: string | null;
  email: string | null;
  role: string;
  permissions: string[];
  is_active: boolean;
  last_login_at: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type RepositoryFeature = {
  id: number;
  repository_id: number;
  scenario: string;
  enabled: boolean;
  auto_on_open: boolean;
  manual_command_enabled: boolean;
};

export type ProviderCredential = {
  id: number;
  scope_type: string;
  scope_key: string;
  name: string;
  provider: string;
  api_url: string | null;
  has_api_key: boolean;
  is_active: boolean;
  last_used_at: string | null;
};

export type RepositoryConfiguration = {
  id: number;
  repository_id: number;
  scenario: 'review' | 'issue' | string;
  engine: string;
  model: string | null;
  credential_id: number | null;
  credential_name: string | null;
  api_url: string | null;
  has_api_key: boolean;
  wire_api: string | null;
  temperature: number | null;
  max_tokens: number | null;
  custom_prompt: string | null;
  focus: string[];
  features: string[];
  is_active: boolean;
};

export type AnalysisAnnotation = {
  id: number;
  analysis_run_id: number;
  annotation_type: string;
  file_path: string | null;
  new_line: number | null;
  old_line: number | null;
  severity: string | null;
  body: string;
  suggestion: string | null;
  created_at: string | null;
};

export type AnalysisRunSummary = {
  id: number;
  kind: 'review' | 'issue' | string;
  repository_id: number;
  repo_full_name: string | null;
  external_number: number;
  external_title: string | null;
  external_author: string | null;
  status: string;
  trigger_type: string;
  effective_engine: string | null;
  effective_model: string | null;
  overall_success: boolean | null;
  overall_severity: string | null;
  summary_markdown: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
};

export type AnalysisRunDetail = AnalysisRunSummary & {
  result_payload: Record<string, unknown>;
  analysis_payload: Record<string, unknown>;
  annotations?: AnalysisAnnotation[];
};

export type ProviderRunSummary = {
  id: number;
  analysis_run_id: number | null;
  repository_id: number | null;
  provider: string;
  provider_session_id: string;
  scenario: string;
  status: string;
  model: string | null;
  turns: number;
  tool_calls_count: number;
  input_tokens: number;
  output_tokens: number;
  cache_creation_input_tokens: number;
  cache_read_input_tokens: number;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
  repo_full_name: string | null;
};

export type ProviderRunDetail = ProviderRunSummary & {
  messages: unknown[];
};

export type UsageEvent = {
  id: number;
  analysis_run_id: number | null;
  repository_id: number;
  actor_id: number | null;
  event_date: string;
  provider: string | null;
  input_tokens: number;
  output_tokens: number;
  cache_creation_input_tokens: number;
  cache_read_input_tokens: number;
  gitea_api_calls: number;
  provider_api_calls: number;
  clone_operations: number;
};

export type UsageSummary = {
  total_input_tokens: number;
  total_output_tokens: number;
  total_gitea_calls: number;
  total_claude_calls?: number;
  total_provider_calls: number;
  total_clones?: number;
  total_clone_operations: number;
  record_count: number;
  run_count: number;
};

export type UsageResponse = {
  summary: UsageSummary;
  events: UsageEvent[];
};

export type AuditEvent = {
  id: number;
  actor_id: number | null;
  actor_type?: string;
  action: string;
  resource_type: string;
  resource_id: number | null;
  repository_id?: number | null;
  status: string;
  error_message?: string | null;
  created_at: string;
};

export type AppSetting = {
  id: number;
  key: string;
  category: string;
  value: unknown;
  description: string | null;
  updated_by_actor_id: number | null;
  updated_at: string | null;
};

export type ProviderInfo = {
  name: string;
  label: string;
};

export type ProvidersResponse = {
  providers: ProviderInfo[];
  default: string;
};

export type ChangelogEntry = {
  version: string;
  date: string;
  changes: string[];
};

export type ChangelogResponse = {
  version: string;
  history: ChangelogEntry[];
};

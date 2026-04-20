export type Repo = {
  id: number;
  name: string;
  owner: { username?: string; login?: string; full_name?: string };
  full_name?: string;
  private?: boolean;
  permissions?: { admin?: boolean; push?: boolean; pull?: boolean };
  is_active?: boolean;
};

export type PublicConfig = {
  gitea_url: string;
  bot_username?: string | null;
  debug: boolean;
  oauth_enabled?: boolean;
};

export type RepoProviderConfig = {
  configured: boolean;
  api_url?: string | null;
  engine?: string | null;
  model?: string | null;
  has_api_key: boolean;
  inherit_global: boolean;
  has_global_config: boolean;
  global_api_url?: string | null;
  global_has_api_key: boolean;
  global_engine?: string | null;
  global_model?: string | null;
};
export type RepoClaudeConfig = RepoProviderConfig;

export type GlobalProviderConfig = {
  configured: boolean;
  api_url?: string | null;
  engine?: string | null;
  model?: string | null;
  has_api_key: boolean;
};
export type GlobalClaudeConfig = GlobalProviderConfig;

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

export type UsageSummary = {
  total_input_tokens: number;
  total_output_tokens: number;
  total_gitea_calls: number;
  total_claude_calls: number;
  total_provider_calls: number;
  total_clones: number;
  record_count: number;
};

export type IssueAnalysisItem = {
  id: number;
  repository_id: number;
  repo_full_name: string | null;
  issue_number: number;
  issue_title: string | null;
  issue_author: string | null;
  issue_state: string | null;
  trigger_type: string;
  engine: string | null;
  model: string | null;
  config_source: string | null;
  overall_severity: string | null;
  overall_success: boolean | null;
  error_message: string | null;
  related_issue_count: number;
  solution_count: number;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  cache_creation_input_tokens: number;
  cache_read_input_tokens: number;
  total_tokens: number;
};

export type RelatedIssue = {
  number: number;
  title: string;
  state: string;
  url: string;
  similarity_reason: string;
  suggested_reference: string;
};

export type SolutionSuggestion = {
  title: string;
  summary: string;
  steps: string[];
};

export type IssueAnalysisDetail = IssueAnalysisItem & {
  source_comment_id: number | null;
  bot_comment_id: number | null;
  summary_markdown: string | null;
  analysis_payload: Record<string, unknown>;
  related_issues: RelatedIssue[];
  solution_suggestions: SolutionSuggestion[];
  related_files: string[];
  next_actions: string[];
  fallback_mode?: 'tool' | 'text_json' | 'raw_text';
  focus_areas?: string[];
};

export type IssueConfigPayload = {
  inherit_global: boolean;
  has_global_config: boolean;
  configured: boolean;
  engine: string;
  model: string | null;
  api_url: string | null;
  has_api_key: boolean;
  temperature: number | null;
  max_tokens: number | null;
  custom_prompt: string | null;
  default_focus: string[];
  global_engine: string | null;
  global_model: string | null;
  global_api_url: string | null;
  global_has_api_key: boolean;
};

export type IssueConfigUpdateRequest = {
  engine?: string;
  model?: string | null;
  api_url?: string | null;
  api_key?: string | null;
  wire_api?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  custom_prompt?: string | null;
  default_focus?: string[];
  inherit_global?: boolean;
};

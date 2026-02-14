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

export type UsageSummary = {
  total_input_tokens: number;
  total_output_tokens: number;
  total_gitea_calls: number;
  total_claude_calls: number;
  total_provider_calls: number;
  total_clones: number;
  record_count: number;
};

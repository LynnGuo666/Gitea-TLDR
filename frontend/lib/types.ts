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
  anthropic_base_url?: string | null; // deprecated
  provider_api_base_url?: string | null;
  has_auth_token: boolean;
  inherit_global: boolean;
  has_global_config: boolean;
  global_base_url?: string | null;
  global_has_auth_token: boolean;
};
export type RepoClaudeConfig = RepoProviderConfig;

export type GlobalProviderConfig = {
  configured: boolean;
  anthropic_base_url?: string | null; // deprecated
  provider_api_base_url?: string | null;
  has_auth_token: boolean;
};
export type GlobalClaudeConfig = GlobalProviderConfig;

export type UsageSummary = {
  total_input_tokens: number;
  total_output_tokens: number;
  total_gitea_calls: number;
  total_claude_calls: number;
  total_provider_calls: number;
  total_clones: number;
  record_count: number;
};

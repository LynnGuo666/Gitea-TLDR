export type Repo = {
  id: number;
  name: string;
  owner: { username?: string; login?: string; full_name?: string };
  full_name?: string;
  private?: boolean;
};

export type PublicConfig = {
  gitea_url: string;
  bot_username?: string | null;
  debug: boolean;
};

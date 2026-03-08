export type PlatformType = "sub2api" | "cliproxy";

export interface AccountItem {
  platform: PlatformType;
  account_id: number | null;
  delete_name: string | null;
  name: string;
  channel: string;
  status: string;
  created_at: string;
  raw: Record<string, unknown>;
  _key?: string;
}

export interface AccountsQuery {
  keyword?: string;
  channel?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

export interface AccountsResponse {
  total: number;
  all_total: number;
  page: number;
  page_size: number;
  accounts: AccountItem[];
  channel_options: string[];
  status_options: string[];
}

export interface LoginResponse extends AccountsResponse {
  session_id: string;
  platform: PlatformType;
}

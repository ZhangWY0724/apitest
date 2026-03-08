import type { PlatformType } from "./types";

export interface LoginFormValues {
  platform: PlatformType;
  base_url: string;
  email?: string;
  password: string;
}

export interface FailedAccountItem {
  key: string;
  name: string;
  account_id?: number;
  delete_name?: string;
  reason: string;
}

export interface DuplicateCandidateItem {
  key: string;
  name: string;
  account_id?: number;
  delete_name?: string;
  channel?: string;
  status?: string;
  created_at?: string;
}

export interface HealthResultItem {
  state: "checking" | "success" | "failed";
  reason: string;
  checkedAt: string;
}

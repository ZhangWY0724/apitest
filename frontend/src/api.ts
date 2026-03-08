import type { AccountsQuery, AccountsResponse, LoginResponse, PlatformType } from "./types";

// 通过 Vite 环境变量注入，本地开发默认 127.0.0.1:8000
const BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      ...init,
    });
  } catch (error) {
    throw new Error(`网络异常或跨域阻止: ${(error as Error).message}`);
  }

  let data: any;
  try {
    data = await res.json();
  } catch {
    data = {};
  }

  if (!res.ok) {
    throw new Error(data?.detail || `请求失败 (${res.status})`);
  }
  return data as T;
}

function buildQueryString(query?: AccountsQuery): string {
  if (!query) {
    return "";
  }

  const searchParams = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
}

export function login(payload: {
  platform: PlatformType;
  base_url: string;
  email?: string;
  password: string;
}) {
  return request<LoginResponse>("/api/session/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchAccounts(sessionId: string, query?: AccountsQuery) {
  return request<AccountsResponse>(`/api/session/${sessionId}/accounts${buildQueryString(query)}`);
}

export function detectDuplicates(sessionId: string) {
  return request<{
    group_count: number;
    delete_count: number;
    duplicate_keys: string[];
    candidates: Array<{
      name: string;
      account_id?: number | null;
      delete_name?: string | null;
      channel?: string;
      status?: string;
      created_at?: string;
    }>;
  }>(
    `/api/session/${sessionId}/detect-duplicates`,
    { method: "POST" }
  );
}

export function deleteDuplicates(sessionId: string, keys: string[]) {
  return request<{ selected: number; success: number; failed: number }>(`/api/session/${sessionId}/delete-duplicates`, {
    method: "POST",
    body: JSON.stringify({ keys }),
  });
}

export function batchHealthCheck(
  sessionId: string,
  model_id: string,
  items?: Array<{ account_id?: number; delete_name?: string }>
) {
  return request<{ total: number; success: number; failed: number; failed_accounts: Array<Record<string, unknown>> }>(
    `/api/session/${sessionId}/batch-health-check`,
    { method: "POST", body: JSON.stringify({ model_id, items: items ?? [] }) }
  );
}

export function testAccount(sessionId: string, payload: { account_id?: number; delete_name?: string; model_id?: string }) {
  return request<{ success: boolean; reason: string }>(`/api/session/${sessionId}/account-test`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteAccount(sessionId: string, payload: { account_id?: number; delete_name?: string }) {
  return request<{ success: boolean }>(`/api/session/${sessionId}/account-delete`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function bulkDeleteAccounts(
  sessionId: string,
  items: Array<{ account_id?: number; delete_name?: string }>
) {
  return request<{ total: number; success: number; failed: number }>(`/api/session/${sessionId}/bulk-delete`, {
    method: "POST",
    body: JSON.stringify({ items }),
  });
}

export function logout(sessionId: string) {
  return request<{ success: boolean }>(`/api/session/${sessionId}`, {
    method: "DELETE",
  });
}

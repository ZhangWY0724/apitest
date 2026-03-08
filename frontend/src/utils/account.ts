import type { AccountItem, PlatformType } from "../types";

export function getAccountKey(record: AccountItem): string {
  return record._key || `${record.platform}:::${record.account_id ?? "n"}:::${record.delete_name ?? record.name}`;
}

export function getAccountIdentity(
  platform: PlatformType,
  item: { account_id?: number | null; delete_name?: string | null; name?: string }
): string {
  return `${platform}:::${item.account_id ?? "n"}:::${item.delete_name ?? item.name ?? ""}`;
}

export function withAccountKeys(accounts: AccountItem[]): AccountItem[] {
  return accounts;
}

export function formatDateTime(value?: string): string {
  if (!value) {
    return "-";
  }

  const datetime = new Date(value);
  if (Number.isNaN(datetime.getTime())) {
    return value;
  }

  const year = datetime.getFullYear();
  const month = String(datetime.getMonth() + 1).padStart(2, "0");
  const day = String(datetime.getDate()).padStart(2, "0");
  const hour = String(datetime.getHours()).padStart(2, "0");
  const minute = String(datetime.getMinutes()).padStart(2, "0");
  const second = String(datetime.getSeconds()).padStart(2, "0");

  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

export function nowText(): string {
  return new Date().toLocaleString("zh-CN", { hour12: false });
}

export function toAccountPayload(item: { account_id?: number | null; delete_name?: string | null }) {
  return {
    account_id: item.account_id ?? undefined,
    delete_name: item.delete_name ?? undefined,
  };
}

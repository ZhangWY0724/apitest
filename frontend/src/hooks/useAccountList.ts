import { useEffect, useRef, useState } from "react";

import { fetchAccounts } from "../api";
import type { AccountItem, AccountsResponse } from "../types";
import { withAccountKeys } from "../utils/account";

interface UseAccountListParams {
  sessionId: string;
  keyword: string;
  channelFilter: string;
  statusFilter: string;
  pageCurrent: number;
  pageSize: number;
  onBeforeLoad?: () => void;
  onAfterLoad?: () => void;
  onError?: (message: string) => void;
  onResetSelection?: () => void;
}

export function useAccountList({
  sessionId,
  keyword,
  channelFilter,
  statusFilter,
  pageCurrent,
  pageSize,
  onBeforeLoad,
  onAfterLoad,
  onError,
  onResetSelection,
}: UseAccountListParams) {
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [accountTotal, setAccountTotal] = useState(0);
  const [allAccountTotal, setAllAccountTotal] = useState(0);
  const [channelOptions, setChannelOptions] = useState<string[]>([]);
  const [statusOptions, setStatusOptions] = useState<string[]>([]);
  const skipNextEffectRef = useRef(false);

  function syncAccountList(payload: AccountsResponse) {
    setAccounts(withAccountKeys(payload.accounts));
    setAccountTotal(payload.total);
    setAllAccountTotal(payload.all_total);
    setChannelOptions(payload.channel_options);
    setStatusOptions(payload.status_options);
    onResetSelection?.();
    return payload;
  }

  async function loadAccountPage(currentSessionId: string) {
    const result = await fetchAccounts(currentSessionId, {
      keyword,
      channel: channelFilter,
      status: statusFilter,
      page: pageCurrent,
      page_size: pageSize,
    });
    return syncAccountList(result);
  }

  function hydrate(payload: AccountsResponse) {
    skipNextEffectRef.current = true;
    return syncAccountList(payload);
  }

  useEffect(() => {
    if (!sessionId) {
      return;
    }
    if (skipNextEffectRef.current) {
      skipNextEffectRef.current = false;
      return;
    }

    let cancelled = false;

    async function run() {
      onBeforeLoad?.();
      try {
        const result = await fetchAccounts(sessionId, {
          keyword,
          channel: channelFilter,
          status: statusFilter,
          page: pageCurrent,
          page_size: pageSize,
        });
        if (!cancelled) {
          syncAccountList(result);
        }
      } catch (error) {
        if (!cancelled) {
          onError?.((error as Error).message);
        }
      } finally {
        if (!cancelled) {
          onAfterLoad?.();
        }
      }
    }

    void run();

    return () => {
      cancelled = true;
    };
  }, [sessionId, keyword, channelFilter, statusFilter, pageCurrent, pageSize]);

  return {
    accounts,
    accountTotal,
    allAccountTotal,
    channelOptions,
    statusOptions,
    hydrate,
    loadAccountPage,
  };
}

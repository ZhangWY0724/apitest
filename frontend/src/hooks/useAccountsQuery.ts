import { useState } from "react";

export function useAccountsQuery(initialPageSize = 20) {
  const [keyword, setKeywordState] = useState("");
  const [channelFilter, setChannelFilterState] = useState("");
  const [statusFilter, setStatusFilterState] = useState("");
  const [pageCurrent, setPageCurrent] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);

  function setKeyword(value: string) {
    setKeywordState(value);
    setPageCurrent(1);
  }

  function setChannelFilter(value: string) {
    setChannelFilterState(value);
    setPageCurrent(1);
  }

  function setStatusFilter(value: string) {
    setStatusFilterState(value);
    setPageCurrent(1);
  }

  function setPagination(nextPageCurrent: number, nextPageSize: number) {
    setPageCurrent(nextPageCurrent);
    setPageSize(nextPageSize);
  }

  function syncPagination(nextPageCurrent: number, nextPageSize: number) {
    setPageCurrent(nextPageCurrent);
    setPageSize(nextPageSize);
  }

  return {
    keyword,
    channelFilter,
    statusFilter,
    pageCurrent,
    pageSize,
    setKeyword,
    setChannelFilter,
    setStatusFilter,
    setPagination,
    syncPagination,
  };
}

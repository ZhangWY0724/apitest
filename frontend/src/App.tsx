import { useState } from "react";
import type { Key } from "react";

import { Form, Modal, message } from "antd";

import {
  batchHealthCheck,
  bulkDeleteAccounts,
  deleteAccount,
  deleteDuplicates,
  detectDuplicates,
  login,
  logout,
  testAccount,
} from "./api";
import { ActionToolbar } from "./components/ActionToolbar";
import { AccountsTable } from "./components/AccountsTable";
import { BulkDeleteModal } from "./components/BulkDeleteModal";
import { DuplicateAccountsModal } from "./components/DuplicateAccountsModal";
import { FailedAccountsModal } from "./components/FailedAccountsModal";
import { LoginPanel } from "./components/LoginPanel";
import { useAccountList } from "./hooks/useAccountList";
import { useAccountsQuery } from "./hooks/useAccountsQuery";
import type { AccountItem, PlatformType } from "./types";
import type { DuplicateCandidateItem, FailedAccountItem, HealthResultItem, LoginFormValues } from "./view-types";
import { getAccountIdentity, getAccountKey, nowText, toAccountPayload } from "./utils/account";

export default function App() {
  const [form] = Form.useForm<LoginFormValues>();
  const [authLoading, setAuthLoading] = useState(false);
  const [listLoading, setListLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [platform, setPlatform] = useState<PlatformType>("sub2api");
  const [failedAccounts, setFailedAccounts] = useState<FailedAccountItem[]>([]);
  const [failedModalOpen, setFailedModalOpen] = useState(false);
  const [selectedFailedKeys, setSelectedFailedKeys] = useState<Key[]>([]);
  const [duplicateModalOpen, setDuplicateModalOpen] = useState(false);
  const [duplicateCandidates, setDuplicateCandidates] = useState<DuplicateCandidateItem[]>([]);
  const [selectedDuplicateKeys, setSelectedDuplicateKeys] = useState<string[]>([]);
  const [checkModelId, setCheckModelId] = useState("gpt-5.4");
  const [healthResults, setHealthResults] = useState<Record<string, HealthResultItem>>({});
  const [batchRunning, setBatchRunning] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [selectedAccountKeys, setSelectedAccountKeys] = useState<Key[]>([]);
  const [selectedAccountRows, setSelectedAccountRows] = useState<AccountItem[]>([]);
  const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false);
  const [bulkDeleteTargets, setBulkDeleteTargets] = useState<AccountItem[]>([]);

  const isLoggedIn = Boolean(sessionId);
  const {
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
  } = useAccountsQuery();

  function resetSelection() {
    setSelectedAccountKeys([]);
    setSelectedAccountRows([]);
  }

  const { accounts, accountTotal, allAccountTotal, channelOptions, statusOptions, hydrate, loadAccountPage } = useAccountList({
    sessionId,
    keyword,
    channelFilter,
    statusFilter,
    pageCurrent,
    pageSize,
    onBeforeLoad: () => setListLoading(true),
    onAfterLoad: () => setListLoading(false),
    onError: (errorMessage) => message.error(errorMessage),
    onResetSelection: resetSelection,
  });

  function buildFailedItems(failedList: Array<Record<string, unknown>>) {
    const failedByIdentity = new Map<string, FailedAccountItem>();

    failedList.forEach((failedItem, index) => {
      const identity = getAccountIdentity(platform, {
        account_id: typeof failedItem.account_id === "number" ? failedItem.account_id : null,
        delete_name: typeof failedItem.delete_name === "string" ? failedItem.delete_name : null,
        name: typeof failedItem.name === "string" ? failedItem.name : "",
      });

      if (!failedByIdentity.has(identity)) {
        failedByIdentity.set(identity, {
          key: `failed-${identity}-${index}`,
          name: String(failedItem.name ?? "unknown"),
          account_id: typeof failedItem.account_id === "number" ? failedItem.account_id : undefined,
          delete_name: typeof failedItem.delete_name === "string" ? failedItem.delete_name : undefined,
          reason: String(failedItem.reason ?? "未知异常"),
        });
      }
    });

    return Array.from(failedByIdentity.values());
  }

  function markAccountsChecking(targets: AccountItem[]) {
    setHealthResults((previous) => {
      const next = { ...previous };
      targets.forEach((account) => {
        next[getAccountKey(account)] = {
          state: "checking",
          reason: "检测中",
          checkedAt: nowText(),
        };
      });
      return next;
    });
  }

  function markBatchResult(targets: AccountItem[], failedList: FailedAccountItem[]) {
    const failedByIdentity = new Map(
      failedList.map((item) => [
        getAccountIdentity(platform, {
          account_id: item.account_id ?? null,
          delete_name: item.delete_name ?? null,
          name: item.name,
        }),
        item,
      ])
    );

    setHealthResults((previous) => {
      const next = { ...previous };
      targets.forEach((account) => {
        const failedItem = failedByIdentity.get(getAccountIdentity(platform, account));
        next[getAccountKey(account)] = failedItem
          ? { state: "failed", reason: failedItem.reason, checkedAt: nowText() }
          : { state: "success", reason: "验证成功", checkedAt: nowText() };
      });
      return next;
    });
  }

  function markBatchInterrupted(targets: AccountItem[]) {
    setHealthResults((previous) => {
      const next = { ...previous };
      targets.forEach((account) => {
        const key = getAccountKey(account);
        if (next[key]?.state === "checking") {
          next[key] = { state: "failed", reason: "测活被中断", checkedAt: nowText() };
        }
      });
      return next;
    });
  }

  function getSelectedAccounts() {
    if (!selectedAccountKeys.length) {
      return [] as AccountItem[];
    }

    const keySet = new Set(selectedAccountKeys.map(String));
    const matchedAccounts = accounts.filter((account) => keySet.has(getAccountKey(account)));
    return matchedAccounts.length > 0 ? matchedAccounts : selectedAccountRows;
  }

  async function onLogin(values: LoginFormValues) {
    setAuthLoading(true);
    setLoginError("");

    try {
      if (sessionId) {
        try {
          await logout(sessionId);
        } catch {
        }
      }

      const result = await login(values);
      setSessionId(result.session_id);
      setPlatform(result.platform);
      setHealthResults({});
      syncPagination(result.page, result.page_size);
      hydrate(result);
      message.success(`登录成功，拉取账号 ${result.all_total} 条`);
    } catch (error) {
      const errorMessage = (error as Error).message;
      setLoginError(errorMessage);
      message.error(errorMessage);
    } finally {
      setAuthLoading(false);
    }
  }

  async function reloadAccounts() {
    if (!sessionId) {
      return;
    }

    setListLoading(true);
    try {
      const result = await loadAccountPage(sessionId);
      message.success(`刷新完成，共 ${result.total} 条`);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setListLoading(false);
    }
  }

  async function handleDetectDuplicate() {
    if (!sessionId) {
      message.warning("请先登录");
      return;
    }

    setActionLoading(true);
    try {
      const result = await detectDuplicates(sessionId);
      if (!result.group_count) {
        message.success("未发现重复账号");
        return;
      }

      setSelectedDuplicateKeys(result.duplicate_keys);
      setDuplicateCandidates(
        (result.candidates || []).map((item, index) => ({
          key: `${item.name}-${String(item.account_id ?? "n")}-${String(item.delete_name ?? "d")}-${index}`,
          name: item.name,
          account_id: typeof item.account_id === "number" ? item.account_id : undefined,
          delete_name: typeof item.delete_name === "string" ? item.delete_name : undefined,
          channel: item.channel,
          status: item.status,
          created_at: item.created_at,
        }))
      );
      setDuplicateModalOpen(true);
      message.info(`发现 ${result.group_count} 组重复账号，待删除 ${result.delete_count} 条`);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setActionLoading(false);
    }
  }

  async function runBatchCheck(targets: AccountItem[], items?: Array<{ account_id?: number; delete_name?: string }>) {
    if (!sessionId || batchRunning) {
      return;
    }
    if (!targets.length) {
      message.info("没有可测活账号");
      return;
    }

    setBatchRunning(true);
    setFailedAccounts([]);
    setSelectedFailedKeys([]);
    markAccountsChecking(targets);

    try {
      const result = await batchHealthCheck(sessionId, checkModelId || "gpt-5.4", items);
      const failedList = buildFailedItems(result.failed_accounts ?? []);
      markBatchResult(targets, failedList);
      message.info(`批量测活完成: 总 ${result.total} / 成功 ${result.success} / 异常 ${result.failed}`);

      if (failedList.length > 0) {
        setFailedAccounts(failedList);
        setSelectedFailedKeys(failedList.map((item) => item.key));
        setFailedModalOpen(true);
      }
    } catch (error) {
      message.error(`批量测活失败: ${(error as Error).message}`);
      markBatchInterrupted(targets);
    } finally {
      setBatchRunning(false);
    }
  }

  async function handleBatchCheckAll() {
    if (!sessionId) {
      message.warning("请先登录");
      return;
    }

    await runBatchCheck(accounts);
  }

  async function handleBatchCheckSelected() {
    if (!sessionId) {
      message.warning("请先登录");
      return;
    }

    const targets = getSelectedAccounts();
    if (!targets.length) {
      message.warning("未找到匹配的选中账号，请重新勾选后再试");
      return;
    }

    await runBatchCheck(targets, targets.map(toAccountPayload));
  }

  function handleBulkDeleteSelected() {
    if (!sessionId || selectedAccountKeys.length === 0) {
      return;
    }

    const targets = getSelectedAccounts();
    if (!targets.length) {
      message.warning("未找到匹配的选中账号，请重新勾选后再试");
      return;
    }

    setBulkDeleteTargets(targets);
    setBulkDeleteModalOpen(true);
  }

  async function confirmBulkDeleteSelected() {
    if (!sessionId || !bulkDeleteTargets.length) {
      return;
    }

    setActionLoading(true);
    try {
      const result = await bulkDeleteAccounts(sessionId, bulkDeleteTargets.map(toAccountPayload));
      message.success(`批量删除完成: 总 ${result.total} / 成功 ${result.success} / 失败 ${result.failed}`);
      setBulkDeleteModalOpen(false);
      setBulkDeleteTargets([]);
      resetSelection();
      await loadAccountPage(sessionId);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDeleteDuplicatesBySelection() {
    if (!sessionId || !selectedDuplicateKeys.length) {
      return;
    }

    setActionLoading(true);
    try {
      const result = await deleteDuplicates(sessionId, selectedDuplicateKeys);
      message.success(`重复账号删除完成，成功 ${result.success}，失败 ${result.failed}`);
      setDuplicateModalOpen(false);
      setDuplicateCandidates([]);
      setSelectedDuplicateKeys([]);
      await loadAccountPage(sessionId);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleBulkDeleteFailed() {
    if (!sessionId || !selectedFailedKeys.length) {
      return;
    }

    setActionLoading(true);
    try {
      const selectedItems = failedAccounts.filter((item) => selectedFailedKeys.includes(item.key));
      const result = await bulkDeleteAccounts(sessionId, selectedItems.map(toAccountPayload));
      message.success(`批量删除完成: 总 ${result.total} / 成功 ${result.success} / 失败 ${result.failed}`);
      setFailedModalOpen(false);
      setFailedAccounts([]);
      setSelectedFailedKeys([]);
      await loadAccountPage(sessionId);
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleTestOne(record: AccountItem) {
    if (!sessionId) {
      return;
    }

    setHealthResults((previous) => ({
      ...previous,
      [getAccountKey(record)]: {
        state: "checking",
        reason: "检测中",
        checkedAt: nowText(),
      },
    }));

    try {
      const result = await testAccount(sessionId, {
        ...toAccountPayload(record),
        model_id: checkModelId || "gpt-5.4",
      });

      if (result.success) {
        message.success(`账号 ${record.name} 测活成功`);
      } else {
        message.warning(`账号 ${record.name} 异常: ${result.reason}`);
      }

      setHealthResults((previous) => ({
        ...previous,
        [getAccountKey(record)]: {
          state: result.success ? "success" : "failed",
          reason: result.reason,
          checkedAt: nowText(),
        },
      }));
    } catch (error) {
      const errorMessage = (error as Error).message;
      message.error(errorMessage);
      setHealthResults((previous) => ({
        ...previous,
        [getAccountKey(record)]: {
          state: "failed",
          reason: errorMessage,
          checkedAt: nowText(),
        },
      }));
    }
  }

  function handleDeleteOne(record: AccountItem) {
    if (!sessionId) {
      return;
    }

    Modal.confirm({
      title: `确认删除账号：${record.name}？`,
      okText: "确认删除",
      cancelText: "取消",
      okButtonProps: { danger: true },
      onOk: async () => {
        setActionLoading(true);
        try {
          await deleteAccount(sessionId, toAccountPayload(record));
          message.success("删除成功");
          await loadAccountPage(sessionId);
        } catch (error) {
          message.error((error as Error).message);
        } finally {
          setActionLoading(false);
        }
      },
    });
  }

  return (
    <div className="page">
      <div className="layout">
        <LoginPanel
          form={form}
          loading={authLoading}
          loginError={loginError}
          isLoggedIn={isLoggedIn}
          sessionId={sessionId}
          platform={platform}
          onSubmit={onLogin}
          onPlatformChange={(nextPlatform) => {
            setLoginError("");
            setPlatform(nextPlatform);
          }}
        />

        <div className="right-area">
          <ActionToolbar
            checkModelId={checkModelId}
            onCheckModelIdChange={setCheckModelId}
            reloadLoading={listLoading}
            duplicateLoading={actionLoading}
            batchRunning={batchRunning}
            isLoggedIn={isLoggedIn}
            platform={platform}
            accountsCount={allAccountTotal}
            selectedCount={selectedAccountKeys.length}
            failedCount={failedAccounts.length}
            onReload={reloadAccounts}
            onDetectDuplicates={handleDetectDuplicate}
            onBatchCheckAll={handleBatchCheckAll}
            onBatchCheckSelected={handleBatchCheckSelected}
            onBulkDeleteSelected={handleBulkDeleteSelected}
            onOpenFailedModal={() => setFailedModalOpen(true)}
          />

          <AccountsTable
            accounts={accounts}
            total={accountTotal}
            loading={listLoading}
            batchRunning={batchRunning}
            keyword={keyword}
            onKeywordChange={setKeyword}
            channelFilter={channelFilter}
            onChannelFilterChange={setChannelFilter}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            channelOptions={channelOptions}
            statusOptions={statusOptions}
            pageCurrent={pageCurrent}
            pageSize={pageSize}
            onPageChange={setPagination}
            selectedAccountKeys={selectedAccountKeys}
            onSelectionChange={(keys, rows) => {
              setSelectedAccountKeys(keys);
              setSelectedAccountRows(rows);
            }}
            healthResults={healthResults}
            onTestOne={handleTestOne}
            onDeleteOne={handleDeleteOne}
          />
        </div>
      </div>

      <BulkDeleteModal
        open={bulkDeleteModalOpen}
        loading={actionLoading}
        count={bulkDeleteTargets.length}
        onCancel={() => {
          setBulkDeleteModalOpen(false);
          setBulkDeleteTargets([]);
        }}
        onConfirm={confirmBulkDeleteSelected}
      />

      <FailedAccountsModal
        open={failedModalOpen}
        loading={actionLoading}
        failedAccounts={failedAccounts}
        selectedKeys={selectedFailedKeys}
        onSelectionChange={setSelectedFailedKeys}
        onCancel={() => setFailedModalOpen(false)}
        onConfirm={handleBulkDeleteFailed}
      />

      <DuplicateAccountsModal
        open={duplicateModalOpen}
        loading={actionLoading}
        selectedDuplicateKeys={selectedDuplicateKeys}
        duplicateCandidates={duplicateCandidates}
        onSelectionChange={setSelectedDuplicateKeys}
        onCancel={() => setDuplicateModalOpen(false)}
        onConfirm={handleDeleteDuplicatesBySelection}
      />
    </div>
  );
}

import { Button, Input, Space, Typography } from "antd";

import type { PlatformType } from "../types";

interface ActionToolbarProps {
  checkModelId: string;
  onCheckModelIdChange: (value: string) => void;
  reloadLoading: boolean;
  duplicateLoading: boolean;
  batchRunning: boolean;
  isLoggedIn: boolean;
  platform: PlatformType;
  accountsCount: number;
  selectedCount: number;
  failedCount: number;
  onReload: () => void;
  onDetectDuplicates: () => void;
  onBatchCheckAll: () => void;
  onBatchCheckSelected: () => void;
  onBulkDeleteSelected: () => void;
  onOpenFailedModal: () => void;
}

export function ActionToolbar({
  checkModelId,
  onCheckModelIdChange,
  reloadLoading,
  duplicateLoading,
  batchRunning,
  isLoggedIn,
  platform,
  accountsCount,
  selectedCount,
  failedCount,
  onReload,
  onDetectDuplicates,
  onBatchCheckAll,
  onBatchCheckSelected,
  onBulkDeleteSelected,
  onOpenFailedModal,
}: ActionToolbarProps) {
  return (
    <section className="right-top">
      <h2 className="panel-title">操作区</h2>
      <Space wrap style={{ marginBottom: 12 }}>
        <Space.Compact>
          <Button disabled>测活模型</Button>
          <Input
            value={checkModelId}
            onChange={(event) => onCheckModelIdChange(event.target.value)}
            placeholder="批量测活模型 ID"
            style={{ width: 180 }}
            disabled={!isLoggedIn || platform !== "sub2api"}
          />
        </Space.Compact>
        <Button type="primary" onClick={onReload} loading={reloadLoading} disabled={!isLoggedIn}>
          刷新列表
        </Button>
        <Button onClick={onDetectDuplicates} loading={duplicateLoading} disabled={!isLoggedIn}>
          检测重复并清理
        </Button>
        <Button onClick={onBatchCheckAll} loading={batchRunning} disabled={!isLoggedIn || batchRunning}>
          批量测活（全部）
        </Button>
        <Button
          type="primary"
          ghost
          onClick={onBatchCheckSelected}
          loading={batchRunning}
          disabled={!isLoggedIn || batchRunning || selectedCount === 0}
        >
          测活选中（{selectedCount}）
        </Button>
        <Button danger onClick={onBulkDeleteSelected} disabled={!isLoggedIn || batchRunning || selectedCount === 0}>
          删除选中（{selectedCount}）
        </Button>
        <Button danger disabled={!isLoggedIn || failedCount === 0} onClick={onOpenFailedModal}>
          删除异常账号
        </Button>
      </Space>

      <Typography.Paragraph style={{ marginTop: 12, color: "#5e6a85" }}>
        已登录平台: {isLoggedIn ? platform : "-"}，账号数: {accountsCount}
      </Typography.Paragraph>
      {batchRunning && (
        <Typography.Paragraph style={{ marginTop: -8, color: "#5e6a85" }}>
          批量测活执行中，请稍候…
        </Typography.Paragraph>
      )}
    </section>
  );
}

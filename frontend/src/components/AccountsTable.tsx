import type { Key } from "react";

import { Button, Input, Select, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { AccountItem } from "../types";
import type { HealthResultItem } from "../view-types";
import { formatDateTime, getAccountKey } from "../utils/account";

interface AccountsTableProps {
  accounts: AccountItem[];
  total: number;
  loading: boolean;
  batchRunning: boolean;
  keyword: string;
  onKeywordChange: (value: string) => void;
  channelFilter: string;
  onChannelFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  channelOptions: string[];
  statusOptions: string[];
  pageCurrent: number;
  pageSize: number;
  onPageChange: (pageCurrent: number, pageSize: number) => void;
  selectedAccountKeys: Key[];
  onSelectionChange: (keys: Key[], rows: AccountItem[]) => void;
  healthResults: Record<string, HealthResultItem>;
  onTestOne: (record: AccountItem) => void;
  onDeleteOne: (record: AccountItem) => void;
}

export function AccountsTable({
  accounts,
  total,
  loading,
  batchRunning,
  keyword,
  onKeywordChange,
  channelFilter,
  onChannelFilterChange,
  statusFilter,
  onStatusFilterChange,
  channelOptions,
  statusOptions,
  pageCurrent,
  pageSize,
  onPageChange,
  selectedAccountKeys,
  onSelectionChange,
  healthResults,
  onTestOne,
  onDeleteOne,
}: AccountsTableProps) {
  const columns: ColumnsType<AccountItem> = [
    {
      title: "账号名称",
      dataIndex: "name",
      key: "name",
      width: 240,
    },
    {
      title: "渠道",
      dataIndex: "channel",
      key: "channel",
      width: 180,
      render: (value: string) => <Tag>{value || "-"}</Tag>,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 140,
      render: (value: string) => value || "-",
    },
    {
      title: "测活结果",
      key: "health_result",
      width: 140,
      render: (_, record) => {
        const result = healthResults[getAccountKey(record)];
        if (!result) {
          return <Typography.Text type="secondary">未测活</Typography.Text>;
        }
        if (result.state === "checking") {
          return <Tag color="processing">检测中</Tag>;
        }
        return <Tag color={result.state === "success" ? "success" : "error"}>{result.state === "success" ? "正常" : "异常"}</Tag>;
      },
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 220,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: "操作",
      key: "actions",
      width: 220,
      render: (_, record) => {
        const rowChecking = healthResults[getAccountKey(record)]?.state === "checking";
        return (
          <Space>
            <Button size="small" loading={rowChecking} disabled={batchRunning || rowChecking} onClick={() => onTestOne(record)}>
              测活
            </Button>
            <Button size="small" danger disabled={batchRunning} onClick={() => onDeleteOne(record)}>
              删除
            </Button>
          </Space>
        );
      },
    },
  ];

  return (
    <section className="right-bottom">
      <h2 className="panel-title">账号列表</h2>
      <Space wrap style={{ marginBottom: 12 }}>
        <Input
          placeholder="关键字筛选（name/channel/status）"
          value={keyword}
          onChange={(event) => onKeywordChange(event.target.value)}
          style={{ width: 280 }}
        />
        <Select
          placeholder="渠道"
          allowClear
          style={{ width: 160 }}
          value={channelFilter || undefined}
          onChange={(value) => onChannelFilterChange(value || "")}
          options={channelOptions.map((item) => ({ label: item, value: item }))}
        />
        <Select
          placeholder="状态"
          allowClear
          style={{ width: 160 }}
          value={statusFilter || undefined}
          onChange={(value) => onStatusFilterChange(value || "")}
          options={statusOptions.map((item) => ({ label: item, value: item }))}
        />
      </Space>

      <Table<AccountItem>
        rowKey={getAccountKey}
        columns={columns}
        dataSource={accounts}
        loading={loading && !batchRunning}
        rowSelection={{
          selectedRowKeys: selectedAccountKeys,
          onChange: onSelectionChange,
        }}
        pagination={{
          current: pageCurrent,
          pageSize,
          showSizeChanger: true,
          pageSizeOptions: [20, 50, 100],
          total,
          showTotal: (itemsTotal) => `共 ${itemsTotal} 条`,
          onChange: onPageChange,
        }}
        scroll={{ x: 900 }}
      />
    </section>
  );
}

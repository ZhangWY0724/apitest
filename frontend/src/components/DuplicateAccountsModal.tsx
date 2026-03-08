import { Modal, Select, Table, Typography } from "antd";

import type { DuplicateCandidateItem } from "../view-types";

interface DuplicateAccountsModalProps {
  open: boolean;
  loading: boolean;
  selectedDuplicateKeys: string[];
  duplicateCandidates: DuplicateCandidateItem[];
  onSelectionChange: (values: string[]) => void;
  onCancel: () => void;
  onConfirm: () => void;
}

export function DuplicateAccountsModal({
  open,
  loading,
  selectedDuplicateKeys,
  duplicateCandidates,
  onSelectionChange,
  onCancel,
  onConfirm,
}: DuplicateAccountsModalProps) {
  const duplicateGroups = Array.from(new Set(duplicateCandidates.map((item) => item.name)));

  return (
    <Modal
      title="重复账号清理预览"
      open={open}
      onCancel={onCancel}
      onOk={onConfirm}
      okText="删除选中分组"
      cancelText="关闭"
      okButtonProps={{ danger: true, disabled: selectedDuplicateKeys.length === 0, loading }}
    >
      <Typography.Paragraph>选择要清理的重复分组（按名称分组）：</Typography.Paragraph>
      <Select
        mode="multiple"
        style={{ width: "100%", marginBottom: 12 }}
        placeholder="选择重复分组"
        value={selectedDuplicateKeys}
        onChange={onSelectionChange}
        options={duplicateGroups.map((name) => ({ label: name, value: name }))}
      />

      <Table<DuplicateCandidateItem>
        size="small"
        rowKey="key"
        dataSource={duplicateCandidates.filter((item) => selectedDuplicateKeys.includes(item.name))}
        pagination={{ pageSize: 6, showSizeChanger: false }}
        columns={[
          { title: "账号名称", dataIndex: "name", key: "name" },
          { title: "渠道", dataIndex: "channel", key: "channel", render: (value: string) => value || "-" },
          { title: "状态", dataIndex: "status", key: "status", render: (value: string) => value || "-" },
          { title: "创建时间", dataIndex: "created_at", key: "created_at", render: (value: string) => value || "-" },
        ]}
      />
    </Modal>
  );
}

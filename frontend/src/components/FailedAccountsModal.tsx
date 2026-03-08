import type { Key } from "react";

import { Modal, Table } from "antd";

import type { FailedAccountItem } from "../view-types";

interface FailedAccountsModalProps {
  open: boolean;
  loading: boolean;
  failedAccounts: FailedAccountItem[];
  selectedKeys: Key[];
  onSelectionChange: (keys: Key[]) => void;
  onCancel: () => void;
  onConfirm: () => void;
}

export function FailedAccountsModal({
  open,
  loading,
  failedAccounts,
  selectedKeys,
  onSelectionChange,
  onCancel,
  onConfirm,
}: FailedAccountsModalProps) {
  return (
    <Modal
      title="异常账号处理"
      open={open}
      onCancel={onCancel}
      onOk={onConfirm}
      okText="删除选中"
      cancelText="关闭"
      okButtonProps={{ danger: true, disabled: selectedKeys.length === 0, loading }}
    >
      <Table<FailedAccountItem>
        size="small"
        rowKey="key"
        dataSource={failedAccounts}
        pagination={false}
        rowSelection={{
          selectedRowKeys: selectedKeys,
          onChange: (keys) => onSelectionChange(keys),
        }}
        columns={[
          { title: "账号名称", dataIndex: "name", key: "name" },
          { title: "异常原因", dataIndex: "reason", key: "reason" },
        ]}
      />
    </Modal>
  );
}

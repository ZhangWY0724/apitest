import { Modal, Typography } from "antd";

interface BulkDeleteModalProps {
  open: boolean;
  loading: boolean;
  count: number;
  onCancel: () => void;
  onConfirm: () => void;
}

export function BulkDeleteModal({ open, loading, count, onCancel, onConfirm }: BulkDeleteModalProps) {
  return (
    <Modal
      title="批量删除确认"
      open={open}
      onCancel={onCancel}
      onOk={onConfirm}
      okText="确认删除"
      cancelText="取消"
      okButtonProps={{ danger: true, loading }}
    >
      <Typography.Paragraph>确认删除选中的 {count} 个账号？此操作不可撤销。</Typography.Paragraph>
    </Modal>
  );
}

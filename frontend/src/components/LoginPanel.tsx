import { Button, Form, Input, Radio, Typography } from "antd";
import type { FormInstance } from "antd/es/form";

import type { PlatformType } from "../types";
import type { LoginFormValues } from "../view-types";

interface LoginPanelProps {
  form: FormInstance<LoginFormValues>;
  loading: boolean;
  loginError: string;
  isLoggedIn: boolean;
  sessionId: string;
  platform: PlatformType;
  onSubmit: (values: LoginFormValues) => void;
  onPlatformChange: (platform: PlatformType) => void;
}

export function LoginPanel({
  form,
  loading,
  loginError,
  isLoggedIn,
  sessionId,
  platform,
  onSubmit,
  onPlatformChange,
}: LoginPanelProps) {
  return (
    <section className="left-panel">
      <h2 className="panel-title">登录</h2>
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          platform: "sub2api",
          base_url: "",
          email: "",
          password: "",
        }}
        onFinish={onSubmit}
        onValuesChange={(changed) => {
          if (changed.platform) {
            onPlatformChange(changed.platform as PlatformType);
          }
        }}
      >
        <Form.Item label="平台" name="platform" rules={[{ required: true }]}>
          <Radio.Group optionType="button" buttonStyle="solid">
            <Radio.Button value="sub2api">Sub2API</Radio.Button>
            <Radio.Button value="cliproxy">CLIProxy</Radio.Button>
          </Radio.Group>
        </Form.Item>

        <Form.Item label="Base URL" name="base_url" rules={[{ required: true, message: "请输入 URL" }]}>
          <Input placeholder="例如: http://127.0.0.1:8080" />
        </Form.Item>

        {platform === "sub2api" && (
          <Form.Item label="邮箱" name="email" rules={[{ required: true, message: "请输入邮箱" }]}>
            <Input placeholder="请输入 Sub2API 邮箱" />
          </Form.Item>
        )}

        <Form.Item label="密码 / Token" name="password" rules={[{ required: true, message: "请输入密码或 Token" }]}>
          <Input.Password placeholder={platform === "sub2api" ? "请输入密码" : "请输入 CLIProxy Token"} />
        </Form.Item>

        <Button type="primary" htmlType="submit" loading={loading} block>
          登录并拉取账号
        </Button>

        {loginError && (
          <Typography.Text type="danger" style={{ display: "block", marginTop: 8 }}>
            {loginError}
          </Typography.Text>
        )}
      </Form>

      <div className="meta-line">当前会话: {isLoggedIn ? sessionId : "未登录"}</div>

      <div className="panel-footnote">
        <Typography.Paragraph className="footnote-heading">开源与声明</Typography.Paragraph>

        <div className="footnote-card">
          <Typography.Text className="footnote-label">源码地址</Typography.Text>
          <Typography.Link className="footnote-link" href="https://github.com/ZhangWY0724/apitest" target="_blank" rel="noreferrer">
            GitHub · ZhangWY0724/apitest
          </Typography.Link>
        </div>

        <div className="footnote-card">
          <Typography.Text className="footnote-label">免责声明</Typography.Text>
          <Typography.Paragraph className="footnote-text">
            本站仅提供自助测试工具界面，不存储、不分发、不托管任何账号、密钥、Token 或第三方平台数据。
          </Typography.Paragraph>
          <Typography.Paragraph className="footnote-text footnote-text-last">
            站点实现与行为均可通过开源仓库源码自行审阅；使用者需自行确认输入信息、目标服务及相关操作的合规性与风险。
          </Typography.Paragraph>
        </div>
      </div>
    </section>
  );
}

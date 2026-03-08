from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from constants import CLIPROXY_API_CALL_PATH, DEFAULT_CLIPROXY_UA


@dataclass
class AppConfig:
    base_url: str
    platform: str
    login_path: str
    accounts_path: str
    timeout_seconds: int = 15


class ExternalApiClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.token: str | None = None
        self.cliproxy_files_cache: list[dict[str, Any]] = []

    def login_sub2api(self, email: str, password: str) -> str:
        response = self.session.post(
            f"{self.config.base_url}{self.config.login_path}",
            json={"email": email, "password": password},
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise ValueError(f"Sub2API 登录失败: {data.get('message', 'unknown error')}")

        token = data.get("data", {}).get("access_token")
        if not token:
            raise ValueError("Sub2API 登录成功但未返回 access_token")

        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        return token

    def login_cliproxyapi(self, password: str) -> str:
        token = password.strip()
        if not token:
            raise ValueError("CLIProxy Token 不能为空")

        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.fetch_cliproxy_auth_files()
        return token

    def fetch_cliproxy_auth_files(self) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{self.config.base_url}{self.config.login_path}",
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, dict) or not isinstance(data.get("files"), list):
            raise ValueError("CLIProxy 返回格式异常")

        self.cliproxy_files_cache = data["files"]
        return self.cliproxy_files_cache

    def fetch_sub2api_accounts_page(
        self,
        page: int,
        page_size: int = 100,
        timezone: str = "Asia/Shanghai",
    ) -> tuple[list[dict[str, Any]], int]:
        response = self.session.get(
            f"{self.config.base_url}{self.config.accounts_path}",
            params={
                "page": page,
                "page_size": page_size,
                "platform": "",
                "type": "",
                "status": "",
                "group": "",
                "search": "",
                "timezone": timezone,
            },
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise ValueError(f"获取账号列表失败: {data.get('message', 'unknown error')}")

        payload = data.get("data", {})
        items = payload.get("items")
        pages = payload.get("pages")
        if not isinstance(items, list) or not isinstance(pages, int):
            raise ValueError("Sub2API 账号列表返回格式异常")

        return items, pages

    def fetch_all_sub2api_accounts(self, page_size: int = 100) -> list[dict[str, Any]]:
        all_items: list[dict[str, Any]] = []
        page = 1
        while True:
            items, pages = self.fetch_sub2api_accounts_page(page, page_size=page_size)
            all_items.extend(items)
            if page >= pages:
                break
            page += 1
        return all_items

    def delete_sub2api_account(self, account_id: int) -> None:
        response = self.session.delete(
            f"{self.config.base_url}{self.config.accounts_path}/{account_id}",
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        try:
            data = response.json() if response.content else {}
        except json.JSONDecodeError:
            data = {}
        if data.get("code") not in (0, None):
            raise ValueError(f"删除账号失败: {data.get('message', 'unknown error')}")

    def delete_cliproxy_auth_file(self, name: str) -> None:
        if not name:
            raise ValueError("删除失败: name 不能为空")

        response = self.session.delete(
            f"{self.config.base_url}{self.config.login_path}",
            params={"name": name},
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        try:
            data = response.json() if response.content else {}
        except json.JSONDecodeError:
            data = {}
        if data.get("status") not in ("ok", None):
            raise ValueError(f"删除失败: response={data}")

    @staticmethod
    def extract_cliproxy_account_id(item: dict[str, Any]) -> str | None:
        for key in ("chatgpt_account_id", "chatgptAccountId", "account_id", "accountId"):
            value = item.get(key)
            if value:
                return str(value)
        id_token = item.get("id_token")
        if isinstance(id_token, dict):
            value = id_token.get("chatgpt_account_id")
            if value:
                return str(value)
        return None

    def test_cliproxy_auth_file(
        self,
        item: dict[str, Any],
        user_agent: str = DEFAULT_CLIPROXY_UA,
        fallback_account_id: str | None = None,
    ) -> tuple[bool, str]:
        auth_index = item.get("auth_index")
        if not auth_index:
            return False, "missing auth_index"

        account_id = self.extract_cliproxy_account_id(item) or fallback_account_id
        call_headers: dict[str, str] = {
            "Authorization": "Bearer $TOKEN$",
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        }
        if account_id:
            call_headers["Chatgpt-Account-Id"] = account_id

        response = self.session.post(
            f"{self.config.base_url}{CLIPROXY_API_CALL_PATH}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={
                "authIndex": auth_index,
                "method": "GET",
                "url": "https://chatgpt.com/backend-api/wham/usage",
                "header": call_headers,
            },
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()

        data = response.json()
        status_code = data.get("status_code")
        if not isinstance(status_code, int):
            return False, "missing status_code"
        if status_code == 401:
            return False, "status_code=401"
        return True, f"status_code={status_code}"

    def test_sub2api_account(self, account_id: int, model_id: str = "gpt-5.4") -> tuple[bool, str]:
        try:
            response = self.session.post(
                f"{self.config.base_url}{self.config.accounts_path}/{account_id}/test",
                json={"model_id": model_id},
                stream=True,
                timeout=(5, self.config.timeout_seconds),
            )
            response.raise_for_status()

            complete_success: bool | None = None
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                line = raw_line.strip()
                if not line.startswith("data:"):
                    continue
                data_text = line[5:].strip()
                if not data_text:
                    continue
                try:
                    event = json.loads(data_text)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "test_complete":
                    complete_success = bool(event.get("success"))

            if complete_success is True:
                return True, "test_complete.success=true"
            if complete_success is False:
                return False, "test_complete.success=false"
            return False, "未收到 test_complete 事件"
        except requests.exceptions.RequestException as exc:
            return False, f"网络错误或流超时: {exc}"

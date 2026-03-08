#!/usr/bin/env python3
"""
自动化脚本主体框架：
1. 选择平台（CLIProxyAPI / Sub2API / CLIProxyAPI+Sub2API）
2. 基于平台执行登录（当前已接通 Sub2API）
3. 展示功能菜单
4. 根据用户选择执行不同功能
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from dataclasses import dataclass
from getpass import getpass
from typing import Any, Callable

import requests

PLATFORM_CLIPROXY = "1"
PLATFORM_SUB2API = "2"
PLATFORM_BOTH = "3"
STATE_FILE = ".apitest_state.json"
DEFAULT_CLIPROXY_UA = "codex_cli_rs/0.76.0 (Debian 13.0.0; x86_64) WindowsTerminal"

ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"
ANSI_BLUE = "\033[34m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_RED = "\033[31m"
ANSI_CYAN = "\033[36m"


def _supports_ansi() -> bool:
    return sys.stdout.isatty()


def _style(text: str, *codes: str) -> str:
    if not _supports_ansi():
        return text
    return f"{''.join(codes)}{text}{ANSI_RESET}"


def print_title(text: str) -> None:
    print(_style(f"\n=== {text} ===", ANSI_BOLD, ANSI_CYAN))


def print_info(text: str) -> None:
    print(_style(f"[INFO] {text}", ANSI_BLUE))


def print_success(text: str) -> None:
    print(_style(f"[OK] {text}", ANSI_GREEN))


def print_warn(text: str) -> None:
    print(_style(f"[WARN] {text}", ANSI_YELLOW))


def print_error(text: str) -> None:
    print(_style(f"[ERR] {text}", ANSI_RED))


def choose_single_option(title: str, options: list[str]) -> int:
    """
    通用单选交互：
    - ↑/↓ 移动
    - Enter 确认
    """
    if not options:
        raise ValueError("选项不能为空。")

    if sys.platform != "win32":
        print_title(title)
        for i, item in enumerate(options, start=1):
            print(f"  {i}. {item}")
        raw = input("请输入序号: ").strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return idx
        raise ValueError("输入无效。")

    import msvcrt

    cursor = 0
    rendered_lines = 0

    def render_block(lines: list[str], previous: int) -> int:
        if previous > 0:
            sys.stdout.write(f"\x1b[{previous}A")
            for i in range(previous):
                sys.stdout.write("\x1b[2K")
                if i < previous - 1:
                    sys.stdout.write("\n")
            sys.stdout.write(f"\x1b[{previous - 1}A\r" if previous > 1 else "\r")
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()
        return len(lines)

    while True:
        lines: list[str] = [
            _style(title, ANSI_BOLD, ANSI_CYAN),
            _style("操作: ↑/↓ 移动 | Enter 确认", ANSI_DIM),
            "",
        ]
        for i, item in enumerate(options):
            pointer = ">" if i == cursor else " "
            lines.append(f"{pointer} {i + 1}. {item}")

        rendered_lines = render_block(lines, rendered_lines)

        key = msvcrt.getch()
        if key in {b"\r", b"\n"}:
            print()
            return cursor
        if key in {b"\x00", b"\xe0"}:
            ext = msvcrt.getch()
            if ext == b"H":
                cursor = (cursor - 1) % len(options)
            elif ext == b"P":
                cursor = (cursor + 1) % len(options)


def confirm_action(prompt: str) -> bool:
    idx = choose_single_option(prompt, ["是", "否"])
    return idx == 0


@dataclass
class AppConfig:
    """应用配置，后续可按需扩展。"""

    base_url: str
    platform: str
    login_path: str = "/api/v1/auth/login"
    accounts_path: str = "/api/v1/admin/accounts"
    login_user_field: str = "email"
    timeout_seconds: int = 15
    saved_email: str | None = None
    saved_password: str | None = None
    remember_credentials: bool = False


def load_local_state() -> dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def save_local_state(state: dict[str, Any]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


class ApiClient:
    """负责与后端 API 交互。"""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.token: str | None = None
        self.cliproxy_files_cache: list[dict[str, Any]] = []

    @staticmethod
    def _extract_by_path(data: dict[str, Any], path: str) -> Any:
        cur: Any = data
        for key in path.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(key)
        return cur

    @staticmethod
    def _check_common_response(data: dict[str, Any], action: str) -> None:
        code = data.get("code")
        if code is not None and code != 0:
            message = data.get("message", "unknown error")
            raise ValueError(f"{action}失败: {message}")

    def login_sub2api(self, email: str, password: str) -> str:
        """Sub2API 登录并保存 access_token。"""
        url = f"{self.config.base_url}{self.config.login_path}"
        payload = {"email": email, "password": password}
        resp = self.session.post(url, json=payload, timeout=self.config.timeout_seconds)
        resp.raise_for_status()

        data = resp.json()
        if data.get("code") != 0:
            message = data.get("message", "unknown error")
            raise ValueError(f"Sub2API 登录失败: {message}")

        token = data.get("data", {}).get("access_token")
        if not token:
            raise ValueError("Sub2API 登录成功但未返回 access_token，请检查接口返回结构。")

        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        return token

    def login_cliproxyapi(self, username: str, password: str) -> str:
        """CLIProxyAPI 登录（Bearer 直接使用密码）并拉取鉴权文件。"""
        _ = username  # CLIProxyAPI 不需要用户名，保留参数仅为兼容调用层。
        token = password.strip()
        if not token:
            raise ValueError("CLIProxyAPI 登录密码不能为空。")

        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})

        # CLIProxyAPI 通过访问 auth-files 接口完成鉴权校验并返回账号文件。
        url = f"{self.config.base_url}{self.config.login_path}"
        resp = self.session.get(url, timeout=self.config.timeout_seconds)
        resp.raise_for_status()

        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError("CLIProxyAPI 登录返回格式异常。")
        files = data.get("files")
        if not isinstance(files, list):
            raise ValueError("CLIProxyAPI 登录返回格式异常：缺少 files 列表。")
        self.cliproxy_files_cache = files
        return token

    def fetch_cliproxy_auth_files(self) -> list[dict[str, Any]]:
        """获取 CLIProxyAPI 鉴权文件列表。"""
        if not self.token:
            raise RuntimeError("尚未登录，请先执行登录。")
        url = f"{self.config.base_url}{self.config.login_path}"
        resp = self.session.get(url, timeout=self.config.timeout_seconds)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError("CLIProxyAPI 返回格式异常。")
        files = data.get("files")
        if not isinstance(files, list):
            raise ValueError("CLIProxyAPI 返回格式异常：files 不是列表。")
        self.cliproxy_files_cache = files
        return files

    @staticmethod
    def _cliproxy_item_type(item: dict[str, Any]) -> str | None:
        return item.get("type") or item.get("typo")

    @staticmethod
    def _extract_cliproxy_account_id(item: dict[str, Any]) -> str | None:
        for key in ("chatgpt_account_id", "chatgptAccountId", "account_id", "accountId"):
            val = item.get(key)
            if val:
                return str(val)
        id_token = item.get("id_token")
        if isinstance(id_token, dict):
            val = id_token.get("chatgpt_account_id")
            if val:
                return str(val)
        return None

    def test_cliproxy_auth_file(
        self,
        item: dict[str, Any],
        user_agent: str = DEFAULT_CLIPROXY_UA,
        fallback_account_id: str | None = None,
    ) -> tuple[bool, str]:
        """CLIProxy 单账号测活：通过 /v0/management/api-call 检查 usage 接口状态。"""
        if not self.token:
            raise RuntimeError("尚未登录，请先执行登录。")

        auth_index = item.get("auth_index")
        if not auth_index:
            return False, "missing auth_index"

        account_id = self._extract_cliproxy_account_id(item) or fallback_account_id
        call_header: dict[str, str] = {
            "Authorization": "Bearer $TOKEN$",
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        }
        if account_id:
            call_header["Chatgpt-Account-Id"] = account_id

        payload = {
            "authIndex": auth_index,
            "method": "GET",
            "url": "https://chatgpt.com/backend-api/wham/usage",
            "header": call_header,
        }

        url = f"{self.config.base_url}/v0/management/api-call"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        resp = self.session.post(url, headers=headers, json=payload, timeout=self.config.timeout_seconds)
        resp.raise_for_status()

        data = resp.json()
        status_code = data.get("status_code")
        if not isinstance(status_code, int):
            return False, "missing status_code"
        if status_code == 401:
            return False, "status_code=401"
        return True, f"status_code={status_code}"

    def delete_cliproxy_auth_file(self, name: str) -> None:
        """CLIProxy 删除账号文件：DELETE /v0/management/auth-files?name=..."""
        if not self.token:
            raise RuntimeError("尚未登录，请先执行登录。")
        if not name:
            raise ValueError("删除失败: missing name")

        url = f"{self.config.base_url}{self.config.login_path}"
        resp = self.session.delete(url, params={"name": name}, timeout=self.config.timeout_seconds)
        resp.raise_for_status()

        data = resp.json()
        if data.get("status") != "ok":
            raise ValueError(f"删除失败: response={data}")

    def fetch_sub2api_account_total(self, timezone: str = "Asia/Shanghai") -> int:
        """获取 Sub2API 账号配置文件总数。"""
        if not self.token:
            raise RuntimeError("尚未登录，请先执行登录。")

        url = f"{self.config.base_url}{self.config.accounts_path}"
        params = {
            "page": 1,
            "page_size": 10,
            "platform": "",
            "type": "",
            "status": "",
            "group": "",
            "search": "",
            "timezone": timezone,
        }
        resp = self.session.get(url, params=params, timeout=self.config.timeout_seconds)
        resp.raise_for_status()

        data = resp.json()
        if data.get("code") != 0:
            message = data.get("message", "unknown error")
            raise ValueError(f"获取账号配置文件失败: {message}")

        total = data.get("data", {}).get("total")
        if not isinstance(total, int):
            raise ValueError("账号配置文件返回格式异常：data.total 不是整数。")
        return total

    def fetch_sub2api_accounts_page(
        self, page: int, page_size: int = 100, timezone: str = "Asia/Shanghai"
    ) -> tuple[list[dict[str, Any]], int]:
        """分页获取 Sub2API 账号配置。"""
        if not self.token:
            raise RuntimeError("尚未登录，请先执行登录。")

        url = f"{self.config.base_url}{self.config.accounts_path}"
        params = {
            "page": page,
            "page_size": page_size,
            "platform": "",
            "type": "",
            "status": "",
            "group": "",
            "search": "",
            "timezone": timezone,
        }
        resp = self.session.get(url, params=params, timeout=self.config.timeout_seconds)
        resp.raise_for_status()

        data = resp.json()
        if data.get("code") != 0:
            message = data.get("message", "unknown error")
            raise ValueError(f"获取账号配置文件失败: {message}")

        payload = data.get("data", {})
        items = payload.get("items")
        pages = payload.get("pages")
        if not isinstance(items, list):
            raise ValueError("账号配置文件返回格式异常：data.items 不是列表。")
        if not isinstance(pages, int):
            raise ValueError("账号配置文件返回格式异常：data.pages 不是整数。")
        return items, pages

    def fetch_all_sub2api_accounts(
        self, page_size: int = 100, timezone: str = "Asia/Shanghai"
    ) -> list[dict[str, Any]]:
        """获取全部账号配置。"""
        all_items: list[dict[str, Any]] = []
        page = 1
        while True:
            items, pages = self.fetch_sub2api_accounts_page(page, page_size=page_size, timezone=timezone)
            all_items.extend(items)
            if page >= pages:
                break
            page += 1
        return all_items

    def delete_sub2api_account(self, account_id: int) -> None:
        """按账号 ID 删除账号配置。"""
        if not self.token:
            raise RuntimeError("尚未登录，请先执行登录。")

        url = f"{self.config.base_url}{self.config.accounts_path}/{account_id}"
        resp = self.session.delete(url, timeout=self.config.timeout_seconds)
        resp.raise_for_status()

        data = resp.json()
        if data.get("code") != 0:
            message = data.get("message", "unknown error")
            raise ValueError(f"删除账号 {account_id} 失败: {message}")

    def test_sub2api_account(self, account_id: int, model_id: str) -> tuple[bool, str]:
        """单账号测活：调用流式 test 接口并解析结果。"""
        if not self.token:
            raise RuntimeError("尚未登录，请先执行登录。")

        url = f"{self.config.base_url}{self.config.accounts_path}/{account_id}/test"
        payload = {"model_id": model_id}
        resp = self.session.post(
            url,
            json=payload,
            stream=True,
            timeout=self.config.timeout_seconds,
        )
        resp.raise_for_status()

        complete_success: bool | None = None
        for raw_line in resp.iter_lines(decode_unicode=True):
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

            event_type = event.get("type")
            if event_type == "test_complete":
                complete_success = bool(event.get("success"))

        if complete_success is True:
            return True, "test_complete.success=true"
        if complete_success is False:
            return False, "test_complete.success=false"
        return False, "未收到 test_complete 事件"


class AuthFileApp:
    """应用编排层：菜单 + 功能分发。"""

    def __init__(self, client: ApiClient) -> None:
        self.client = client
        self.platform = client.config.platform
        self.account_total: int = 0
        self.menu_items: list[tuple[str, Callable[[], None]]] = [
            ("检测重复账号", self.detect_duplicate_accounts),
            ("批量测活", self.batch_health_check),
            ("退出", self.exit_app),
        ]
        self.running = True

    def initialize(self) -> None:
        """按平台初始化，当前先接通 Sub2API 登录。"""
        if self.platform == PLATFORM_SUB2API:
            self.initialize_sub2api()
            return

        if self.platform == PLATFORM_CLIPROXY:
            self.initialize_cliproxyapi()
            return

        if self.platform == PLATFORM_BOTH:
            raise NotImplementedError("CLIProxyAPI+Sub2API 联合流程暂未实现。")

        raise ValueError("未知平台类型。")

    def initialize_sub2api(self) -> None:
        email = self.client.config.saved_email
        password = self.client.config.saved_password

        if email and password:
            print_info(f"已使用本地保存账号: {email}")
        else:
            email = input("请输入 Sub2API 登录邮箱: ").strip()
            password = getpass("请输入 Sub2API 登录密码: ").strip()

        print_info("正在登录 Sub2API...")
        self.client.login_sub2api(email, password)
        print_success("Sub2API 登录成功。")

        if self.client.config.remember_credentials:
            state = load_local_state()
            state["sub2api"] = {
                "base_url": self.client.config.base_url,
                "email": email,
                "password": password,
                "login_path": self.client.config.login_path,
                "accounts_path": self.client.config.accounts_path,
            }
            save_local_state(state)
            print_warn("注意: 密码将以明文保存在本地文件中。")
            print_success("已保存 URL/邮箱/密码，下次可直接复用。")

        print_info("正在获取账号配置文件总数...")
        self.account_total = self.client.fetch_sub2api_account_total()
        print_success(f"当前账号配置文件总数: {self.account_total}")

    def initialize_cliproxyapi(self) -> None:
        password = self.client.config.saved_password

        if password:
            print_info("已使用本地保存密码。")
        else:
            password = getpass("请输入 CLIProxyAPI 登录密码: ").strip()

        print_info("正在登录 CLIProxyAPI...")
        self.client.login_cliproxyapi("", password)
        print_success("CLIProxyAPI 登录成功。")

        if self.client.config.remember_credentials:
            state = load_local_state()
            state["cliproxyapi"] = {
                "base_url": self.client.config.base_url,
                "password": password,
            }
            save_local_state(state)
            print_warn("注意: 密码将以明文保存在本地文件中。")
            print_success("已保存 URL/密码，下次可直接复用。")

        files = self.client.cliproxy_files_cache or self.client.fetch_cliproxy_auth_files()
        self.account_total = len(files)
        print_success(f"当前账号配置文件总数: {self.account_total}")

    def _detect_duplicates_from_accounts(self, accounts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        skipped = 0
        for account in accounts:
            key = str(account.get("name", "")).strip()
            if not key:
                skipped += 1
                continue
            grouped[key].append(account)
        if skipped:
            print_warn(f"检测到 {skipped} 个无名账号，已跳过判重。")
        return {name: items for name, items in grouped.items() if len(items) > 1}

    def _detect_duplicates_from_cliproxy_files(
        self, files: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        skipped = 0
        for item in files:
            # 优先按 account 判重，其次 label/name
            key = (
                str(item.get("account", "")).strip()
                or str(item.get("label", "")).strip()
                or str(item.get("name", "")).strip()
            )
            if not key:
                skipped += 1
                continue
            grouped[key].append(item)
        if skipped:
            print_warn(f"检测到 {skipped} 个无名鉴权文件，已跳过判重。")
        return {name: items for name, items in grouped.items() if len(items) > 1}

    def run(self) -> None:
        """应用主循环。"""
        while self.running:
            choice = choose_single_option("\n=== 功能菜单 ===", [item[0] for item in self.menu_items])
            action = self.menu_items[choice][1]
            action()

    @staticmethod
    def choose_accounts_with_keyboard(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        键盘交互选择账号（Windows 终端）：
        - ↑/↓：移动
        - Space：勾选/取消
        - A：全选/全不选
        - Enter：确认
        - Q：取消
        """
        if not items:
            return []

        if sys.platform != "win32":
            print("当前环境非 Windows，降级为文本序号输入。")
            choice = input("输入 all 全选，输入序号(逗号分隔)单选/多选，输入 n 取消: ").strip().lower()
            if choice in {"n", "no", ""}:
                return []
            if choice == "all":
                return items
            indexes: list[int] = []
            for token in choice.split(","):
                token = token.strip()
                if token.isdigit():
                    val = int(token)
                    if 1 <= val <= len(items):
                        indexes.append(val - 1)
            selected = []
            seen: set[int] = set()
            for idx in indexes:
                if idx in seen:
                    continue
                seen.add(idx)
                selected.append(items[idx])
            return selected

        import msvcrt

        cursor = 0
        selected: set[int] = set()
        rendered_lines = 0

        def render_block(lines: list[str], previous: int) -> int:
            if previous > 0:
                sys.stdout.write(f"\x1b[{previous}A")
                for i in range(previous):
                    sys.stdout.write("\x1b[2K")
                    if i < previous - 1:
                        sys.stdout.write("\n")
                sys.stdout.write(f"\x1b[{previous - 1}A\r" if previous > 1 else "\r")
            sys.stdout.write("\n".join(lines) + "\n")
            sys.stdout.flush()
            return len(lines)

        def render() -> None:
            nonlocal rendered_lines
            lines: list[str] = [
                "=== 异常账号选择删除 ===",
                "操作: ↑/↓ 移动 | Space 勾选 | A 全选/全不选 | Enter 确认 | Q 取消",
                "",
            ]
            for idx, item in enumerate(items):
                pointer = ">" if idx == cursor else " "
                checked = "[x]" if idx in selected else "[ ]"
                account_id = item.get("id")
                account_name = item.get("name", "unknown")
                lines.append(f"{pointer} {checked} {idx + 1}. id={account_id}, name={account_name}")
            lines.append("")
            lines.append(f"已选择: {len(selected)}/{len(items)}")
            rendered_lines = render_block(lines, rendered_lines)

        while True:
            render()
            key = msvcrt.getch()

            if key in {b"\r", b"\n"}:
                print()
                return [items[i] for i in sorted(selected)]
            if key in {b"q", b"Q"}:
                print()
                return []
            if key in {b"a", b"A"}:
                if len(selected) == len(items):
                    selected.clear()
                else:
                    selected = set(range(len(items)))
                continue
            if key == b" ":
                if cursor in selected:
                    selected.remove(cursor)
                else:
                    selected.add(cursor)
                continue
            if key in {b"\x00", b"\xe0"}:
                ext = msvcrt.getch()
                if ext == b"H":  # Up
                    cursor = (cursor - 1) % len(items)
                elif ext == b"P":  # Down
                    cursor = (cursor + 1) % len(items)

    def detect_duplicate_accounts(self) -> None:
        print_title("检测重复账号")
        print_info("正在拉取账号明细并检测重复...")
        duplicates: dict[str, list[dict[str, Any]]]
        if self.platform == PLATFORM_SUB2API:
            accounts = self.client.fetch_all_sub2api_accounts(page_size=100)
            self.account_total = len(accounts)
            print_info(f"账号明细拉取完成，共 {self.account_total} 条。")
            duplicates = self._detect_duplicates_from_accounts(accounts)
        elif self.platform == PLATFORM_CLIPROXY:
            files = self.client.fetch_cliproxy_auth_files()
            self.account_total = len(files)
            print_info(f"鉴权文件拉取完成，共 {self.account_total} 条。")
            duplicates = self._detect_duplicates_from_cliproxy_files(files)
        else:
            raise NotImplementedError("当前平台尚未实现重复检测。")

        if not duplicates:
            print_success("检测完成：未发现重复账号。")
            return

        duplicate_groups = len(duplicates)
        duplicate_records = sum(len(items) - 1 for items in duplicates.values())
        print_warn(f"检测完成：发现 {duplicate_groups} 组重复账号，待清理 {duplicate_records} 条重复记录。")

        to_delete_items: list[dict[str, Any]] = []
        if self.platform == PLATFORM_SUB2API:
            for items in duplicates.values():
                # 每组保留最小 id，删除其余，保证策略简单且可预测。
                valid_items = [item for item in items if isinstance(item.get("id"), int)]
                valid_items.sort(key=lambda item: item["id"])
                to_delete_items.extend({"id": item["id"], "name": str(item.get("name", ""))} for item in valid_items[1:])
        elif self.platform == PLATFORM_CLIPROXY:
            for items in duplicates.values():
                # 每组保留一个，其余按文件名删除。
                valid_items = [item for item in items if str(item.get("name", "")).strip()]
                valid_items.sort(
                    key=lambda item: (
                        str(item.get("updated_at", "")),
                        str(item.get("modtime", "")),
                        str(item.get("created_at", "")),
                    ),
                    reverse=True,
                )
                for item in valid_items[1:]:
                    to_delete_items.append(
                        {
                            "name": str(item.get("name", "")).strip(),
                        }
                    )

        if not to_delete_items:
            print_warn("检测到重复账号，但缺少可删除的合法标识，已跳过删除。")
            return

        if not confirm_action("检测到重复账号，是否删除重复项？"):
            print_info("已取消删除操作。")
            return

        success = 0
        failed = 0
        for item in to_delete_items:
            try:
                if self.platform == PLATFORM_SUB2API:
                    account_id = item.get("id")
                    if not isinstance(account_id, int):
                        raise ValueError("invalid id")
                    self.client.delete_sub2api_account(account_id)
                else:
                    name = str(item.get("name", "")).strip()
                    if not name:
                        raise ValueError("missing name")
                    self.client.delete_cliproxy_auth_file(name)
                success += 1
            except Exception as exc:  # 删除批处理中不中断，继续处理后续账号。
                failed += 1
            print(
                f"\r删除进度: {success + failed}/{len(to_delete_items)} | 成功 {success} | 失败 {failed}",
                end="",
                flush=True,
            )

        print()
        print_success(f"删除完成：成功 {success} 条，失败 {failed} 条。")

    def batch_health_check(self) -> None:
        print_title("批量测活")
        model_id = "gpt-5.4"
        user_agent = DEFAULT_CLIPROXY_UA

        if self.platform == PLATFORM_SUB2API:
            model_choice = choose_single_option("请选择测活模型", ["gpt-5.4（默认）", "自定义输入"])
            if model_choice == 1:
                model_id = input("请输入测活模型ID: ").strip() or "gpt-5.4"
            print_info("正在拉取账号明细...")
            accounts = self.client.fetch_all_sub2api_accounts(page_size=100)
        elif self.platform == PLATFORM_CLIPROXY:
            print_info("正在拉取鉴权文件明细...")
            accounts = self.client.fetch_cliproxy_auth_files()
        else:
            raise NotImplementedError("当前平台尚未实现批量测活。")

        if not accounts:
            print_warn("没有可测活账号。")
            return

        print_info(f"开始批量测活，共 {len(accounts)} 个账号，最大并发 5。")
        max_workers = min(5, len(accounts))
        success_count = 0
        failed_count = 0
        done_count = 0
        failed_accounts: list[dict[str, Any]] = []

        def run_one(account: dict[str, Any]) -> tuple[bool, int | None, str, str, str | None]:
            account_name = str(
                account.get("name")
                or account.get("account")
                or account.get("email")
                or "unknown"
            )
            delete_name = str(account.get("name", "")).strip() or None
            account_id = account.get("id")
            # 使用独立 Session 避免跨线程共享连接池
            standalone = requests.Session()
            standalone.headers.update(self.client.session.headers)
            try:
                if self.platform == PLATFORM_SUB2API:
                    if not isinstance(account_id, int):
                        return False, None, account_name, "账号缺少合法 id", None
                    url = f"{self.client.config.base_url}{self.client.config.accounts_path}/{account_id}/test"
                    payload = {"model_id": model_id}
                    resp = standalone.post(url, json=payload, stream=True, timeout=self.client.config.timeout_seconds)
                    resp.raise_for_status()
                    complete_success: bool | None = None
                    for raw_line in resp.iter_lines(decode_unicode=True):
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
                        return True, account_id, account_name, "test_complete.success=true", None
                    if complete_success is False:
                        return False, account_id, account_name, "test_complete.success=false", None
                    return False, account_id, account_name, "未收到 test_complete 事件", None
                else:
                    auth_index = account.get("auth_index")
                    if not auth_index:
                        return False, None, account_name, "missing auth_index", delete_name
                    account_id_str = self.client._extract_cliproxy_account_id(account)
                    call_header: dict[str, str] = {
                        "Authorization": "Bearer $TOKEN$",
                        "Content-Type": "application/json",
                        "User-Agent": user_agent,
                    }
                    if account_id_str:
                        call_header["Chatgpt-Account-Id"] = account_id_str
                    payload = {
                        "authIndex": auth_index,
                        "method": "GET",
                        "url": "https://chatgpt.com/backend-api/wham/usage",
                        "header": call_header,
                    }
                    url = f"{self.client.config.base_url}/v0/management/api-call"
                    headers = {
                        "Authorization": f"Bearer {self.client.token}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    }
                    resp = standalone.post(url, headers=headers, json=payload, timeout=self.client.config.timeout_seconds)
                    resp.raise_for_status()
                    data = resp.json()
                    status_code = data.get("status_code")
                    if not isinstance(status_code, int):
                        return False, None, account_name, "missing status_code", delete_name
                    if status_code == 401:
                        return False, None, account_name, "status_code=401", delete_name
                    return True, None, account_name, f"status_code={status_code}", delete_name
            except Exception as exc:
                return False, account_id if isinstance(account_id, int) else None, account_name, str(exc), delete_name
            finally:
                standalone.close()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(run_one, account) for account in accounts]
            for future in as_completed(futures):
                try:
                    ok, account_id, account_name, reason, delete_name = future.result()
                except Exception as exc:
                    ok, account_id, account_name, reason, delete_name = False, None, "unknown", f"Future 异常: {str(exc)}", None
                done_count += 1
                if ok:
                    success_count += 1
                else:
                    failed_count += 1
                    failed_accounts.append(
                        {
                            "id": account_id,
                            "name": account_name,
                            "reason": reason,
                            "delete_name": delete_name,
                        }
                    )
                print(
                    f"\r进度: 全部 {done_count}/{len(accounts)} | 成功 {success_count} | 异常 {failed_count}",
                    end="",
                    flush=True,
                )

        print()

        print_title("批量测活结果")
        print(f"总数: {len(accounts)}")
        print(_style(f"成功: {success_count}", ANSI_GREEN))
        print(_style(f"异常: {failed_count}", ANSI_RED if failed_count else ANSI_GREEN))

        if not failed_accounts:
            return

        print("\n异常账号列表：")
        for idx, item in enumerate(failed_accounts, start=1):
            account_id = item.get("id")
            account_name = item.get("name", "unknown")
            reason = item.get("reason", "")
            print(f"{idx}. id={account_id}, name={account_name}, reason={reason}")

        if not confirm_action("是否进入交互选择并删除异常账号？"):
            print_info("已取消删除异常账号。")
            return

        to_delete = self.choose_accounts_with_keyboard(failed_accounts)

        if not to_delete:
            print_warn("没有可删除的异常账号。")
            return

        success = 0
        failed = 0
        for item in to_delete:
            try:
                if self.platform == PLATFORM_SUB2API:
                    account_id = item.get("id")
                    if not isinstance(account_id, int):
                        raise ValueError("invalid id")
                    self.client.delete_sub2api_account(account_id)
                else:
                    name = str(item.get("delete_name") or item.get("name", "")).strip()
                    if not name:
                        raise ValueError("missing name")
                    self.client.delete_cliproxy_auth_file(name)
                success += 1
            except Exception:
                failed += 1
            print(
                f"\r删除进度: {success + failed}/{len(to_delete)} | 成功 {success} | 失败 {failed}",
                end="",
                flush=True,
            )

        print()
        print_success(f"异常账号删除完成：成功 {success} 条，失败 {failed} 条。")

    def exit_app(self) -> None:
        self.running = False
        print_success("程序已退出。")


def build_default_config() -> AppConfig:
    """构造配置：先选平台，再录入对应 Base URL。"""
    platform_options = ["CLIProxyAPI", "Sub2API", "CLIProxyAPI+Sub2API"]
    platform_idx = choose_single_option("=== 平台选择 ===", platform_options)
    platform_map = {
        0: PLATFORM_CLIPROXY,
        1: PLATFORM_SUB2API,
        2: PLATFORM_BOTH,
    }
    platform = platform_map[platform_idx]
    state = load_local_state()

    if platform == PLATFORM_SUB2API:
        sub2_state = state.get("sub2api", {}) if isinstance(state.get("sub2api", {}), dict) else {}
        saved_base_url = str(sub2_state.get("base_url", "")).strip()
        saved_email = str(sub2_state.get("email", "")).strip()
        saved_password = str(sub2_state.get("password", "")).strip()
        saved_login_path = str(sub2_state.get("login_path", "/api/v1/auth/login")).strip() or "/api/v1/auth/login"
        saved_accounts_path = (
            str(sub2_state.get("accounts_path", "/api/v1/admin/accounts")).strip() or "/api/v1/admin/accounts"
        )

        use_saved_url = False
        if saved_base_url:
            use_saved_url = confirm_action(f"检测到已保存 URL: {saved_base_url}\n是否直接使用？")

        if use_saved_url:
            base_url = saved_base_url
        else:
            base_url = input("请输入平台 URL（例如 http://74.48.108.97:8080）: ").strip().rstrip("/")
            if not base_url:
                raise ValueError("Base URL 不能为空。")

        use_saved_credentials = False
        if saved_email and saved_password:
            use_saved_credentials = confirm_action(f"检测到已保存账号: {saved_email}\n是否直接使用？")

        remember_credentials = confirm_action("是否记住本次 URL/邮箱/密码，供下次直接使用？")
        return AppConfig(
            base_url=base_url,
            platform=platform,
            login_path=saved_login_path,
            accounts_path=saved_accounts_path,
            login_user_field="email",
            saved_email=saved_email if use_saved_credentials else None,
            saved_password=saved_password if use_saved_credentials else None,
            remember_credentials=remember_credentials,
        )

    elif platform == PLATFORM_CLIPROXY:
        cliproxy_state = (
            state.get("cliproxyapi", {}) if isinstance(state.get("cliproxyapi", {}), dict) else {}
        )
        saved_base_url = str(cliproxy_state.get("base_url", "")).strip()
        saved_password = str(cliproxy_state.get("password", "")).strip()
        login_path = "/v0/management/auth-files"

        use_saved_url = False
        if saved_base_url:
            use_saved_url = confirm_action(f"检测到已保存 URL: {saved_base_url}\n是否直接使用？")

        if use_saved_url:
            base_url = saved_base_url
        else:
            base_url = input("请输入平台 URL（例如 http://74.48.108.97:8080）: ").strip().rstrip("/")
            if not base_url:
                raise ValueError("Base URL 不能为空。")

        use_saved_credentials = False
        if saved_password:
            use_saved_credentials = confirm_action("检测到已保存 CLIProxyAPI 密码，是否直接使用？")

        remember_credentials = confirm_action("是否记住本次 CLIProxyAPI 的 URL/密码？")
        return AppConfig(
            base_url=base_url,
            platform=platform,
            login_path=login_path,
            accounts_path=login_path,
            login_user_field="password",
            saved_password=saved_password if use_saved_credentials else None,
            remember_credentials=remember_credentials,
        )

    else:
        raise NotImplementedError("CLIProxyAPI+Sub2API 联合模式待实现。")


def main() -> None:
    try:
        config = build_default_config()
        client = ApiClient(config)
        app = AuthFileApp(client)
        app.initialize()
        app.run()
    except requests.HTTPError as exc:
        print_error(f"HTTP 请求失败: {exc}")
    except requests.RequestException as exc:
        print_error(f"网络请求异常: {exc}")
    except Exception as exc:  # 保留统一兜底，便于主流程稳定。
        print_error(f"程序异常: {exc}")


if __name__ == "__main__":
    main()

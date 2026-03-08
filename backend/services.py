from __future__ import annotations

import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterable

import requests

from clients import AppConfig, ExternalApiClient
from constants import (
    CLIPROXY_API_CALL_PATH,
    CLIPROXY_AUTH_FILES_PATH,
    DEFAULT_CLIPROXY_UA,
    PLATFORM_CLIPROXY,
    PLATFORM_SUB2API,
    SUB2API_ACCOUNTS_PATH,
    SUB2API_LOGIN_PATH,
)
from store import SessionContext


def build_client(platform: str, base_url: str, email: str | None, password: str) -> ExternalApiClient:
    normalized_base_url = base_url.strip().rstrip("/")
    if not normalized_base_url:
        raise ValueError("base_url 不能为空")

    if platform == PLATFORM_SUB2API:
        if not email:
            raise ValueError("Sub2API 需要 email")
        client = ExternalApiClient(
            AppConfig(
                base_url=normalized_base_url,
                platform=PLATFORM_SUB2API,
                login_path=SUB2API_LOGIN_PATH,
                accounts_path=SUB2API_ACCOUNTS_PATH,
            )
        )
        client.login_sub2api(email, password)
        return client

    if platform == PLATFORM_CLIPROXY:
        client = ExternalApiClient(
            AppConfig(
                base_url=normalized_base_url,
                platform=PLATFORM_CLIPROXY,
                login_path=CLIPROXY_AUTH_FILES_PATH,
                accounts_path=CLIPROXY_AUTH_FILES_PATH,
            )
        )
        client.login_cliproxyapi(password)
        return client

    raise ValueError("不支持的平台")


def normalize_sub2_account(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "platform": PLATFORM_SUB2API,
        "account_id": item.get("id"),
        "delete_name": None,
        "name": str(item.get("name") or item.get("email") or "unknown"),
        "channel": str(item.get("platform") or item.get("type") or "sub2api"),
        "status": str(item.get("status") or "unknown"),
        "created_at": str(item.get("created_at") or item.get("create_time") or ""),
        "raw": item,
    }


def normalize_cliproxy_account(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "platform": PLATFORM_CLIPROXY,
        "account_id": None,
        "delete_name": str(item.get("name") or "").strip() or None,
        "name": str(item.get("account") or item.get("label") or item.get("name") or "unknown"),
        "channel": str(item.get("type") or item.get("typo") or "cliproxy"),
        "status": str(item.get("status") or "unknown"),
        "created_at": str(item.get("created_at") or item.get("modtime") or item.get("updated_at") or ""),
        "raw": item,
    }


def load_accounts(context: SessionContext) -> list[dict[str, Any]]:
    if context.platform == PLATFORM_SUB2API:
        return [normalize_sub2_account(item) for item in context.client.fetch_all_sub2api_accounts()]
    return [normalize_cliproxy_account(item) for item in context.client.fetch_cliproxy_auth_files()]


def filter_accounts(
    accounts: list[dict[str, Any]],
    keyword: str = "",
    channel: str = "",
    status: str = "",
) -> list[dict[str, Any]]:
    normalized_keyword = keyword.strip().lower()

    def matches(account: dict[str, Any]) -> bool:
        name = str(account.get("name") or "").lower()
        current_channel = str(account.get("channel") or "")
        current_status = str(account.get("status") or "")

        keyword_hit = (
            not normalized_keyword
            or normalized_keyword in name
            or normalized_keyword in current_channel.lower()
            or normalized_keyword in current_status.lower()
        )
        channel_hit = not channel or current_channel == channel
        status_hit = not status or current_status == status
        return keyword_hit and channel_hit and status_hit

    return [account for account in accounts if matches(account)]


def paginate_accounts(
    accounts: list[dict[str, Any]],
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int, int]:
    normalized_page_size = min(max(page_size, 1), 200)
    total = len(accounts)
    max_page = max((total - 1) // normalized_page_size + 1, 1)
    normalized_page = min(max(page, 1), max_page)
    start = (normalized_page - 1) * normalized_page_size
    end = start + normalized_page_size
    return accounts[start:end], normalized_page, normalized_page_size


def query_accounts(
    context: SessionContext,
    keyword: str = "",
    channel: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    all_accounts = load_accounts(context)
    filtered_accounts = filter_accounts(all_accounts, keyword=keyword, channel=channel, status=status)
    page_items, normalized_page, normalized_page_size = paginate_accounts(filtered_accounts, page=page, page_size=page_size)

    return {
        "total": len(filtered_accounts),
        "all_total": len(all_accounts),
        "page": normalized_page,
        "page_size": normalized_page_size,
        "accounts": page_items,
        "channel_options": sorted({str(item.get("channel") or "") for item in all_accounts if item.get("channel")}),
        "status_options": sorted({str(item.get("status") or "") for item in all_accounts if item.get("status")}),
    }


def detect_duplicates(platform: str, accounts: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for account in accounts:
        name = str(account.get("name") or "").strip()
        if name:
            grouped[name].append(account)

    duplicates = {name: items for name, items in grouped.items() if len(items) > 1}
    delete_candidates: list[dict[str, Any]] = []

    if platform == PLATFORM_SUB2API:
        for items in duplicates.values():
            valid_items = [item for item in items if isinstance(item.get("account_id"), int)]
            valid_items.sort(key=lambda item: int(item["account_id"]))
            delete_candidates.extend(valid_items[1:])
    else:
        for items in duplicates.values():
            valid_items = [item for item in items if item.get("delete_name")]
            valid_items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
            delete_candidates.extend(valid_items[1:])

    return duplicates, delete_candidates


def delete_duplicate_accounts(context: SessionContext, keys: list[str]) -> dict[str, int]:
    if not keys:
        return {"selected": 0, "success": 0, "failed": 0}

    accounts = load_accounts(context)
    _, delete_candidates = detect_duplicates(context.platform, accounts)
    allowed_names = set(keys)
    selected_accounts = [item for item in delete_candidates if item["name"] in allowed_names]

    success = 0
    failed = 0
    for item in selected_accounts:
        try:
            delete_account(
                context,
                account_id=item.get("account_id"),
                delete_name=item.get("delete_name"),
            )
            success += 1
        except Exception:
            failed += 1

    return {"selected": len(selected_accounts), "success": success, "failed": failed}


def _item_value(item: Any, field: str) -> Any:
    if isinstance(item, dict):
        return item.get(field)
    return getattr(item, field, None)


def _select_accounts(all_accounts: list[dict[str, Any]], items: Iterable[Any]) -> list[dict[str, Any]]:
    target_ids: set[int] = set()
    target_names: set[str] = set()
    for item in items:
        account_id = _item_value(item, "account_id")
        delete_name = _item_value(item, "delete_name")
        if isinstance(account_id, int):
            target_ids.add(account_id)
        if isinstance(delete_name, str) and delete_name:
            target_names.add(delete_name)

    return [
        account
        for account in all_accounts
        if account.get("account_id") in target_ids or account.get("delete_name") in target_names
    ]


def run_batch_health_check(context: SessionContext, model_id: str, items: list[Any]) -> dict[str, Any]:
    all_accounts = load_accounts(context)
    accounts = _select_accounts(all_accounts, items) if items else all_accounts
    if not accounts:
        return {"total": 0, "success": 0, "failed": 0, "failed_accounts": []}

    failed_accounts: list[dict[str, Any]] = []
    success = 0
    failed = 0

    def run_one(account: dict[str, Any]) -> tuple[bool, str]:
        standalone = requests.Session()
        standalone.headers.update(context.client.session.headers)
        try:
            if context.platform == PLATFORM_SUB2API:
                account_id = account.get("account_id")
                if not isinstance(account_id, int):
                    return False, "账号缺少合法 id"

                response = standalone.post(
                    f"{context.client.config.base_url}{context.client.config.accounts_path}/{account_id}/test",
                    json={"model_id": model_id},
                    stream=True,
                    timeout=(5, context.client.config.timeout_seconds),
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

            raw = account.get("raw", {})
            auth_index = raw.get("auth_index")
            if not auth_index:
                return False, "missing auth_index"

            account_id = context.client.extract_cliproxy_account_id(raw)
            call_headers: dict[str, str] = {
                "Authorization": "Bearer $TOKEN$",
                "Content-Type": "application/json",
                "User-Agent": DEFAULT_CLIPROXY_UA,
            }
            if account_id:
                call_headers["Chatgpt-Account-Id"] = account_id

            response = standalone.post(
                f"{context.client.config.base_url}{CLIPROXY_API_CALL_PATH}",
                headers={
                    "Authorization": f"Bearer {context.client.token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={
                    "authIndex": auth_index,
                    "method": "GET",
                    "url": "https://chatgpt.com/backend-api/wham/usage",
                    "header": call_headers,
                },
                timeout=context.client.config.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            status_code = data.get("status_code")
            if not isinstance(status_code, int):
                return False, "missing status_code"
            if status_code == 401:
                return False, "status_code=401"
            return True, f"status_code={status_code}"
        except Exception as exc:
            return False, f"请求异常: {exc}"
        finally:
            standalone.close()

    with ThreadPoolExecutor(max_workers=min(5, len(accounts))) as executor:
        futures = {executor.submit(run_one, account): account for account in accounts}
        for future in as_completed(futures):
            account = futures[future]
            try:
                is_success, reason = future.result()
            except Exception as exc:
                is_success, reason = False, f"Future 异常: {exc}"

            if is_success:
                success += 1
                continue

            failed += 1
            failed_accounts.append(
                {
                    "name": account.get("name"),
                    "account_id": account.get("account_id"),
                    "delete_name": account.get("delete_name"),
                    "reason": reason,
                }
            )

    return {
        "total": len(accounts),
        "success": success,
        "failed": failed,
        "failed_accounts": failed_accounts,
    }


def test_account(
    context: SessionContext,
    account_id: int | None,
    delete_name: str | None,
    model_id: str,
) -> tuple[bool, str]:
    if context.platform == PLATFORM_SUB2API:
        if not isinstance(account_id, int):
            raise ValueError("缺少 account_id")
        return context.client.test_sub2api_account(account_id, model_id)

    target = next(
        (account for account in load_accounts(context) if account.get("delete_name") == delete_name),
        None,
    )
    if not target:
        raise ValueError("未找到目标账号")
    return context.client.test_cliproxy_auth_file(target.get("raw", {}))


def delete_account(context: SessionContext, account_id: int | None, delete_name: str | None) -> None:
    if context.platform == PLATFORM_SUB2API:
        if not isinstance(account_id, int):
            raise ValueError("缺少 account_id")
        context.client.delete_sub2api_account(account_id)
        return

    if not delete_name:
        raise ValueError("缺少 delete_name")
    context.client.delete_cliproxy_auth_file(delete_name)


def bulk_delete_accounts(context: SessionContext, items: list[Any]) -> dict[str, int]:
    if not items:
        return {"total": 0, "success": 0, "failed": 0}

    success = 0
    failed = 0
    for item in items:
        try:
            delete_account(
                context,
                account_id=_item_value(item, "account_id"),
                delete_name=_item_value(item, "delete_name"),
            )
            success += 1
        except Exception:
            failed += 1

    return {"total": len(items), "success": success, "failed": failed}

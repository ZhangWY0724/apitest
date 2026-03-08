from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from constants import ALLOWED_ORIGINS
from schemas import (
    AccountActionRequest,
    BatchHealthCheckRequest,
    BulkDeleteRequest,
    DuplicateDeleteRequest,
    LoginRequest,
)
from services import (
    build_client,
    bulk_delete_accounts,
    delete_account,
    delete_duplicate_accounts,
    detect_duplicates,
    load_accounts,
    query_accounts,
    run_batch_health_check,
    test_account,
)
from store import SessionStore

store = SessionStore()
app = FastAPI(title="API Test Web Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_context(session_id: str):
    try:
        return store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/session/login")
def login(request: LoginRequest) -> dict[str, Any]:
    try:
        client = build_client(request.platform, request.base_url, request.email, request.password)
        context = store.create(request.platform, client)
        return {
            "session_id": context.session_id,
            "platform": request.platform,
            **query_accounts(context),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/session/{session_id}/accounts")
def accounts(
    session_id: str,
    keyword: str = "",
    channel: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    try:
        context = _get_context(session_id)
        return query_accounts(
            context,
            keyword=keyword,
            channel=channel,
            status=status,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/session/{session_id}/detect-duplicates")
def detect_duplicate_accounts(session_id: str) -> dict[str, Any]:
    try:
        context = _get_context(session_id)
        items = load_accounts(context)
        duplicate_groups, candidates = detect_duplicates(context.platform, items)
        return {
            "group_count": len(duplicate_groups),
            "delete_count": len(candidates),
            "duplicate_keys": sorted(duplicate_groups.keys()),
            "candidates": candidates,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/session/{session_id}/delete-duplicates")
def delete_duplicates(session_id: str, request: DuplicateDeleteRequest) -> dict[str, Any]:
    try:
        context = _get_context(session_id)
        return delete_duplicate_accounts(context, request.keys)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/session/{session_id}/batch-health-check")
def batch_health_check(session_id: str, request: BatchHealthCheckRequest) -> dict[str, Any]:
    try:
        context = _get_context(session_id)
        return run_batch_health_check(context, request.model_id, request.items)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/session/{session_id}/account-test")
def account_test_endpoint(session_id: str, request: AccountActionRequest) -> dict[str, Any]:
    try:
        context = _get_context(session_id)
        success, reason = test_account(context, request.account_id, request.delete_name, request.model_id)
        return {"success": success, "reason": reason}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/session/{session_id}/account-delete")
def account_delete_endpoint(session_id: str, request: AccountActionRequest) -> dict[str, Any]:
    try:
        context = _get_context(session_id)
        delete_account(context, request.account_id, request.delete_name)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/session/{session_id}/bulk-delete")
def bulk_delete_endpoint(session_id: str, request: BulkDeleteRequest) -> dict[str, Any]:
    try:
        context = _get_context(session_id)
        return bulk_delete_accounts(context, request.items)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/session/{session_id}")
def logout(session_id: str) -> dict[str, Any]:
    store.remove(session_id)
    return {"success": True}

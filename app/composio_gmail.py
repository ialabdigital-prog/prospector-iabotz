from __future__ import annotations

from typing import Any


def _client(api_key: str):
    try:
        from composio import Composio
    except ImportError as exc:
        raise RuntimeError("SDK Composio não instalado") from exc
    return Composio(api_key=api_key)


def gmail_status(api_key: str, user_id: str = "") -> dict[str, Any]:
    if not api_key:
        return {"connected": False, "reason": "API key não configurada"}
    try:
        composio = _client(api_key)
        response = composio.connected_accounts.list(
            toolkit_slugs=["gmail"], statuses=["ACTIVE"], limit=50
        )
        accounts = list(response.items or [])
        selected = next(
            (account for account in accounts if user_id and account.user_id == user_id),
            None,
        )
        configured_user_mismatch = bool(user_id and not selected)
        if not selected and len(accounts) == 1:
            selected = accounts[0]
        if not selected:
            reason = "Nenhuma conta Gmail ACTIVE encontrada no projeto Composio"
            if len(accounts) > 1:
                reason = "Há várias contas Gmail; informe o User ID correto"
            return {
                "connected": False,
                "reason": reason,
                "accounts": len(accounts),
                "configured_user_mismatch": configured_user_mismatch,
            }
        return {
            "connected": True,
            "reason": "Conta Gmail ACTIVE",
            "accounts": len(accounts),
            "user_id": selected.user_id,
            "connected_account_id": selected.id,
            "configured_user_mismatch": configured_user_mismatch,
        }
    except Exception as exc:
        return {"connected": False, "reason": str(exc), "accounts": 0}


def create_draft(
    api_key: str,
    user_id: str,
    recipient: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    status = gmail_status(api_key, user_id)
    if not status.get("connected"):
        raise RuntimeError(status.get("reason") or "Gmail não conectado")
    composio = _client(api_key)
    tool = composio.tools.get_raw_composio_tool_by_slug("GMAIL_CREATE_EMAIL_DRAFT")
    result = composio.tools.execute(
        slug="GMAIL_CREATE_EMAIL_DRAFT",
        version=tool.version,
        user_id=status["user_id"],
        connected_account_id=status["connected_account_id"],
        arguments={
            "recipient_email": recipient,
            "subject": subject,
            "body": body,
            "is_html": True,
        },
    )
    if not result.get("successful"):
        raise RuntimeError(str(result.get("error") or "Composio recusou a criação do draft"))
    data = result.get("data") or {}
    return {
        "draft_id": data.get("draft_id") or data.get("id") or "",
        "user_id": status["user_id"],
        "configured_user_mismatch": status.get("configured_user_mismatch", False),
    }


def search_messages(api_key: str, user_id: str, query: str, limit: int = 10) -> list[dict]:
    status = gmail_status(api_key, user_id)
    if not status.get("connected"):
        raise RuntimeError(status.get("reason") or "Gmail não conectado")
    composio = _client(api_key)
    tool = composio.tools.get_raw_composio_tool_by_slug("GMAIL_FETCH_EMAILS")
    result = composio.tools.execute(
        slug="GMAIL_FETCH_EMAILS",
        version=tool.version,
        user_id=status["user_id"],
        connected_account_id=status["connected_account_id"],
        arguments={
            "query": query,
            "max_results": limit,
            "include_payload": False,
            "verbose": False,
        },
    )
    if not result.get("successful"):
        raise RuntimeError(str(result.get("error") or "Falha ao consultar Gmail"))
    data = result.get("data") or {}
    return data.get("messages") or []

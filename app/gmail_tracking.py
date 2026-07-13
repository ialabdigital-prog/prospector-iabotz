from __future__ import annotations

from datetime import date, datetime, timedelta

from app.composio_gmail import search_messages
from app.config import load_config
from app.db import db
from app.followups import mark_contact_sent, mark_responded
from app.outreach import log_outreach


def _gmail_date(value: str | None) -> str:
    try:
        parsed = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
        return parsed.strftime("%Y/%m/%d")
    except (TypeError, ValueError):
        return (date.today() - timedelta(days=30)).strftime("%Y/%m/%d")


def sync_gmail_replies(slug: str = "todos", on_progress=None) -> dict:
    config = load_config()
    composio = config.get("composio") or {}
    api_key = (composio.get("api_key") or "").strip()
    user_id = (composio.get("entity_id") or "").strip()
    if not api_key:
        raise RuntimeError("Composio API key não configurada")

    with db() as conn:
        sql = """SELECT * FROM leads WHERE status IN ('publicado','proposta')
                 AND COALESCE(email,'') != ''"""
        params = []
        if slug != "todos":
            sql += " AND slug=?"
            params.append(slug)
        leads = [dict(row) for row in conn.execute(sql, params).fetchall()]

    sent_detected = []
    responded = []
    checked = []
    for lead in leads:
        email = lead["email"].strip()
        since = _gmail_date(
            lead.get("emailSentAt") or lead.get("proposalPreparedAt")
            or lead.get("dataProposta") or lead.get("atualizado")
        )
        if on_progress:
            on_progress(f"Verificando Gmail: {lead['nome']}")

        if not lead.get("emailSentAt"):
            sent = search_messages(api_key, user_id, f'in:sent to:"{email}" after:{since}', 5)
            if sent:
                mark_contact_sent(lead["slug"], "email")
                log_outreach(lead["slug"], "email", "sent_detected", email, kind="tracking")
                lead["emailSentAt"] = datetime.now().isoformat(timespec="seconds")
                sent_detected.append(lead["slug"])

        contact_date = lead.get("emailSentAt") or lead.get("dataProposta")
        if contact_date:
            reply_since = _gmail_date(contact_date)
            replies = search_messages(api_key, user_id, f'in:anywhere from:"{email}" after:{reply_since}', 5)
            if replies:
                summary = f"Resposta detectada no Gmail em {date.today().strftime('%d/%m/%Y')}"
                mark_responded(lead["slug"], summary)
                log_outreach(lead["slug"], "email", "replied", email, kind="tracking")
                responded.append(lead["slug"])
        checked.append(lead["slug"])

    return {
        "checked": len(checked),
        "sent_detected": sent_detected,
        "responded": responded,
    }

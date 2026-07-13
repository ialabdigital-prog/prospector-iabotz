from __future__ import annotations

from datetime import datetime, timedelta

from app.db import db


def business_days_since(value: str | None, now: datetime | None = None) -> int:
    if not value:
        return 0
    try:
        start = datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return 0
    end = now or datetime.now()
    days = 0
    cursor = start.date()
    while cursor < end.date():
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            days += 1
    return days


def followup_candidates(slug: str = "todos", minimum_days: int = 3) -> list[dict]:
    with db() as conn:
        sql = """SELECT * FROM leads
                 WHERE status='proposta' AND respondedAt IS NULL"""
        params: list[str] = []
        if slug != "todos":
            sql += " AND slug=?"
            params.append(slug)
        rows = [dict(row) for row in conn.execute(sql, params).fetchall()]

    candidates = []
    for lead in rows:
        email_base = lead.get("emailSentAt") or lead.get("dataProposta")
        whatsapp_base = lead.get("whatsappSentAt") or lead.get("dataWhatsApp") or lead.get("dataProposta")
        email_days = business_days_since(email_base)
        whatsapp_days = business_days_since(whatsapp_base)
        due_email = bool(
            lead.get("email") and email_base and not lead.get("followupEmailAt")
            and email_days >= minimum_days
        )
        due_whatsapp = bool(
            (lead.get("whatsapp") or lead.get("telefone")) and whatsapp_base
            and not lead.get("followupWhatsAppAt") and whatsapp_days >= minimum_days
        )
        if due_email or due_whatsapp:
            lead.update({
                "due_email": due_email,
                "due_whatsapp": due_whatsapp,
                "email_days": email_days,
                "whatsapp_days": whatsapp_days,
            })
            candidates.append(lead)
    return candidates


def mark_contact_sent(slug: str, channel: str, when: str | None = None) -> None:
    field = "emailSentAt" if channel == "email" else "whatsappSentAt"
    legacy = ", dataWhatsApp=COALESCE(dataWhatsApp,?)" if channel == "whatsapp" else ""
    value = when or datetime.now().isoformat(timespec="seconds")
    params = [value]
    if channel == "whatsapp":
        params.append(value)
    params.append(slug)
    with db() as conn:
        conn.execute(
            f"""UPDATE leads SET {field}=COALESCE({field},?){legacy},
                dataProposta=COALESCE(dataProposta,date('now','localtime')),
                status=CASE WHEN status IN ('publicado','proposta') THEN 'proposta' ELSE status END,
                atualizado=datetime('now','localtime') WHERE slug=?""",
            params,
        )


def mark_followup(slug: str, channel: str) -> None:
    field = "followupEmailAt" if channel == "email" else "followupWhatsAppAt"
    with db() as conn:
        conn.execute(
            f"UPDATE leads SET {field}=datetime('now','localtime'), atualizado=datetime('now','localtime') WHERE slug=?",
            (slug,),
        )


def mark_responded(slug: str, summary: str) -> None:
    with db() as conn:
        conn.execute(
            """UPDATE leads SET status='respondeu', respondedAt=datetime('now','localtime'),
               responseSummary=?, obs=CASE WHEN COALESCE(obs,'')='' THEN ? ELSE obs || '\n' || ? END,
               atualizado=datetime('now','localtime') WHERE slug=?""",
            (summary, summary, summary, slug),
        )

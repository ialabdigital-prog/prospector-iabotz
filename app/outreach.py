"""Persistence for outreach attempts, independent from the lead pipeline state."""
from __future__ import annotations

from app.db import db


def log_outreach(
    lead_slug: str,
    channel: str,
    status: str,
    recipient: str = "",
    content: str = "",
    kind: str = "proposta",
    external_id: str = "",
    error: str = "",
) -> None:
    with db() as conn:
        conn.execute(
            """INSERT INTO outreach_log
               (lead_slug, channel, kind, status, recipient, content, external_id, error)
               VALUES (?,?,?,?,?,?,?,?)""",
            (lead_slug, channel, kind, status, recipient, content, external_id, error),
        )

from __future__ import annotations

from datetime import datetime

from app.config import load_config
from app.db import db
from app.jobs.queue import create_job
from app.followups import followup_candidates


def enqueue_scheduled_outreach() -> list[int]:
    automation = load_config().get("automation") or {}
    if not automation.get("followup_enabled"):
        return []
    hour = max(0, min(int(automation.get("followup_hour") or 9), 23))
    if datetime.now().hour < hour:
        return []

    types = []
    if automation.get("response_check_enabled", True):
        types.append("respostas")
    if followup_candidates():
        types.append("followup")
    created = []
    for job_type in types:
        with db() as conn:
            exists = conn.execute(
                """SELECT 1 FROM jobs WHERE type=? AND date(created_at)=date('now','localtime')
                   AND status IN ('queued','running','succeeded') LIMIT 1""",
                (job_type,),
            ).fetchone()
        if not exists:
            created.append(create_job(job_type, {"slug": "todos"}))
    return created

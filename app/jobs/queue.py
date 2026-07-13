"""SQLite job queue."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.db import db, row_to_dict


def create_job(
    job_type: str,
    payload: dict | None = None,
    provider: str | None = None,
    created_by: int | None = None,
) -> int:
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO jobs (type, payload, status, provider, created_by)
               VALUES (?,?, 'queued', ?, ?)""",
            (job_type, json.dumps(payload or {}, ensure_ascii=False), provider, created_by),
        )
        job_id = cur.lastrowid
        claimed = conn.execute(
            "INSERT INTO job_events (job_id, level, message) VALUES (?, 'info', ?)",
            (job_id, f"Job {job_type} enfileirado"),
        )
        return int(job_id)


def append_event(job_id: int, message: str, level: str = "info") -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO job_events (job_id, level, message) VALUES (?,?,?)",
            (job_id, level, message),
        )


def update_job(
    job_id: int,
    *,
    status: str | None = None,
    progress: float | None = None,
    result: Any = None,
    error: str | None = None,
) -> None:
    fields = []
    vals = []
    if status:
        fields.append("status=?")
        vals.append(status)
        if status == "running":
            fields.append("started_at=?")
            vals.append(datetime.now().isoformat(timespec="seconds"))
        if status in ("succeeded", "failed", "cancelled"):
            fields.append("finished_at=?")
            vals.append(datetime.now().isoformat(timespec="seconds"))
    if progress is not None:
        fields.append("progress=?")
        vals.append(progress)
    if result is not None:
        fields.append("result=?")
        vals.append(json.dumps(result, ensure_ascii=False, default=str))
    if error is not None:
        fields.append("error=?")
        vals.append(error)
    if not fields:
        return
    vals.append(job_id)
    with db() as conn:
        conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id=?", vals)


def claim_next_job() -> dict | None:
    with db() as conn:
        row = conn.execute(
            """SELECT * FROM jobs WHERE status='queued'
               ORDER BY id ASC LIMIT 1"""
        ).fetchone()
        if not row:
            return None
        claimed = conn.execute(
            """UPDATE jobs SET status='running', started_at=datetime('now','localtime')
               WHERE id=? AND status='queued'""",
            (row["id"],),
        )
        # More than one worker may wake up at once. Only the worker that
        # successfully changed queued -> running owns this job.
        if claimed.rowcount != 1:
            return None
        return row_to_dict(
            conn.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
        )


def get_job(job_id: int) -> dict | None:
    with db() as conn:
        return row_to_dict(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())


def list_jobs(limit: int = 50, status: str | None = None) -> list[dict]:
    with db() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def list_events(job_id: int, after_id: int = 0) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """SELECT * FROM job_events WHERE job_id=? AND id>? ORDER BY id ASC""",
            (job_id, after_id),
        ).fetchall()
        return [dict(r) for r in rows]


def cancel_job(job_id: int) -> bool:
    with db() as conn:
        cur = conn.execute(
            """UPDATE jobs SET status='cancelled', finished_at=datetime('now','localtime')
               WHERE id=? AND status IN ('queued','running')""",
            (job_id,),
        )
        return cur.rowcount > 0

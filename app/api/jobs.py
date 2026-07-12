from __future__ import annotations

import json
import time

from flask import Blueprint, Response, jsonify, request, session, stream_with_context

from app.jobs import queue as jq

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


@jobs_bp.get("")
def list_jobs():
    status = request.args.get("status")
    return jsonify(jq.list_jobs(limit=int(request.args.get("limit") or 50), status=status))


@jobs_bp.post("")
def create_job():
    data = request.json or {}
    job_type = data.get("type")
    if not job_type:
        return jsonify({"error": "type obrigatório"}), 400
    job_id = jq.create_job(
        job_type,
        payload=data.get("payload") or data,
        provider=data.get("provider"),
        created_by=session.get("user_id"),
    )
    return jsonify({"success": True, "id": job_id})


@jobs_bp.get("/<int:job_id>")
def get_job(job_id: int):
    job = jq.get_job(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    job["events"] = jq.list_events(job_id)
    return jsonify(job)


@jobs_bp.post("/<int:job_id>/cancel")
def cancel(job_id: int):
    ok = jq.cancel_job(job_id)
    jq.append_event(job_id, "Cancelamento solicitado", "warn")
    return jsonify({"success": ok})


@jobs_bp.get("/<int:job_id>/events")
def events_sse(job_id: int):
    def generate():
        last = int(request.args.get("after") or 0)
        idle = 0
        while idle < 120:  # ~4 min @ 2s
            events = jq.list_events(job_id, after_id=last)
            job = jq.get_job(job_id)
            for ev in events:
                last = ev["id"]
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            if job and job.get("status") in ("succeeded", "failed", "cancelled"):
                yield f"data: {json.dumps({'done': True, 'status': job['status']})}\n\n"
                break
            if not events:
                idle += 1
                yield ": keepalive\n\n"
            else:
                idle = 0
            time.sleep(2)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

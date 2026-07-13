#!/usr/bin/env python3
"""Background worker — claim and run queued jobs."""
from __future__ import annotations

import sys
import time
import fcntl
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import init_db
from app.jobs import queue as jq
from app.jobs.runners import run_job


def main():
    lock_path = ROOT / ".prospector-worker.lock"
    lock_file = lock_path.open("w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Prospector worker already running; exiting duplicate", flush=True)
        return
    init_db()
    print("Prospector worker started", flush=True)
    while True:
        job = jq.claim_next_job()
        if not job:
            time.sleep(2)
            continue
        print(f"Running job #{job['id']} {job['type']}", flush=True)
        run_job(job)


if __name__ == "__main__":
    main()

"""SQLite schema and helpers."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from app.config import DB_FILE, LEADS_FILE


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        c = conn.cursor()
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS leads(
              slug TEXT PRIMARY KEY, nome TEXT, nicho TEXT, cidade TEXT, nota REAL, avaliacoes INTEGER,
              email TEXT, telefone TEXT, whatsapp TEXT, siteAntigo TEXT, motivo TEXT,
              status TEXT DEFAULT 'novo', urlNova TEXT, dataProposta TEXT, valor REAL, obs TEXT,
              contratoStatus TEXT DEFAULT 'pendente', contratoEm TEXT, manutencao REAL, pago INTEGER DEFAULT 0,
              docCliente TEXT, endCliente TEXT, placeId TEXT, engine TEXT,
              atualizado TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS users(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL,
              created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS jobs(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              type TEXT NOT NULL,
              payload TEXT NOT NULL DEFAULT '{}',
              status TEXT NOT NULL DEFAULT 'queued',
              progress REAL DEFAULT 0,
              result TEXT,
              error TEXT,
              provider TEXT,
              created_by INTEGER,
              created_at TEXT DEFAULT (datetime('now','localtime')),
              started_at TEXT,
              finished_at TEXT
            );

            CREATE TABLE IF NOT EXISTS job_events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              job_id INTEGER NOT NULL,
              level TEXT DEFAULT 'info',
              message TEXT NOT NULL,
              created_at TEXT DEFAULT (datetime('now','localtime')),
              FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audit_log(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER,
              action TEXT NOT NULL,
              detail TEXT,
              created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS outreach_log(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              lead_slug TEXT NOT NULL,
              channel TEXT NOT NULL,
              kind TEXT NOT NULL DEFAULT 'proposta',
              status TEXT NOT NULL,
              recipient TEXT,
              content TEXT,
              external_id TEXT,
              error TEXT,
              created_at TEXT DEFAULT (datetime('now','localtime')),
              FOREIGN KEY(lead_slug) REFERENCES leads(slug) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events(job_id);
            CREATE INDEX IF NOT EXISTS idx_outreach_lead ON outreach_log(lead_slug, created_at DESC);
            """
        )
        # soft migrations for older DBs
        cols = {r[1] for r in c.execute("PRAGMA table_info(leads)").fetchall()}
        if "placeId" not in cols:
            c.execute("ALTER TABLE leads ADD COLUMN placeId TEXT")
        if "engine" not in cols:
            c.execute("ALTER TABLE leads ADD COLUMN engine TEXT")
        if "dataWhatsApp" not in cols:
            c.execute("ALTER TABLE leads ADD COLUMN dataWhatsApp TEXT")

        c.execute("SELECT COUNT(*) FROM leads")
        if c.fetchone()[0] == 0:
            _import_leads_md(c)


def _import_leads_md(c: sqlite3.Cursor) -> None:
    if not LEADS_FILE.exists():
        return
    for line in LEADS_FILE.read_text(encoding="utf-8").split("\n"):
        if "|" not in line or line.startswith("| #") or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.split("|")]
        # table rows often have empty first/last from leading/trailing |
        parts = [p for p in parts if p != "" or True]
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 10:
            continue
        nome = parts[1] if parts[0].isdigit() or parts[0] == "#" else parts[0]
        # standard leads.md: # | Nome | Nota | Aval. | E-mail | Telefone | WhatsApp | Site | Motivo | Status | URL
        try:
            if parts[0].replace(".", "").isdigit() or parts[0].isdigit():
                nome, nota, aval, email, tel, wa, site, motivo, status, url = (
                    parts[1],
                    parts[2],
                    parts[3],
                    parts[4],
                    parts[5],
                    parts[6],
                    parts[7],
                    parts[8],
                    parts[9],
                    parts[10] if len(parts) > 10 else "",
                )
            else:
                continue
        except IndexError:
            continue
        slug = _slugify(nome)
        c.execute(
            """INSERT OR IGNORE INTO leads
            (slug,nome,nota,avaliacoes,email,telefone,whatsapp,siteAntigo,motivo,status,urlNova,atualizado)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                slug,
                nome,
                _float(nota),
                _int(aval),
                email,
                tel,
                wa,
                site,
                motivo,
                status or "novo",
                url,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def _slugify(nome: str, site_url: str = "") -> str:
    import re
    import unicodedata
    import hashlib
    from urllib.parse import urlparse

    # A real business domain is a concise, recognizable public identifier.
    # Prefer it over a long Maps display name whenever it is available.
    host = ""
    if site_url:
        parsed = urlparse(site_url if "://" in site_url else f"https://{site_url}")
        host = (parsed.hostname or "").lower().removeprefix("www.")
    if host:
        # www.clinica.example.br -> clinica; avoid TLD-only labels.
        label = host.split(".")[0]
        if label and label not in {"www", "site", "home"}:
            nome = label

    s = unicodedata.normalize("NFKD", nome)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if not s:
        return "lead"
    # DNS labels are limited to 63 bytes. Keep a readable prefix plus a stable
    # hash so two long business names cannot collide on a customer subdomain.
    if len(s) > 55:
        digest = hashlib.sha1(s.encode("utf-8")).hexdigest()[:7]
        s = f"{s[:47].rstrip('-')}-{digest}"
    return s


def _float(v: Any) -> float:
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return 0.0


def _int(v: Any) -> int:
    try:
        return int(float(str(v).replace(",", ".")))
    except Exception:
        return 0


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)

"""Job runners — wire discovery + existing skill scripts."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.config import BASE_DIR
from app.discovery import run_prospecting
from app.jobs import queue as jq
from app.llm.router import complete as llm_complete


def run_job(job: dict) -> None:
    job_id = job["id"]
    job_type = job["type"]
    payload = json.loads(job.get("payload") or "{}")
    provider = job.get("provider")

    def log(msg: str, level: str = "info"):
        jq.append_event(job_id, msg, level)
        # cancel check
        current = jq.get_job(job_id)
        if current and current.get("status") == "cancelled":
            raise RuntimeError("cancelled")

    try:
        jq.update_job(job_id, status="running", progress=0.05)
        if job_type == "prospectar":
            result = _run_prospectar(payload, log)
        elif job_type == "publicar":
            slug = payload.get("slug") or "todos"
            if slug != "todos":
                site_dir = BASE_DIR / "sites" / slug
                if not site_dir.exists():
                    raise RuntimeError(
                        f"Site ainda não redesenhado: falta sites/{slug}/. "
                        f"Rode primeiro o job «redesenhar» para este lead."
                    )
            result = _run_script(
                "skills/deploy-aapanel/references/deploy.py",
                slug,
                log,
            )
        elif job_type == "redesenhar":
            result = _run_script(
                "skills/redesign-premium/references/redesign.py",
                payload.get("slug") or "todos",
                log,
                provider=provider,
                enrich=True,
            )
        elif job_type == "proposta":
            result = _run_proposta(payload, log, provider)
        elif job_type == "followup":
            result = _run_script(
                "skills/proposta-email/references/followup.py",
                payload.get("slug") or "todos",
                log,
            )
        elif job_type == "contrato":
            result = _run_contrato(payload, log)
        else:
            raise RuntimeError(f"Tipo de job desconhecido: {job_type}")

        jq.update_job(job_id, status="succeeded", progress=1.0, result=result)
        log("Concluído com sucesso", "success")
    except Exception as e:
        if str(e) == "cancelled":
            log("Job cancelado", "warn")
            return
        jq.update_job(job_id, status="failed", error=str(e))
        log(f"Falhou: {e}", "error")


def _run_prospectar(payload: dict, log) -> dict:
    return run_prospecting(
        nicho=payload.get("nicho") or "nutricionistas",
        cidade=payload.get("cidade") or "São Paulo",
        meta=int(payload.get("meta") or 10),
        nota_min=float(payload.get("notaMinima") or 4.7),
        aval_min=int(payload.get("avaliacoesMinimas") or 40),
        raio_km=int(payload.get("raioKm") or 15),
        engine=payload.get("engine"),
        on_progress=log,
    )


def _run_script(rel_path: str, slug: str, log, provider=None, enrich=False) -> dict:
    script = BASE_DIR / rel_path
    if not script.exists():
        raise FileNotFoundError(script)
    if enrich and provider:
        log(f"LLM provider selecionado: {provider} (copy pós-template se disponível)")
    log(f"Executando {rel_path} {slug}")
    proc = subprocess.Popen(
        [sys.executable, str(script), slug],
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"Script exit {code}")
    return {"slug": slug, "exit": code}


def _run_proposta(payload: dict, log, provider: str | None) -> dict:
    slug = payload.get("slug") or "todos"
    if provider and slug != "todos":
        try:
            from app.db import db

            with db() as conn:
                lead = conn.execute("SELECT * FROM leads WHERE slug=?", (slug,)).fetchone()
            if lead:
                log("Gerando texto de proposta via LLM…")
                text = llm_complete(
                    provider,
                    system=(
                        "Você escreve e-mails curtos de proposta de redesign de site. "
                        "120-180 palavras, rapport específico, sem preço, 1 CTA, pt-BR."
                    ),
                    prompt=(
                        f"Lead: {lead['nome']}, nota {lead['nota']} ({lead['avaliacoes']} aval.). "
                        f"Site atual: {lead['siteAntigo']}. Motivo: {lead['motivo']}. "
                        f"URL nova: {lead['urlNova']}. Escreva assunto + corpo."
                    ),
                )
                drafts = BASE_DIR / "drafts"
                drafts.mkdir(exist_ok=True)
                (drafts / f"{slug}-proposta.txt").write_text(text, encoding="utf-8")
                log(f"Rascunho LLM salvo em drafts/{slug}-proposta.txt")
        except Exception as e:
            log(f"LLM proposta falhou (seguindo script): {e}", "warn")
    return _run_script("skills/proposta-email/references/proposta.py", slug, log)


def _run_contrato(payload: dict, log) -> dict:
    script = BASE_DIR / "skills/contrato-servico/references/contrato.py"
    if not script.exists():
        raise FileNotFoundError(script)
    slug = payload.get("slug")
    if not slug:
        raise RuntimeError("contrato exige slug")
    args = [sys.executable, str(script), slug]
    for flag, key in (
        ("--valor", "valor"),
        ("--entrada", "entrada"),
        ("--parcelas", "parcelas"),
        ("--manutencao", "manutencao"),
    ):
        if payload.get(key) is not None:
            args += [flag, str(payload[key])]
    log(" ".join(args))
    proc = subprocess.run(args, cwd=str(BASE_DIR), capture_output=True, text=True)
    if proc.stdout:
        for line in proc.stdout.splitlines():
            log(line)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or f"exit {proc.returncode}")
    return {"slug": slug, "exit": 0}

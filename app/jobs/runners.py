"""Job runners — wire discovery + existing skill scripts."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.config import BASE_DIR, load_config
from app.discovery import run_prospecting
from app.jobs import queue as jq


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
            result = _run_followup(payload, log)
        elif job_type == "respostas":
            from app.gmail_tracking import sync_gmail_replies
            result = sync_gmail_replies(payload.get("slug") or "todos", on_progress=log)
        elif job_type == "contrato":
            result = _run_contrato(payload, log)
        else:
            raise RuntimeError(f"Tipo de job desconhecido: {job_type}")

        _enqueue_automation(job_type, result, provider, log)

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
        lat=float(payload["lat"]) if payload.get("lat") not in (None, "") else None,
        lng=float(payload["lng"]) if payload.get("lng") not in (None, "") else None,
        candidate_limit=int(payload.get("candidateLimit") or 0) or None,
        quality_mode=payload.get("siteQuality") or None,
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
    results = []
    for line in proc.stdout:
        line = line.rstrip()
        if line.startswith("RESULT_JSON:"):
            try:
                results.append(json.loads(line.removeprefix("RESULT_JSON:")))
            except json.JSONDecodeError:
                log("Resultado estruturado inválido", "warn")
        elif line:
            log(line)
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"Script exit {code}")
    return {"slug": slug, "exit": code, "results": results}


def _run_proposta(payload: dict, log, provider: str | None) -> dict:
    slug = payload.get("slug") or "todos"
    log("Preparando outreach nos canais configurados…")
    canais = (load_config().get("envio") or {}).get("canais") or ["email"]
    results = []
    if "email" in canais:
        output = _run_script("skills/proposta-email/references/proposta.py", slug, log)
        results.extend(output.get("results") or [])
    if "whatsapp" in canais:
        output = _run_script("skills/proposta-whatsapp/references/proposta_whatsapp.py", slug, log)
        results.extend(output.get("results") or [])
    if not results:
        raise RuntimeError("Nenhum resultado de outreach foi produzido para os canais ativos")
    return {"slug": slug, "channels": results, "exit": 0}


def _run_followup(payload: dict, log) -> dict:
    slug = payload.get("slug") or "todos"
    config = load_config()
    channels = (config.get("envio") or {}).get("canais") or ["email"]
    results = []
    if "email" in channels:
        try:
            from app.gmail_tracking import sync_gmail_replies
            tracking = sync_gmail_replies(slug, on_progress=log)
            if tracking.get("responded"):
                log(f"Respostas detectadas antes do follow-up: {len(tracking['responded'])}", "success")
        except Exception as exc:
            log(f"Não foi possível verificar respostas no Gmail: {exc}", "warn")
        output = _run_script("skills/proposta-email/references/followup.py", slug, log)
        results.extend(output.get("results") or [])
    if "whatsapp" in channels:
        output = _run_script("skills/proposta-whatsapp/references/followup_whatsapp.py", slug, log)
        results.extend(output.get("results") or [])
    return {"slug": slug, "channels": results, "kind": "followup", "exit": 0}


def _enqueue_automation(job_type: str, result: dict, provider: str | None, log) -> None:
    """Encadeia o funil somente quando o piloto automático estiver explicitamente ativo."""
    automation = load_config().get("automation") or {}
    if not automation.get("enabled"):
        return

    if job_type == "prospectar" and automation.get("redesign", True):
        for lead in result.get("qualified") or []:
            jq.create_job("redesenhar", {"slug": lead["slug"]}, provider=provider)
            log(f"Autopilot: redesign enfileirado para {lead['nome']}")
    elif job_type == "redesenhar" and automation.get("publish", True):
        slug = result.get("slug")
        if slug and slug != "todos":
            jq.create_job("publicar", {"slug": slug}, provider=provider)
            log(f"Autopilot: publicação enfileirada para {slug}")
    elif job_type == "publicar" and automation.get("outreach", False):
        slug = result.get("slug")
        if slug and slug != "todos":
            jq.create_job("proposta", {"slug": slug}, provider=provider)
            log(f"Autopilot: proposta enfileirada para {slug}")


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

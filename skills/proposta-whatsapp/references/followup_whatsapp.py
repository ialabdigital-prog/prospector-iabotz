"""Create or send one WhatsApp follow-up after three business days."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BASE_DIR))

from app.config import load_config
from app.followups import followup_candidates, mark_followup
from app.outreach import log_outreach
from proposta_whatsapp import (
    send_via_evolution_api,
    send_via_evolution_go,
)


def message_for(lead: dict, config: dict) -> str:
    first_name = (lead.get("nome") or "Olá").split()[0]
    url = f"{(lead.get('urlNova') or '').rstrip('/')}/proposta.html"
    sender = (config.get("assinatura") or {}).get("nome", "")
    return (
        f"Oi {first_name}, te mandei há alguns dias a nova versão do site. "
        f"Conseguiu dar uma olhada?\n{url}\n\n"
        f"Se não for o momento, sem problemas. É só me avisar.\n\n{sender}"
    ).strip()


def save_local(lead: dict, text: str) -> Path:
    folder = BASE_DIR / "drafts"
    folder.mkdir(exist_ok=True)
    path = folder / f"followup_whatsapp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{lead['slug']}.txt"
    path.write_text(f"Para: {lead['nome']} ({lead.get('whatsapp') or lead.get('telefone')})\n---\n{text}", encoding="utf-8")
    return path


async def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "todos"
    config = load_config()
    candidates = [lead for lead in followup_candidates(target) if lead.get("due_whatsapp")]
    if not candidates:
        result = {"channel": "whatsapp", "status": "not_due", "sent": False, "message": "Nenhum follow-up WhatsApp devido"}
        print("✅ Nenhum follow-up WhatsApp devido")
        print("RESULT_JSON:" + json.dumps(result, ensure_ascii=False))
        return

    envio = config.get("envio") or {}
    wa = envio.get("whatsapp") or {}
    provider = wa.get("provedor") or "evolution_api"
    draft_only = (envio.get("modo") or "rascunho") != "envio"
    for lead in candidates:
        text = message_for(lead, config)
        number = "".join(ch for ch in (lead.get("whatsapp") or lead.get("telefone") or "") if ch.isdigit())
        result = None
        if not draft_only:
            result = send_via_evolution_go(config, number, text) if provider == "evolution_go" else send_via_evolution_api(config, number, text)
        if result and result.get("success"):
            status, location, sent, local, error = "sent", "Evolution API", True, None, ""
        else:
            local = save_local(lead, text)
            error = (result or {}).get("error", "")
            status = "failed_local_draft" if result else "local_draft"
            location, sent = "Painel > Mensagens", False
        mark_followup(lead["slug"], "whatsapp")
        log_outreach(lead["slug"], "whatsapp", status, number, text, kind="followup", error=error)
        payload = {
            "channel": "whatsapp", "status": status, "sent": sent,
            "location": location, "draft_file": str(local) if local else "",
            "error": error, "kind": "followup",
        }
        print(f"✅ {lead['nome']}: follow-up {'enviado' if sent else 'preparado como rascunho'}")
        print(f"   Enviado: {'SIM' if sent else 'NÃO'}")
        print("RESULT_JSON:" + json.dumps(payload, ensure_ascii=False))
        if sent:
            time.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())

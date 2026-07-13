"""Create one email follow-up draft after three business days without a reply."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BASE_DIR))

from app.composio_gmail import create_draft
from app.config import load_config
from app.followups import followup_candidates, mark_followup
from app.outreach import log_outreach


def generate_followup(lead: dict, config: dict) -> tuple[str, str]:
    first_name = (lead.get("nome") or "Olá").split()[0]
    signature = config.get("assinatura") or {}
    proposal_url = f"{(lead.get('urlNova') or '').rstrip('/')}/proposta.html"
    subject = f"Re: {first_name}, conseguiu ver a página?"[:60]
    body = f"""<p>Oi {first_name},</p>
<p>Te escrevi há alguns dias sobre a nova versão do site. Conseguiu dar uma olhada?</p>
<p><a href="{proposal_url}">{proposal_url}</a></p>
<p>Se não for o momento, sem problemas. É só me avisar.</p>
<p>{signature.get('nome', '')}<br>{signature.get('apresentacao', '')}</p>"""
    return subject, body


def save_local(lead: dict, subject: str, body: str, storage: str) -> Path:
    draft_dir = BASE_DIR / "drafts"
    draft_dir.mkdir(exist_ok=True)
    path = draft_dir / f"followup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{lead['slug']}.html"
    path.write_text(
        f"<!doctype html><html><head><meta charset=utf-8><title>{subject}</title></head><body>"
        f"<p><strong>Para:</strong> {lead['email']}<br><strong>Assunto:</strong> {subject}<br>"
        f"<strong>Modo:</strong> {storage}</p><hr>{body}</body></html>",
        encoding="utf-8",
    )
    return path


async def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "todos"
    config = load_config()
    candidates = [lead for lead in followup_candidates(target) if lead.get("due_email")]
    if not candidates:
        result = {"channel": "email", "status": "not_due", "sent": False, "message": "Nenhum follow-up de e-mail devido"}
        print("✅ Nenhum follow-up de e-mail devido")
        print("RESULT_JSON:" + json.dumps(result, ensure_ascii=False))
        return

    composio = config.get("composio") or {}
    for lead in candidates:
        subject, body = generate_followup(lead, config)
        gmail = None
        error = ""
        try:
            gmail = create_draft(
                (composio.get("api_key") or "").strip(),
                (composio.get("entity_id") or "").strip(),
                lead["email"], subject, body,
            )
        except Exception as exc:
            error = str(exc)
        status = "gmail_draft" if gmail else "local_draft"
        location = "Gmail > Rascunhos" if gmail else "Painel > Mensagens"
        local = save_local(lead, subject, body, "Gmail + cópia local" if gmail else "Somente cópia local")
        mark_followup(lead["slug"], "email")
        log_outreach(
            lead["slug"], "email", status, lead["email"], body, kind="followup",
            external_id=(gmail or {}).get("draft_id", ""), error=error,
        )
        result = {
            "channel": "email", "status": status, "sent": False,
            "location": location, "draft_file": str(local),
            "fallback_reason": error, "kind": "followup",
        }
        print(f"✅ {lead['nome']}: follow-up criado em {location}")
        print("   Enviado: NÃO")
        if error:
            print(f"   Motivo do fallback: {error}")
        print("RESULT_JSON:" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

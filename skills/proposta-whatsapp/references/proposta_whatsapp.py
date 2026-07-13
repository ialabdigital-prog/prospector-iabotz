#!/usr/bin/env python3
"""
Proposta WhatsApp - Envia proposta comercial via Evolution API ou Evolution Go
"""

import sys
import os
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))


def load_config() -> Dict:
    config_file = BASE_DIR / "prospector-config.json"
    if not config_file.exists():
        return {}
    return json.loads(config_file.read_text(encoding="utf-8"))


def load_leads() -> List[Dict]:
    db_file = BASE_DIR / "prospector.db"
    if db_file.exists():
        import sqlite3
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM leads ORDER BY atualizado DESC").fetchall()
        conn.close()
        return [
            {
                "slug": r["slug"],
                "nome": r["nome"] or "",
                "nicho": r["nicho"] or "",
                "cidade": r["cidade"] or "",
                "nota": r["nota"],
                "avaliacoes": r["avaliacoes"],
                "email": r["email"] or "",
                "telefone": r["telefone"] or "",
                "whatsapp": r["whatsapp"] or "",
                "site_atual": r["siteAntigo"] or "",
                "motivo": r["motivo"] or "",
                "status": r["status"] or "",
                "url_nova": r["urlNova"] or "",
            }
            for r in rows
        ]

    leads_file = BASE_DIR / "leads.md"
    if not leads_file.exists():
        return []
    leads = []
    content = leads_file.read_text(encoding="utf-8")
    for line in content.split("\n"):
        if "|" in line and not line.startswith("| #") and not line.startswith("|---"):
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) >= 10:
                leads.append({
                    "slug": parts[1].lower().replace(" ", "-") if parts[0].isdigit() else parts[0],
                    "nome": parts[1] if parts[0].isdigit() else parts[0],
                    "email": parts[4] if len(parts) > 4 else "",
                    "status": parts[9] if len(parts) > 9 else "",
                    "url_nova": parts[10] if len(parts) > 10 else "",
                    "site_atual": parts[7] if len(parts) > 7 else "",
                    "motivo": parts[8] if len(parts) > 8 else "",
                    "whatsapp": parts[6] if len(parts) > 6 else "",
                    "nicho": "",
                    "cidade": "",
                })
    return leads


def mark_prepared(slug: str) -> None:
    db_file = BASE_DIR / "prospector.db"
    if not db_file.exists():
        return
    import sqlite3
    conn = sqlite3.connect(db_file)
    conn.execute(
        """UPDATE leads SET proposalPreparedAt=datetime('now','localtime'),
           atualizado=datetime('now','localtime') WHERE slug=?""",
        (slug,),
    )
    conn.commit()
    conn.close()


def generate_whatsapp_message(lead: Dict, config: Dict) -> str:
    assinatura = config.get("assinatura", {})
    nome = assinatura.get("nome", "")
    apresentacao = assinatura.get("apresentacao", "")
    whatsapp_sender = assinatura.get("whatsapp", "")

    primeiro_nome = lead["nome"].split()[0] if lead["nome"] else "Olá"
    url_proposta = f"{lead['url_nova']}proposta.html" if lead.get("url_nova") else ""
    motivos = lead["motivo"].split("; ") if "; " in lead["motivo"] else [lead["motivo"]]
    motivo1 = motivos[0] if motivos else "o site não reflete a qualidade do trabalho"
    motivo2 = motivos[1] if len(motivos) > 1 else "faltam informações para o cliente agendar"

    msg = (
        f"Olá {primeiro_nome}, tudo bem?\n\n"
        f"Vi a {lead['nome']} no Google Maps com {lead['avaliacoes']} avaliações e nota {lead['nota']} — "
        f"impressionante! Mas dando uma olhada no site, notei que {motivo1.lower()} e {motivo2.lower()}.\n\n"
        f"Preparei uma nova versão completa do site, já no ar. Dá uma olhada:\n"
        f"{url_proposta}\n\n"
        f"Abra no celular também — o layout se adapta.\n\n"
        f"Se gostar, a gente conversa sobre valores. Sem pressão.\n\n"
        f"{nome}\n{apresentacao}"
    )
    return msg.strip()


def send_via_evolution_api(config: Dict, number: str, text: str) -> Dict:
    wa = config.get("envio", {}).get("whatsapp", {})
    evo = wa.get("evolution_api", {})
    url = evo.get("url", "").rstrip("/")
    api_key = evo.get("api_key", "")
    instance = evo.get("instance", "prospector")

    if not url or not api_key:
        return {"success": False, "error": "Evolution API não configurada"}

    endpoint = f"{url}/message/sendText/{instance}"
    body = json.dumps({
        "number": number,
        "text": text,
        "linkPreview": True,
        "delay": 2000,
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "apikey": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return {"success": True, "result": result}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        return {"success": False, "error": f"HTTP {e.code}: {error_body}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_via_evolution_go(config: Dict, number: str, text: str) -> Dict:
    wa = config.get("envio", {}).get("whatsapp", {})
    evo = wa.get("evolution_go", {})
    url = evo.get("url", "").rstrip("/")
    api_key = evo.get("api_key", "")

    if not url or not api_key:
        return {"success": False, "error": "Evolution Go não configurado"}

    endpoint = f"{url}/send/text"
    body = json.dumps({
        "number": number,
        "text": text,
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "apikey": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return {"success": True, "result": result}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        return {"success": False, "error": f"HTTP {e.code}: {error_body}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_whatsapp(lead: Dict, config: Dict) -> Dict:
    wa = config.get("envio", {}).get("whatsapp", {})
    provedor = wa.get("provedor", "evolution_api")
    number = lead.get("whatsapp", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    if not number:
        return {"success": False, "error": "Lead sem WhatsApp"}

    text = generate_whatsapp_message(lead, config)

    if provedor == "evolution_go":
        return send_via_evolution_go(config, number, text)
    else:
        return send_via_evolution_api(config, number, text)


def log_attempt(lead: Dict, result: Dict, text: str) -> None:
    try:
        from app.outreach import log_outreach

        response = result.get("result") or {}
        key = response.get("key") or response.get("data", {}).get("Info", {}) or {}
        external_id = key.get("id") or key.get("ID") or ""
        log_outreach(
            lead["slug"],
            "whatsapp",
            "sent" if result.get("success") else "failed",
            lead.get("whatsapp", ""),
            text,
            external_id=external_id,
            error=result.get("error", ""),
        )
    except Exception:
        pass


def save_draft(lead: Dict, text: str) -> str:
    draft_dir = BASE_DIR / "drafts"
    draft_dir.mkdir(exist_ok=True)
    draft_file = draft_dir / f"whatsapp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{lead['slug']}.txt"
    content = f"""Para: {lead['nome']} ({lead['whatsapp']})
---
{text}
"""
    draft_file.write_text(content, encoding="utf-8")
    return str(draft_file)


async def main():
    if len(sys.argv) < 2:
        print("Uso: python3 proposta_whatsapp.py <slug|todos>")
        sys.exit(1)

    target = sys.argv[1]
    config = load_config()
    wa = config.get("envio", {}).get("whatsapp", {})
    provedor = wa.get("provedor", "evolution_api")
    draft_only = (config.get("envio", {}).get("modo") or "rascunho") != "envio"

    leads = load_leads()
    if not leads:
        print("⚠️  Nenhum lead encontrado")
        return

    if target == "todos":
        targets = [l for l in leads if l["whatsapp"] and l["whatsapp"].strip()]
    else:
        targets = [l for l in leads if l["slug"] == target and l.get("whatsapp") and l["whatsapp"].strip()]

    if not targets:
        print("⚠️  Nenhum lead com WhatsApp encontrado")
        return

    print(f"\n📱 {'Gerando rascunhos' if draft_only else 'Enviando propostas'} via WhatsApp para {len(targets)} lead(s)...\n")
    print(f"   Provedor: {provedor}\n")

    for lead in targets:
        if not lead.get("whatsapp"):
            print(f"⚠️  {lead['nome']}: sem WhatsApp cadastrado — pulando")
            continue

        text = generate_whatsapp_message(lead, config)
        if draft_only:
            draft_file = save_draft(lead, text)
            print(f"✅ {lead['nome']}: rascunho WhatsApp criado")
            print("   Enviado: NÃO")
            print("   Local: Painel > E-mails e Outreach")
            print(f"   Arquivo: {Path(draft_file).name}")
            result = {
                "success": True,
                "channel": "whatsapp",
                "status": "local_draft",
                "sent": False,
                "location": "Painel > E-mails e Outreach",
                "draft_file": draft_file,
                "message": "Mensagem pronta para revisão; nenhuma mensagem foi enviada.",
            }
            try:
                from app.outreach import log_outreach
                log_outreach(lead["slug"], "whatsapp", "local_draft", lead.get("whatsapp", ""), text)
            except Exception:
                pass
            mark_prepared(lead["slug"])
            print("RESULT_JSON:" + json.dumps(result, ensure_ascii=False))
            continue

        result = send_whatsapp(lead, config)
        log_attempt(lead, result, text)

        if result["success"]:
            print(f"✅ {lead['nome']}: WhatsApp enviado com sucesso")
            print("   Enviado: SIM")
            response = result.get("result") or {}
            key = response.get("key") or response.get("data", {}).get("Info", {}) or {}
            result.update({
                "channel": "whatsapp",
                "status": "sent",
                "sent": True,
                "location": "Evolution API",
                "external_id": key.get("id") or key.get("ID") or "",
            })
            from app.followups import mark_contact_sent
            mark_contact_sent(lead["slug"], "whatsapp")
        else:
            print(f"⚠️  {lead['nome']}: {result.get('error', 'erro desconhecido')}")
            draft_file = save_draft(lead, text)
            print("   Enviado: NÃO")
            print(f"   Arquivo: {Path(draft_file).name}")
            result.update({
                "channel": "whatsapp",
                "status": "failed_local_draft",
                "sent": False,
                "location": "Painel > E-mails e Outreach",
                "draft_file": draft_file,
            })

        print("RESULT_JSON:" + json.dumps(result, ensure_ascii=False))

        time.sleep(5)

    print(f"\n📱 {len(targets)} lead(s) processado(s)")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

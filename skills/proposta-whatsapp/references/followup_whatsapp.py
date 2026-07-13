#!/usr/bin/env python3
"""
Follow-up WhatsApp - Envia follow-up para leads que não responderam à proposta via WhatsApp
"""

import sys
import os
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List
from datetime import datetime, timedelta

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
                "whatsapp": r["whatsapp"] or "",
                "status": r["status"] or "",
                "url_nova": r["urlNova"] or "",
                "dataWhatsApp": r["dataWhatsApp"] or "",
            }
            for r in rows
        ]
    return []


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
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json", "apikey": api_key},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {"success": True, "result": json.loads(resp.read().decode("utf-8"))}
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.read().decode('utf-8')}"}
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
    body = json.dumps({"number": number, "text": text}).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json", "apikey": api_key},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {"success": True, "result": json.loads(resp.read().decode("utf-8"))}
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.read().decode('utf-8')}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_followup_message(lead: Dict, config: Dict) -> str:
    assinatura = config.get("assinatura", {})
    primeiro_nome = lead["nome"].split()[0] if lead["nome"] else "Olá"
    url_proposta = f"{lead['url_nova']}proposta.html" if lead.get("url_nova") else ""

    return (
        f"Oi {primeiro_nome}, só passando pra saber se conseguiu dar uma olhada "
        f"na nova versão do site que preparei:\n"
        f"{url_proposta}\n\n"
        f"Qualquer dúvida é só chamar. Se não for o momento, sem problemas — é só avisar.\n\n"
        f"{assinatura.get('nome', '')}"
    ).strip()


def is_followup_due(lead: Dict) -> bool:
    if lead["status"] not in ("proposta",):
        return False
    if not lead.get("dataWhatsApp"):
        return False
    try:
        data_envio = datetime.fromisoformat(lead["dataWhatsApp"])
    except (ValueError, TypeError):
        return False
    dias = (datetime.now() - data_envio).days
    return dias >= 3


def save_draft(lead: Dict, text: str) -> str:
    draft_dir = BASE_DIR / "drafts"
    draft_dir.mkdir(exist_ok=True)
    draft_file = draft_dir / f"followup_whatsapp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{lead['slug']}.txt"
    draft_file.write_text(f"Para: {lead['nome']} ({lead['whatsapp']})\n---\n{text}", encoding="utf-8")
    return str(draft_file)


async def main():
    if len(sys.argv) < 2:
        print("Uso: python3 followup_whatsapp.py [slug|todos]")
        sys.exit(1)

    target = sys.argv[1]
    config = load_config()
    wa = config.get("envio", {}).get("whatsapp", {})
    provedor = wa.get("provedor", "evolution_api")

    leads = load_leads()
    if not leads:
        print("⚠️  Nenhum lead encontrado")
        return

    if target == "todos":
        targets = [l for l in leads if is_followup_due(l) and l.get("whatsapp") and l["whatsapp"].strip()]
    else:
        targets = [l for l in leads if l["slug"] == target and is_followup_due(l)]

    if not targets:
        print("✅ Nenhum follow-up devido no momento")
        return

    print(f"\n📱 Gerando follow-ups WhatsApp para {len(targets)} lead(s)...\n")
    print(f"   Provedor: {provedor}\n")

    for lead in targets:
        if not lead.get("whatsapp"):
            print(f"⚠️  {lead['nome']}: sem WhatsApp cadastrado — pulando")
            continue

        text = generate_followup_message(lead, config)
        number = lead["whatsapp"].replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

        if provedor == "evolution_go":
            result = send_via_evolution_go(config, number, text)
        else:
            result = send_via_evolution_api(config, number, text)

        if result["success"]:
            print(f"✅ {lead['nome']}: follow-up enviado")
        else:
            print(f"⚠️  {lead['nome']}: {result.get('error', 'erro')}")
            draft_file = save_draft(lead, text)
            print(f"   → Mensagem salva em: {draft_file}")

        time.sleep(5)

    print(f"\n📱 {len(targets)} follow-up(s) processado(s)")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

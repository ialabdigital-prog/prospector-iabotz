#!/usr/bin/env python3
"""
Publicador automático para aapanel
Roda como serviço (systemd/cron) verificando fila de publicação a cada 60s
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent.parent.parent
CONFIG_FILE = BASE_DIR / "prospector-config.json"
QUEUE_FILE = BASE_DIR / "fila-publicacao.txt"
LOG_FILE = BASE_DIR / "publicador-log.txt"

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}

def run_rsync(local_dir, remote_host, remote_user, remote_path):
    """Deploy via rsync sobre SSH"""
    cmd = [
        "rsync", "-avz", "--delete",
        "-e", "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
        f"{local_dir}/",
        f"{remote_user}@{remote_host}:{remote_path}/"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout (120s)"
    except Exception as e:
        return False, "", str(e)

def process_queue():
    """Processa fila de publicação"""
    if not QUEUE_FILE.exists():
        return
    
    config = load_config()
    aapanel = config.get("aapanel", {})
    
    if not aapanel.get("url") or not aapanel.get("api_token"):
        log("⚠️  Config aapanel incompleta - pulando")
        return
    
    # Extrair host do URL
    url = aapanel["url"].replace("https://", "").replace("http://", "")
    host = url.split(":")[0]
    usuario = aapanel.get("usuario", "root")
    usar_subdominio = aapanel.get("usar_subdominio", True)
    dominio_base = aapanel.get("dominio_base", "")
    pasta_base = aapanel.get("pasta_base", "clientes")
    
    if not dominio_base:
        log("⚠️  dominio_base não configurado")
        return
    
    lines = QUEUE_FILE.read_text().strip().split("\n")
    processed = []
    
    for line in lines:
        if not line.strip() or "|" not in line:
            continue
        
        local_file, remote_file = line.split("|", 1)
        local_path = Path(local_file).resolve()
        
        if not local_path.exists():
            log(f"❌ Arquivo local não existe: {local_path}")
            continue
        
        # Determinar slug e path remoto
        # remote_file ex: /www/wwwroot/cliente-slug.dominio.com/index.html
        # ou /www/wwwroot/dominio.com/clientes/cliente-slug/index.html
        
        if usar_subdominio:
            # extrair slug do path
            # /www/wwwroot/cliente-slug.dominio.com/index.html
            import re
            match = re.search(r'/www/wwwroot/([^/]+)\.' + re.escape(dominio_base), remote_file)
            if match:
                slug = match.group(1)
                remote_dir = f"/www/wwwroot/{slug}.{dominio_base}"
            else:
                log(f"❌ Não conseguiu extrair slug de: {remote_file}")
                continue
        else:
            # subpasta: /www/wwwroot/dominio.com/clientes/cliente-slug/
            import re
            match = re.search(rf'/www/wwwroot/{re.escape(dominio_base)}/{re.escape(pasta_base)}/([^/]+)/', remote_file)
            if match:
                slug = match.group(1)
                remote_dir = f"/www/wwwroot/{dominio_base}/{pasta_base}/{slug}"
            else:
                log(f"❌ Não conseguiu extrair slug de: {remote_file}")
                continue
        
        log(f"📤 Publicando {slug} → {remote_dir}")
        
        # Criar diretório remoto se não existe
        ssh_mkdir = ["ssh", "-o", "StrictHostKeyChecking=no", f"{usuario}@{host}", f"mkdir -p {remote_dir}"]
        subprocess.run(ssh_mkdir, capture_output=True, timeout=30)
        
        # rsync
        ok, out, err = run_rsync(local_path.parent, host, usuario, remote_dir)
        
        if ok:
            log(f"✅ {slug} publicado com sucesso")
        else:
            log(f"❌ Falha ao publicar {slug}: {err}")
        
        processed.append(line)
    
    # Renomear fila processada
    if processed:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        done_file = BASE_DIR / f"fila-publicada-{timestamp}.txt"
        remaining = [l for l in lines if l not in processed]
        
        if remaining:
            QUEUE_FILE.write_text("\n".join(remaining) + "\n")
        else:
            QUEUE_FILE.unlink(missing_ok=True)
        
        done_file.write_text("\n".join(processed) + "\n")
        log(f"📋 Fila processada → {done_file.name}")

def main():
    log("🔄 Publicador aapanel iniciado (loop 60s)")
    log(f"📁 Base: {BASE_DIR}")
    
    while True:
        try:
            process_queue()
        except Exception as e:
            log(f"❌ Erro no loop: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main()
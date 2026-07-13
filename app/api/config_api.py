from __future__ import annotations

import json
import os
import select
import subprocess

import requests
from flask import Blueprint, jsonify, request

from app.config import get_maps_keys, mask_config, merge_config
from app.discovery import engine_status
from app.discovery.apify_client import ApifyGoogleMapsService
from app.discovery.places import GooglePlacesService

config_bp = Blueprint("config_api", __name__, url_prefix="/api/config")


def _kie_tools(key: str) -> tuple[dict, list[dict]]:
    """Open a short-lived stdio MCP session and return server/tool metadata."""
    proc = subprocess.Popen(
        ["npx", "-y", "@felores/kie-ai-mcp-server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env={**os.environ, "KIE_AI_API_KEY": key},
    )
    try:
        assert proc.stdin and proc.stdout
        def request_mcp(message: dict) -> dict:
            proc.stdin.write(json.dumps(message) + "\n")
            proc.stdin.flush()
            ready, _, _ = select.select([proc.stdout], [], [], 20)
            if not ready:
                raise RuntimeError("o MCP não respondeu em 20 segundos")
            return json.loads(proc.stdout.readline().strip())

        init = request_mcp({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "prospector-iabotz", "version": "1.0"}}})
        if init.get("error"):
            raise RuntimeError(init["error"].get("message") or "erro MCP")
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()
        tools = request_mcp({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        if tools.get("error"):
            raise RuntimeError(tools["error"].get("message") or "tools/list falhou")
        return (init.get("result") or {}).get("serverInfo") or {}, (tools.get("result") or {}).get("tools") or []
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


def _kie_call(key: str, tool_name: str, arguments: dict) -> dict:
    """Call one KIE MCP tool in a short-lived stdio session."""
    proc = subprocess.Popen(
        ["npx", "-y", "@felores/kie-ai-mcp-server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env={**os.environ, "KIE_AI_API_KEY": key},
    )
    try:
        assert proc.stdin and proc.stdout
        def request_mcp(message: dict) -> dict:
            proc.stdin.write(json.dumps(message) + "\n")
            proc.stdin.flush()
            ready, _, _ = select.select([proc.stdout], [], [], 60)
            if not ready:
                raise RuntimeError("o KIE MCP não respondeu em 60 segundos")
            return json.loads(proc.stdout.readline().strip())
        init = request_mcp({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "prospector-iabotz", "version": "1.0"}}})
        if init.get("error"):
            raise RuntimeError(init["error"].get("message") or "erro MCP")
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()
        result = request_mcp({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}})
        if result.get("error"):
            raise RuntimeError(result["error"].get("message") or "geração falhou")
        return result.get("result") or {}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


def _kie_payload(result: dict) -> dict:
    """KIE wraps JSON in MCP content text; normalize it for the web client."""
    for item in result.get("content") or []:
        if item.get("type") == "text" and item.get("text"):
            try:
                return json.loads(item["text"])
            except json.JSONDecodeError:
                continue
    return result


@config_bp.get("")
def get_config():
    return jsonify(mask_config())


@config_bp.post("")
def save_config():
    data = request.json or {}
    merge_config(data)
    return jsonify({"success": True, "config": mask_config()})


@config_bp.get("/engines")
def engines():
    return jsonify(engine_status())


@config_bp.post("/engines/test")
def test_engine():
    data = request.json or {}
    which = data.get("engine") or "google_places"
    google_key, apify_key = get_maps_keys()
    if which in ("google_places", "places"):
        if not google_key:
            return jsonify({"success": False, "message": "google_maps_api_key vazia"})
        return jsonify(GooglePlacesService(google_key).test_connection())
    if which == "apify":
        if not apify_key:
            return jsonify({"success": False, "message": "apify_api_key vazia"})
        return jsonify(ApifyGoogleMapsService(apify_key).test_connection())
    return jsonify({"success": False, "message": "engine inválido"}), 400


@config_bp.get("/integrations")
def integrations_status():
    """Status claro de cada integração do funil."""
    from app.config import load_config

    cfg = load_config()
    maps = cfg.get("maps") or {}
    cf = cfg.get("cloudflare") or {}
    aa = cfg.get("aapanel") or {}
    composio = cfg.get("composio") or {}
    llm = cfg.get("llm") or {}
    envio = cfg.get("envio") or {}
    from app.composio_gmail import gmail_status

    gmail = gmail_status(
        (composio.get("api_key") or "").strip(),
        (composio.get("entity_id") or "").strip(),
    )
    return jsonify(
        {
            "funnel": [
                {
                    "id": "maps",
                    "label": "1. Google Maps",
                    "ready": bool(maps.get("google_maps_api_key") or maps.get("apify_api_key")),
                    "detail": f"Engine: {maps.get('engine') or 'auto'}",
                },
                {
                    "id": "redesign",
                    "label": "2. Redesign (LLM)",
                    "ready": bool(llm.get("openrouter_api_key")) or True,
                    "detail": f"Provider: {llm.get('default_provider') or 'openrouter'}",
                },
                {
                    "id": "aapanel",
                    "label": "3. Publicar aaPanel",
                    "ready": bool(aa.get("dominio_base")),
                    "detail": aa.get("dominio_base") or "domínio base não definido",
                },
                {
                    "id": "cloudflare",
                    "label": "4. DNS Cloudflare",
                    "ready": bool(cf.get("api_key") or cf.get("api_token")),
                    "detail": f"Zona: {cf.get('zone') or '—'}",
                },
                {
                    "id": "gmail",
                    "label": "5. Gmail (Composio)",
                    "ready": bool(gmail.get("connected")),
                    "detail": (
                        f"Modo envio: {envio.get('modo') or 'rascunho'}"
                        + f" · {gmail.get('reason') or 'não verificado'}"
                        + (" · User ID configurado não corresponde; conta única será usada" if gmail.get("configured_user_mismatch") else "")
                    ),
                },
                {
                    "id": "whatsapp",
                    "label": "6. WhatsApp (Evolution)",
                    "ready": bool(
                        (envio.get("canais") and "whatsapp" in envio["canais"]) and
                        (envio.get("whatsapp", {}).get("evolution_api", {}).get("api_key")
                        or envio.get("whatsapp", {}).get("evolution_go", {}).get("api_key"))
                    ),
                    "detail": (
                        f"Canais: {' + '.join(envio.get('canais') or ['—'])}"
                        + " · "
                        + f"Provedor: {envio.get('whatsapp', {}).get('provedor') or '—'}"
                    ),
                },
            ]
        }
    )


@config_bp.post("/composio/test")
def test_composio():
    from app.composio_gmail import gmail_status
    from app.config import load_config

    composio = load_config().get("composio") or {}
    result = gmail_status(
        (composio.get("api_key") or "").strip(),
        (composio.get("entity_id") or "").strip(),
    )
    return jsonify({
        "success": bool(result.get("connected")),
        "message": result.get("reason"),
        "accounts": result.get("accounts", 0),
        "configured_user_mismatch": result.get("configured_user_mismatch", False),
    })


@config_bp.post("/cloudflare/test")
def test_cloudflare():
    from app.config import load_config
    import sys
    from pathlib import Path

    cfg = load_config().get("cloudflare") or {}
    if not (cfg.get("api_key") or cfg.get("api_token")):
        return jsonify({"success": False, "message": "Cloudflare sem api_key/api_token"})
    ref = Path(__file__).resolve().parents[2] / "skills" / "deploy-aapanel" / "references"
    sys.path.insert(0, str(ref))
    try:
        from cloudflare_client import CloudflareClient

        if cfg.get("api_token"):
            client = CloudflareClient(
                api_token=cfg["api_token"],
                zone_name=cfg.get("zone") or "example.com",
            )
        else:
            client = CloudflareClient(
                api_key=cfg["api_key"],
                api_email=cfg.get("email") or "",
                zone_name=cfg.get("zone") or "example.com",
            )
        records = client.list_records()
        return jsonify(
            {
                "success": True,
                "message": f"OK — zona {cfg.get('zone')} com {len(records)} CNAMEs",
                "count": len(records),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@config_bp.post("/whatsapp/test")
def test_whatsapp():
    """Checks the selected Evolution provider using its saved API key."""
    from app.config import load_config

    wa = ((load_config().get("envio") or {}).get("whatsapp") or {})
    provider = wa.get("provedor") or "evolution_api"
    provider_cfg = wa.get(provider) or {}
    url = (provider_cfg.get("url") or "").rstrip("/")
    api_key = (provider_cfg.get("api_key") or "").strip()
    if not url or not api_key:
        return jsonify({"success": False, "message": "Preencha URL e API key antes de testar"}), 400

    try:
        if provider == "evolution_go":
            response = requests.get(f"{url}/instance/all", headers={"apikey": api_key}, timeout=12)
            response.raise_for_status()
            data = response.json()
            instances = data.get("data") or data.get("instances") or []
            return jsonify({"success": True, "message": f"Evolution Go conectado · {len(instances)} instância(s) encontrada(s)"})

        instance = provider_cfg.get("instance") or ""
        response = requests.get(f"{url}/instance/fetchInstances", headers={"apikey": api_key}, timeout=12)
        response.raise_for_status()
        data = response.json()
        instances = data.get("response") if isinstance(data, dict) else data
        instances = instances if isinstance(instances, list) else []
        found = not instance or any((item.get("instanceName") or item.get("name")) == instance for item in instances if isinstance(item, dict))
        if instance and not found:
            return jsonify({"success": False, "message": f"Evolution conectou, mas a instância '{instance}' não foi encontrada"})
        return jsonify({"success": True, "message": f"Evolution API conectada · instância {instance or 'padrão'} pronta"})
    except requests.HTTPError as exc:
        return jsonify({"success": False, "message": f"Evolution respondeu HTTP {exc.response.status_code}: verifique URL e API key"})
    except Exception as exc:
        return jsonify({"success": False, "message": f"Falha ao conectar Evolution: {exc}"})


@config_bp.post("/kie/test")
def test_kie():
    """Starts KIE's stdio MCP and validates its MCP initialize handshake."""
    from app.config import load_config

    submitted = (request.json or {}).get("api_key") or ""
    key = submitted.strip() if submitted != "***" else ""
    if not key:
        key = ((load_config().get("redesign") or {}).get("kie_api_key") or "").strip()
    if not key:
        return jsonify({"success": False, "message": "Informe a KIE AI API key antes de testar"}), 400

    try:
        info, tools = _kie_tools(key)
        return jsonify({"success": True, "message": f"KIE MCP conectado: {info.get('name', 'servidor')} · {len(tools)} ferramenta(s)"})
    except Exception as exc:
        return jsonify({"success": False, "message": f"Falha KIE MCP: {exc}"})


@config_bp.post("/kie/models")
def kie_models():
    """Expose selectable image models declared by the KIE MCP tool schemas."""
    from app.config import load_config
    submitted = (request.json or {}).get("api_key") or ""
    key = submitted.strip() if submitted != "***" else ""
    if not key:
        key = ((load_config().get("redesign") or {}).get("kie_api_key") or "").strip()
    if not key:
        return jsonify({"success": False, "message": "Informe a KIE AI API key", "models": []}), 400
    try:
        _, tools = _kie_tools(key)
        models = []
        for tool in tools:
            schema = tool.get("inputSchema") or {}
            name = tool.get("name") or ""
            if "prompt" in (schema.get("properties") or {}) and any(token in name for token in ("image", "recraft", "midjourney", "grok")):
                models.append({"id": name, "label": (tool.get("description") or name).split(".")[0], "schema": schema})
        return jsonify({"success": True, "models": models, "tools": [tool.get("name") for tool in tools]})
    except Exception as exc:
        return jsonify({"success": False, "message": f"Falha KIE MCP: {exc}", "models": []})


@config_bp.post("/kie/generate")
def kie_generate():
    """Generate an image preview with the selected KIE image tool."""
    from app.config import load_config
    data = request.json or {}
    key = (data.get("api_key") or "").strip()
    if not key or key == "***":
        key = ((load_config().get("redesign") or {}).get("kie_api_key") or "").strip()
    model = (data.get("model") or "").strip()
    prompt = (data.get("prompt") or "").strip()
    if not key or not model or not prompt:
        return jsonify({"success": False, "message": "API key, modelo e prompt são obrigatórios"}), 400
    try:
        _, tools = _kie_tools(key)
        tool = next((item for item in tools if item.get("name") == model), None)
        if not tool:
            return jsonify({"success": False, "message": "Modelo não disponível no KIE MCP"}), 400
        props = ((tool.get("inputSchema") or {}).get("properties") or {})
        arguments = {"prompt": prompt}
        for name in ("aspect_ratio", "resolution", "output_format"):
            if name in props and data.get(name):
                arguments[name] = data[name]
        result = _kie_payload(_kie_call(key, model, arguments))
        task_id = ((result.get("response") or {}).get("data") or {}).get("taskId") or result.get("task_id")
        return jsonify({"success": bool(result.get("success", True)), "message": result.get("message") or "Imagem solicitada ao KIE", "task_id": task_id, "status": result.get("status") or "queued", "result": result})
    except Exception as exc:
        return jsonify({"success": False, "message": f"Falha ao gerar imagem: {exc}"})


@config_bp.post("/kie/status")
def kie_status():
    """Poll a KIE generation task and return its final image URLs when ready."""
    from app.config import load_config
    data = request.json or {}
    task_id = (data.get("task_id") or "").strip()
    key = (data.get("api_key") or "").strip()
    if not key or key == "***":
        key = ((load_config().get("redesign") or {}).get("kie_api_key") or "").strip()
    if not task_id or not key:
        return jsonify({"success": False, "message": "Task ID e API key são obrigatórios"}), 400
    try:
        result = _kie_payload(_kie_call(key, "get_task_status", {"task_id": task_id}))
        status = result.get("status") or "unknown"
        urls = result.get("result_urls") or []
        return jsonify({"success": bool(result.get("success", True)), "task_id": task_id, "status": status, "urls": urls, "error": result.get("error"), "message": result.get("message") or status})
    except Exception as exc:
        return jsonify({"success": False, "task_id": task_id, "status": "error", "message": f"Falha ao consultar imagem: {exc}"})

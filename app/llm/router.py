"""LLM provider router."""
from __future__ import annotations

from app.config import load_config
from app.llm import cli_providers, openrouter


PROVIDERS = ("openrouter", "claude", "codex", "cursor")


def list_providers() -> list[dict]:
    cfg = load_config()
    llm = cfg.get("llm") or {}
    items = []
    # OpenRouter
    or_key = (llm.get("openrouter_api_key") or "").strip()
    items.append(
        {
            "id": "openrouter",
            "name": "OpenRouter",
            "available": bool(or_key),
            "models": [],  # sob demanda: /api/providers/openrouter/models
            "models_loaded_via": "/api/providers/openrouter/models",
            "default_model": llm.get("openrouter_model") or "openai/gpt-4o-mini",
            "detail": "API key configurada" if or_key else "Sem API key",
        }
    )
    for pid, name, checker in (
        ("claude", "Claude CLI", cli_providers.claude_available),
        ("codex", "Codex CLI", cli_providers.codex_available),
        ("cursor", "Cursor Agent", cli_providers.cursor_available),
    ):
        ok, detail = checker()
        items.append(
            {
                "id": pid,
                "name": name,
                "available": ok,
                "detail": detail,
                "models": [],
            }
        )
    return items


def complete(
    provider: str | None,
    prompt: str,
    system: str = "",
    model: str | None = None,
) -> str:
    cfg = load_config()
    llm = cfg.get("llm") or {}
    provider = (provider or llm.get("default_provider") or "openrouter").lower()

    if provider == "openrouter":
        key = (llm.get("openrouter_api_key") or "").strip()
        if not key:
            raise RuntimeError("OpenRouter não configurado")
        return openrouter.chat(
            key,
            model or llm.get("openrouter_model") or "openai/gpt-4o-mini",
            prompt,
            system=system,
        )
    if provider == "claude":
        return cli_providers.run_claude(prompt, system=system)
    if provider == "codex":
        return cli_providers.run_codex(prompt, system=system)
    if provider == "cursor":
        return cli_providers.run_cursor(prompt, system=system)
    raise RuntimeError(f"Provider desconhecido: {provider}")

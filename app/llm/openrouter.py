"""OpenRouter API client."""
from __future__ import annotations

import requests

API = "https://openrouter.ai/api/v1"

PREFERRED = [
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "anthropic/claude-sonnet-4",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-2.5-flash",
    "google/gemini-2.0-flash-001",
    "deepseek/deepseek-chat",
    "meta-llama/llama-3.3-70b-instruct",
]


def list_models(api_key: str, q: str | None = None) -> list[dict]:
    r = requests.get(
        f"{API}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json().get("data") or []
    out = []
    needle = (q or "").strip().lower()
    for m in data:
        mid = m.get("id") or ""
        if not mid:
            continue
        name = m.get("name") or mid
        low = mid.lower()
        if "embedding" in low or "-embed" in low:
            continue
        if needle and needle not in mid.lower() and needle not in name.lower():
            continue
        pricing = m.get("pricing") or {}
        out.append(
            {
                "id": mid,
                "name": name,
                "context": m.get("context_length"),
                "prompt": pricing.get("prompt"),
                "completion": pricing.get("completion"),
            }
        )

    pref_index = {mid: i for i, mid in enumerate(PREFERRED)}

    def sort_key(item: dict):
        mid = item["id"]
        if mid in pref_index:
            return (0, pref_index[mid], mid)
        return (1, 0, mid.lower())

    out.sort(key=sort_key)
    return out


def chat(api_key: str, model: str, prompt: str, system: str = "") -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    r = requests.post(
        f"{API}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"model": model, "messages": messages},
        timeout=120,
    )
    r.raise_for_status()
    choices = r.json().get("choices") or []
    if not choices:
        raise RuntimeError("OpenRouter sem choices")
    return choices[0]["message"]["content"]

"""OpenRouter API client."""
from __future__ import annotations

import requests

API = "https://openrouter.ai/api/v1"


def list_models(api_key: str) -> list[dict]:
    r = requests.get(
        f"{API}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json().get("data") or []
    out = []
    for m in data:
        mid = m.get("id") or ""
        if mid:
            out.append({"id": mid, "name": m.get("name") or mid})
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

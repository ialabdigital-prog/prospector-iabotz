"""Detect and invoke authenticated CLIs: claude, codex, cursor agent."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple


def _extra_bins() -> list[Path]:
    home = Path(os.path.expanduser("~"))
    return [
        home / ".local" / "bin",
        home / ".cursor" / "bin",
        Path("/usr/local/bin"),
    ]


def _which(cmd: str) -> str | None:
    found = shutil.which(cmd)
    if found:
        return found
    for d in _extra_bins():
        candidate = d / cmd
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def claude_available() -> Tuple[bool, str]:
    path = _which("claude")
    if not path:
        return False, "claude não encontrado (PATH / ~/.local/bin)"
    try:
        p = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=10
        )
        raw = (p.stdout or p.stderr or "").strip()
        ver = raw.splitlines()[0][:100] if raw else "ok"
        if p.returncode == 0:
            return True, f"{ver} · {path}"
        return False, f"claude sem auth · {path}"
    except Exception as e:
        return False, str(e)


def codex_available() -> Tuple[bool, str]:
    path = _which("codex")
    if not path:
        return False, "codex não encontrado (PATH / ~/.local/bin)"
    try:
        p = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=10
        )
        raw = (p.stdout or p.stderr or "").strip()
        ver = raw.splitlines()[0][:100] if raw else "ok"
        if p.returncode != 0 or "codex" not in raw.lower():
            return False, f"binário incompatível em {path}"
        return True, f"{ver} · {path}"
    except Exception as e:
        return False, str(e)


def cursor_available() -> Tuple[bool, str]:
    for name in ("cursor-agent", "agent", "cursor"):
        path = _which(name)
        if path:
            return True, f"{name} · {path}"
    return False, "cursor-agent / agent não encontrado"


def run_claude(prompt: str, system: str = "") -> str:
    path = _which("claude")
    if not path:
        raise RuntimeError("claude CLI indisponível")
    full = f"{system}\n\n{prompt}" if system else prompt
    p = subprocess.run(
        [path, "-p", full, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr or "claude failed")
    return p.stdout.strip()


def run_codex(prompt: str, system: str = "") -> str:
    path = _which("codex")
    if not path:
        raise RuntimeError("codex CLI indisponível")
    full = f"{system}\n\n{prompt}" if system else prompt
    p = subprocess.run(
        [path, "exec", full],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr or "codex failed")
    return p.stdout.strip()


def run_cursor(prompt: str, system: str = "") -> str:
    for name in ("cursor-agent", "agent"):
        path = _which(name)
        if not path:
            continue
        full = f"{system}\n\n{prompt}" if system else prompt
        p = subprocess.run(
            [path, "-p", full],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if p.returncode == 0:
            return p.stdout.strip()
        raise RuntimeError(p.stderr or f"{name} failed")
    raise RuntimeError("cursor agent CLI indisponível")

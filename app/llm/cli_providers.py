"""Detect and invoke authenticated CLIs: claude, codex, cursor agent."""
from __future__ import annotations

import shutil
import subprocess
from typing import Tuple


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def claude_available() -> Tuple[bool, str]:
    path = _which("claude")
    if not path:
        return False, "claude não encontrado no PATH"
    try:
        p = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=10
        )
        if p.returncode == 0:
            return True, (p.stdout or p.stderr or "ok").strip()[:120]
        return False, "claude sem auth ou erro"
    except Exception as e:
        return False, str(e)


def codex_available() -> Tuple[bool, str]:
    path = _which("codex")
    if not path:
        return False, "codex não encontrado no PATH"
    try:
        p = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=10
        )
        return p.returncode == 0, ((p.stdout or p.stderr or "")[:120] or "ok")
    except Exception as e:
        return False, str(e)


def cursor_available() -> Tuple[bool, str]:
    for name in ("cursor-agent", "agent", "cursor"):
        path = _which(name)
        if path:
            return True, f"{name} em {path}"
    return False, "cursor/agent CLI não encontrado"


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

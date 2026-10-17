"""Клиент к локальному llama-server (Qwen3-VL, GGUF). Только localhost — никаких облачных API."""
from __future__ import annotations

import json
import os
import re
import urllib.request

import numpy as np

from ..video import to_jpeg_b64

VLM_URL = os.getenv("VLM_URL", "http://127.0.0.1:8080")


def ask(prompt: str, frames: list[np.ndarray], max_tokens: int = 400, temperature: float = 0.0,
        timeout: float = 120) -> str:
    content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{to_jpeg_b64(f)}"}} for f in frames]
    content.append({"type": "text", "text": prompt})
    body = json.dumps({
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()
    req = urllib.request.Request(f"{VLM_URL}/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def ask_json(prompt: str, frames: list[np.ndarray], **kw) -> dict:
    text = ask(prompt, frames, **kw)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"VLM не вернула JSON: {text[:200]}")
    return json.loads(m.group(0))


def healthy() -> bool:
    try:
        with urllib.request.urlopen(f"{VLM_URL}/health", timeout=3) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False

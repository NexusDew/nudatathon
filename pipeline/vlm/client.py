"""Клиент к локальному llama-server (Qwen3-VL, GGUF). Только localhost — никаких облачных API."""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path

import numpy as np

from ..video import to_jpeg_b64

VLM_URL = os.getenv("VLM_URL", "http://127.0.0.1:8080")
# Кэш ответов по (промпт, байты изображений): повторные прогоны eval не тратят время GPU
CACHE_DIR = Path(os.getenv("VLM_CACHE_DIR", "runs/vlm_cache"))


def ask(prompt: str, frames: list[np.ndarray], max_tokens: int = 300, temperature: float = 0.0,
        timeout: float = 120) -> str:
    images = [to_jpeg_b64(f) for f in frames]
    key = hashlib.sha1((prompt + "".join(images) + str(max_tokens)).encode()).hexdigest()
    cached = CACHE_DIR / f"{key}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8")

    content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}} for b in images]
    content.append({"type": "text", "text": prompt})
    body = json.dumps({
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()
    req = urllib.request.Request(f"{VLM_URL}/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        text = json.loads(r.read())["choices"][0]["message"]["content"]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(text, encoding="utf-8")
    return text


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

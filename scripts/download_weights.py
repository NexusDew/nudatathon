"""Скачивание всех весов и бинарников в WEIGHTS_DIR (по умолчанию ./weights).

    python scripts/download_weights.py [--dir D:/nudatathon_weights] [--only dfine,owlv2,qwen4b,qwen8b,llamacpp]

Повторы и докачка при обрывах сети. После загрузки сервису интернет не нужен.
Все модели — Apache 2.0 (проверено по тегам на huggingface.co).
"""
from __future__ import annotations

import argparse
import os
import time
import urllib.request
import zipfile
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

HF_MODELS = {
    # name: (repo_id, allow_patterns | list of files)
    "dfine": ("ustc-community/dfine-medium-obj365", ["*.json", "*.safetensors"]),
    "dfine_coco": ("ustc-community/dfine-medium-coco", ["*.json", "*.safetensors"]),
    "owlv2": ("google/owlv2-base-patch16-ensemble", ["*.json", "*.safetensors", "*.txt"]),
}
QWEN = {
    # name: (repo, files, local dir)
    "qwen4b": ("Qwen/Qwen3-VL-4B-Instruct-GGUF",
               ["Qwen3VL-4B-Instruct-Q4_K_M.gguf", "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf"], "qwen3vl-4b"),
    "qwen8b": ("Qwen/Qwen3-VL-8B-Instruct-GGUF",
               ["Qwen3VL-8B-Instruct-Q4_K_M.gguf", "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"], "qwen3vl-8b"),
}

LLAMACPP_TAG = "b11707"
LLAMACPP_ZIPS = [
    f"llama-{LLAMACPP_TAG}-bin-win-cuda-12.4-x64.zip",
    "cudart-llama-bin-win-cuda-12.4-x64.zip",
]


def retry(fn, what: str, attempts: int = 30):
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — сеть на хакатоне нестабильна
            print(f"[{what}] попытка {i}/{attempts} не удалась: {e!r}", flush=True)
            time.sleep(min(5 * i, 30))
    raise RuntimeError(f"не удалось скачать {what}")


def http_download(url: str, dst: Path) -> None:
    """Скачивание с докачкой через Range."""
    tmp = dst.with_suffix(dst.suffix + ".part")
    have = tmp.stat().st_size if tmp.exists() else 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "ab" if have else "wb") as f:
        if have and r.status != 206:  # сервер не поддержал Range — начинаем заново
            f.truncate(0)
            have = 0
        expected = have + int(r.headers.get("Content-Length", 0))
        while chunk := r.read(4 * 1024 * 1024):
            f.write(chunk)
    got = tmp.stat().st_size
    if expected and got < expected:  # соединение оборвалось без исключения — докачаем в следующей попытке
        raise IOError(f"скачано {got} из {expected} байт")
    tmp.replace(dst)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.getenv("WEIGHTS_DIR", "weights"))
    ap.add_argument("--only", default="dfine,dfine_coco,owlv2,qwen4b,llamacpp")
    a = ap.parse_args()
    root = Path(a.dir)
    root.mkdir(parents=True, exist_ok=True)
    only = set(a.only.split(","))

    for name, (repo, patterns) in HF_MODELS.items():
        if name in only:
            retry(lambda: snapshot_download(repo, local_dir=root / name, allow_patterns=patterns), name)
            print(f"OK {name} -> {root / name}", flush=True)

    for name, (repo, files, sub) in QWEN.items():
        if name in only:
            for fname in files:
                retry(lambda: hf_hub_download(repo, fname, local_dir=root / sub), fname)
                print(f"OK {fname}", flush=True)

    if "llamacpp" in only:
        dst_dir = root / "llama.cpp"
        dst_dir.mkdir(exist_ok=True)
        for z in LLAMACPP_ZIPS:
            zp = root / z
            url = f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMACPP_TAG}/{z}"
            if not zp.exists():
                retry(lambda: http_download(url, zp), z)
            if not zipfile.is_zipfile(zp):  # битый архив от старой версии скрипта — докачать
                zp.rename(zp.with_suffix(zp.suffix + ".part"))
                retry(lambda: http_download(url, zp), z)
            with zipfile.ZipFile(zp) as zf:
                zf.extractall(dst_dir)
            zp.unlink()
            print(f"OK {z} -> {dst_dir}", flush=True)

    print("Готово.")


if __name__ == "__main__":
    main()

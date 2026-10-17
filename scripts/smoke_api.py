"""Проверка API так, как это сделает жюри: загрузка .mov -> опрос job -> проверка схемы.

    python scripts/smoke_api.py --url http://localhost:8000 --key <API_KEY> --video open/videos/X-1.mov
"""
from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def request(url: str, key: str, data: bytes | None = None, ctype: str | None = None) -> dict:
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("X-API-Key", key)
    if ctype:
        req.add_header("Content-Type", ctype)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def upload(url: str, key: str, video: Path) -> dict:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"video.mov\"\r\n"
            f"Content-Type: video/quicktime\r\n\r\n").encode() + video.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    return request(f"{url}/api/v1/analyze", key, body, f"multipart/form-data; boundary={boundary}")


def check_schema(j: dict) -> list[str]:
    errs = []
    if j.get("verdict") not in ("violation", "no_violation"):
        errs.append(f"verdict={j.get('verdict')!r}")
    v = j.get("violations")
    if not isinstance(v, list):
        return errs + ["violations не список"]
    if (j["verdict"] == "violation") != bool(v):
        errs.append("verdict не согласован с violations")
    for i, x in enumerate(v):
        for k, t in (("type", str), ("timecode_sec", (int, float)), ("description", str), ("evidence_frames", list)):
            if not isinstance(x.get(k), t):
                errs.append(f"violations[{i}].{k}")
        frames = x.get("evidence_frames") or []
        if not 1 <= len(frames) <= 3:
            errs.append(f"violations[{i}]: кадров {len(frames)}, нужно 1–3")
        for f in frames:
            if not base64.b64decode(f["image_base64"])[:3] == b"\xff\xd8\xff":
                errs.append(f"violations[{i}]: кадр не JPEG")
    return errs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--key", required=True)
    ap.add_argument("--video", required=True)
    a = ap.parse_args()

    try:
        request(f"{a.url}/api/v1/jobs/x", "wrong-key")
        print("ОШИБКА: запрос с неверным ключом не отклонён")
    except urllib.error.HTTPError as e:
        print(f"неверный ключ -> {e.code} (ожидается 401)")

    t0 = time.time()
    job = upload(a.url, a.key, Path(a.video))
    print("analyze ->", job)
    while True:
        j = request(f"{a.url}/api/v1/jobs/{job['job_id']}", a.key)
        if j["status"] != "processing":
            break
        time.sleep(2)
    dt = time.time() - t0
    errs = check_schema(j) if j["status"] == "done" else [f"status={j['status']}"]
    for x in j.get("violations", []):
        for f in x["evidence_frames"]:
            f["image_base64"] = f["image_base64"][:16] + "…"
    print(json.dumps(j, ensure_ascii=False, indent=2))
    print(f"\nвремя: {dt:.1f} с {'(ПРЕВЫШЕН ЛИМИТ 300 с)' if dt > 300 else ''}")
    print("схема OK" if not errs else "ПРОБЛЕМЫ: " + "; ".join(errs))


if __name__ == "__main__":
    main()

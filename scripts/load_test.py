"""Нагрузочная проверка: N видео загружаются одновременно, время до результата каждого — от момента загрузки.

    python scripts/load_test.py --key <API_KEY> --videos open/videos/Х-14.mov,open/videos/Х-4.mov,...
Лимит жюри — 300 с на видео с момента загрузки.
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.smoke_api import check_schema, request, upload  # noqa: E402


def run_one(url: str, key: str, video: Path) -> tuple[str, float, str, list[str]]:
    t0 = time.time()
    job = upload(url, key, video)
    while True:
        j = request(f"{url}/api/v1/jobs/{job['job_id']}", key)
        if j["status"] != "processing":
            break
        time.sleep(2)
    errs = check_schema(j) if j["status"] == "done" else [j.get("error", "")]
    return video.stem, time.time() - t0, j["status"], errs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--key", required=True)
    ap.add_argument("--videos", required=True)
    a = ap.parse_args()
    videos = [Path(p) for p in a.videos.split(",")]
    with ThreadPoolExecutor(len(videos)) as pool:
        results = list(pool.map(lambda p: run_one(a.url, a.key, p), videos))
    for name, dt, status, errs in sorted(results, key=lambda r: r[1]):
        flag = "OK " if dt <= 300 and status == "done" and not errs else "FAIL"
        print(f"{flag} {name:6} {status:8} {dt:6.1f} с  {'; '.join(errs)}")
    print(f"максимум: {max(r[1] for r in results):.1f} с (лимит 300 с)")


if __name__ == "__main__":
    main()

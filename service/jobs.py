"""Очередь задач анализа. Один воркер: GPU один, видео обрабатываются по очереди.

Состояние хранится на диске (DATA_DIR/jobs/<id>/), поэтому переживает перезапуск сервиса.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import uuid
from pathlib import Path

from pipeline import analyze
from pipeline.analyze import warmup
from pipeline.catalog import rule_for, verified_sources

log = logging.getLogger("jobs")
JOB_DEADLINE_SEC = float(os.getenv("JOB_DEADLINE_SEC", "250"))  # запас 50 с до лимита 300 с


class JobStore:
    def __init__(self, data_dir: str):
        self.root = Path(data_dir) / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self._queue: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        threading.Thread(target=self._worker, daemon=True, name="analyze-worker").start()
        self._requeue_unfinished()

    # --- публичное API ---

    def new_job_dir(self) -> tuple[str, Path]:
        job_id = uuid.uuid4().hex[:12]
        d = self.root / job_id
        d.mkdir(parents=True)
        return job_id, d

    def submit(self, job_id: str, video_path: Path) -> None:
        self._write(job_id, {"job_id": job_id, "status": "processing", "video": video_path.name,
                             "submitted_at": time.time()})
        self._queue.put(job_id)

    def get(self, job_id: str) -> dict | None:
        p = self.root / job_id / "result.json"
        if not job_id.isalnum() or not p.exists():
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    # --- внутреннее ---

    def _write(self, job_id: str, payload: dict) -> None:
        p = self.root / job_id / "result.json"
        tmp = p.with_suffix(".tmp")
        with self._lock:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            tmp.replace(p)

    def _requeue_unfinished(self) -> None:
        for d in sorted(self.root.iterdir(), key=lambda p: p.stat().st_mtime):
            job = self.get(d.name)
            if job and job.get("status") == "processing":
                self._queue.put(d.name)

    def _worker(self) -> None:
        try:
            warmup()
        except Exception:  # noqa: BLE001 — сервис должен подняться, ошибка всплывёт на первой задаче
            log.exception("warmup failed")
        while True:
            job_id = self._queue.get()
            job = self.get(job_id) or {"job_id": job_id}
            video = self.root / job_id / job.get("video", "")
            started = time.time()
            # Лимит жюри — 300 с с момента загрузки, включая ожидание в очереди.
            # Оставшееся время делим поровну с задачами, которые ждут за этой: иначе хвост очереди
            # получает пустой анализ, а первые видео — лишнюю точность
            deadline = job.get("submitted_at", started) + JOB_DEADLINE_SEC
            waiting = self._queue.qsize()
            deadline = started + max(0.0, deadline - started) / (1 + waiting)
            try:
                violations = analyze(str(video), deadline)
                result = {
                    "job_id": job_id,
                    "status": "done",
                    "verdict": "violation" if violations else "no_violation",
                    "violations": [_serialize(v) for v in violations],
                }
            except Exception as e:  # noqa: BLE001 — любая ошибка пайплайна = failed, сервис живёт дальше
                log.exception("job %s failed", job_id)
                result = {"job_id": job_id, "status": "failed", "error": str(e)}
            result["processing_sec"] = round(time.time() - started, 1)
            self._write(job_id, result)
            log.info("job %s -> %s за %.1f с", job_id, result["status"], result["processing_sec"])


def _serialize(v) -> dict:
    rule = rule_for(v.type_id)
    sources = verified_sources(v.type_id)
    description = v.description
    if sources:
        refs = "; ".join(f"{s['document']}, {s['clause']}" for s in sources)
        description = f"{description} Норма: {refs}."
    return {
        "type": rule["name"],
        "timecode_sec": round(float(v.timecode_sec), 1),
        "description": description,
        "evidence_frames": [
            {"timestamp_sec": round(float(f.timestamp_sec), 1), "image_base64": f.image_base64}
            for f in v.evidence_frames[:3]
        ],
        # Доп. поля сверх схемы ТЗ — для UI и проверяющего
        "type_id": v.type_id,
        "confidence": round(float(v.confidence), 2),
        "rule": {"summary": rule.get("summary", ""), "sources": sources},
    }

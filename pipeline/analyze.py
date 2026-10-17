"""Точка входа пайплайна: analyze(video_path) -> list[Violation].

Сервис вызывает только эту функцию. Внутренности (детектор, правила, VLM) меняются свободно.
"""
from __future__ import annotations

import os

from .types import EvidenceFrame, Violation
from .video import frame_at, probe, to_jpeg_b64


def analyze(video_path: str) -> list[Violation]:
    mode = os.getenv("PIPELINE_MODE", "stub")
    if mode == "stub":
        return _stub(video_path)
    raise NotImplementedError(f"PIPELINE_MODE={mode} ещё не реализован")


def _stub(video_path: str) -> list[Violation]:
    """Заглушка для проверки деплоя и UI: одно фиктивное событие в середине видео."""
    info = probe(video_path)
    t = round(info.duration_sec / 2, 1)
    frames = []
    for ts in (t,):
        frame = frame_at(video_path, ts)
        if frame is not None:
            frames.append(EvidenceFrame(ts, to_jpeg_b64(frame)))
    return [
        Violation(
            type_id="stub",
            timecode_sec=t,
            description="ЗАГЛУШКА: тестовое событие для проверки сервиса, не является результатом анализа.",
            evidence_frames=frames,
            confidence=0.0,
        )
    ]

"""Чтение кадров и кодирование кадров-доказательств."""
from __future__ import annotations

import base64
from collections.abc import Iterator
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class VideoInfo:
    fps: float
    frame_count: int
    duration_sec: float
    width: int
    height: int


def probe(path: str) -> VideoInfo:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError(f"не удалось открыть видео: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    info = VideoInfo(fps, n, n / fps, int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    cap.release()
    return info


def iter_frames(path: str, sample_fps: float = 2.0) -> Iterator[tuple[float, np.ndarray]]:
    """Кадры (timestamp_sec, BGR) с частотой sample_fps. grab() без декодирования пропущенных кадров."""
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(fps / sample_fps))
    idx = 0
    while cap.grab():
        if idx % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                yield idx / fps, frame
        idx += 1
    cap.release()


def frame_at(path: str, t_sec: float) -> np.ndarray | None:
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t_sec) * 1000)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def to_jpeg_b64(frame: np.ndarray, quality: int = 85) -> str:
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("не удалось закодировать кадр")
    return base64.b64encode(buf.tobytes()).decode("ascii")

"""Визуальная проверка детектора на размеченных моментах.

    python scripts/probe_detector.py --videos Х-20,X-1,Х-46,Х-26,Х-15 --out runs/probe

Для каждого видео: кадры вокруг метки (-2..+2 с) с рамками детекций -> JPEG-лист.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.detect import Detector  # noqa: E402
from pipeline.video import frame_at  # noqa: E402
from scripts.eval import load_labels, norm_name  # noqa: E402

COLORS = {"person": (200, 200, 200), "phone": (0, 0, 255), "cup": (0, 165, 255), "food": (0, 255, 255),
          "laptop": (255, 0, 0), "tablet": (255, 0, 255), "bag": (0, 255, 0), "wallet": (0, 128, 0), "chair": (90, 90, 90)}


def draw(frame: np.ndarray, dets, t: float) -> np.ndarray:
    img = frame.copy()
    for d in dets:
        x1, y1, x2, y2 = map(int, d.box)
        c = COLORS.get(d.cls, (255, 255, 255))
        cv2.rectangle(img, (x1, y1), (x2, y2), c, 2)
        cv2.putText(img, f"{d.cls} {d.score:.2f}", (x1, max(12, y1 - 4)), 0, 0.45, c, 1)
    cv2.putText(img, f"{t:.1f}s", (5, 22), 0, 0.7, (0, 255, 0), 2)
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="open")
    ap.add_argument("--videos", default="Х-20,X-1,Х-46,Х-26,Х-15,Х-22,Х-40")
    ap.add_argument("--out", default="runs/probe")
    ap.add_argument("--threshold", type=float, default=0.3)
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    df = load_labels(Path(a.data)).set_index("key")
    t0 = time.time()
    det = Detector(threshold=a.threshold)
    print(f"модель загружена за {time.time() - t0:.1f} с, device={det.device}")

    for name in a.videos.split(","):
        r = df.loc[norm_name(name)]
        center = r.gt_time if r.gt_time == r.gt_time and r.gt_time is not None else 5.0
        ts = [center + d for d in (-2, -1, 0, 1, 2)]
        frames = [frame_at(str(r.path), t) for t in ts]
        frames = [f for f in frames if f is not None]
        t1 = time.time()
        dets = det(frames)
        dt = (time.time() - t1) / max(len(frames), 1)
        tiles = [draw(f, d, t) for f, d, t in zip(frames, dets, ts)]
        sheet = np.hstack([cv2.resize(x, (348, 636)) for x in tiles])
        cv2.imencode(".jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tofile(str(out / f"{norm_name(name)}.jpg"))
        found = sorted({d.cls for ds in dets for d in ds})
        print(f"{norm_name(name):6} t={center}: {dt * 1000:.0f} мс/кадр, классы: {found}")


if __name__ == "__main__":
    main()

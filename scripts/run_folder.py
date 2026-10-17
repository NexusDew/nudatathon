"""Прогон пайплайна по папке видео без разметки: вердикты, типы, время, падения.

    python scripts/run_folder.py data/external/meva [--expect no_violation]

Для чужих сцен (MEVA) ожидаем no_violation и отсутствие падений; для своих съёмок — смотреть глазами.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import analyze  # noqa: E402
from pipeline.video import probe  # noqa: E402

EXTS = {".mov", ".mp4", ".avi", ".mkv", ".m4v"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--expect", choices=["no_violation", "violation"], default=None)
    a = ap.parse_args()
    files = sorted(p for p in Path(a.folder).iterdir() if p.suffix.lower() in EXTS)
    n_bad = 0
    times = []
    for p in files:
        info = probe(str(p))
        t0 = time.time()
        try:
            viols, err = analyze(str(p)), ""
        except Exception as e:  # noqa: BLE001
            viols, err = [], repr(e)
        dt = time.time() - t0
        times.append(dt)
        verdict = "violation" if viols else "no_violation"
        bad = bool(err) or (a.expect is not None and verdict != a.expect)
        n_bad += bad
        types = ", ".join(f"{v.type_id}@{v.timecode_sec:.1f}" for v in viols)
        print(f"{'ERR' if bad else 'OK '} {p.stem:28} {info.width}x{info.height} {info.duration_sec:5.1f}s "
              f"-> {verdict:12} {dt:5.1f}s  {types} {err}")
    print(f"\nвидео: {len(files)}, не как ожидалось/упало: {n_bad}; время среднее {sum(times) / max(len(times), 1):.1f} с, "
          f"максимум {max(times, default=0):.1f} с")


if __name__ == "__main__":
    main()

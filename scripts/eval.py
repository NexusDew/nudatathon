"""Прогон пайплайна по размеченному датасету и метрики.

    python scripts/eval.py --data open [--only Х-1,Х-2] [--tol 2.0]

Метрики:
  - вердикт по видео: accuracy, recall (пропуски недопустимы), precision (ложные срабатывания);
  - локализация: |ошибка| ближайшего предсказанного таймкода к метке, доля попаданий в ±tol с.
Подробности по каждому видео — в eval_out/report.csv.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import analyze  # noqa: E402


def norm_name(s: str) -> str:
    return str(s).strip().replace("X", "Х")  # латинская X -> кириллическая Х


def parse_time(s) -> float | None:
    if not isinstance(s, str) or not s.strip():
        return None
    nums = list(map(int, re.findall(r"\d+", s)))
    if "мин" in s:
        return nums[0] * 60 + (nums[1] if len(nums) > 1 else 0)
    return float(nums[0])


def load_labels(data_dir: Path) -> pd.DataFrame:
    df = pd.read_excel(data_dir / "open_labels.xlsx")
    df.columns = ["name", "time", "label"]
    df["key"] = df["name"].map(norm_name)
    df["gt_time"] = df["time"].map(parse_time)
    df["gt_violation"] = df["label"].str.strip().str.lower().eq("нарушение")
    files = {norm_name(p.stem): p for p in (data_dir / "videos").glob("*.mov")}
    df["path"] = df["key"].map(files)
    missing = df[df["path"].isna()]
    if len(missing):
        print("Нет видео для:", ", ".join(missing["name"]))
    return df.dropna(subset=["path"])


def load_types(path: Path) -> dict[str, set[str]]:
    """Ручная разметка типов от команды: видео -> множество type_id (без 'none')."""
    if not path.exists():
        return {}
    out: dict[str, set[str]] = {}
    # В заметках бывают запятые без кавычек — делим строку только по первым трём запятым
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split(",", 3)
        if len(parts) >= 3 and parts[2].strip() and parts[2].strip() != "none":
            out.setdefault(norm_name(parts[0]), set()).add(parts[2].strip())
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="open")
    ap.add_argument("--only", default="")
    ap.add_argument("--tol", type=float, default=2.0)
    ap.add_argument("--out", default="eval_out")
    args = ap.parse_args()

    df = load_labels(Path(args.data))
    gt_types = load_types(Path(__file__).resolve().parent.parent / "docs" / "labels_types.csv")
    if args.only:
        keep = {norm_name(x) for x in args.only.split(",")}
        df = df[df["key"].isin(keep)]

    rows = []
    for r in df.itertuples():
        t0 = time.time()
        try:
            viols = analyze(str(r.path))
            err = ""
        except Exception as e:  # noqa: BLE001
            viols, err = [], repr(e)
        dt = time.time() - t0
        pred = bool(viols)
        tcs = [v.timecode_sec for v in viols]
        loc_err = min((abs(t - r.gt_time) for t in tcs), default=None) if r.gt_time is not None else None
        expected = gt_types.get(r.key, set())
        rows.append({
            "video": r.key, "gt": r.gt_violation, "pred": pred, "gt_time": r.gt_time,
            "pred_times": ";".join(f"{t:.1f}" for t in tcs),
            "types": ";".join(v.type_id for v in viols),
            "gt_types": ";".join(sorted(expected)),
            "type_ok": bool(expected & {v.type_id for v in viols}) if expected else None,
            "loc_err": loc_err, "sec": round(dt, 1), "error": err,
        })
        mark = "OK " if pred == r.gt_violation else "ERR"
        print(f"{mark} {r.key:6} gt={int(r.gt_violation)} pred={int(pred)} "
              f"gt_t={r.gt_time} pred_t=[{rows[-1]['pred_times']}] types=[{rows[-1]['types']}] {dt:.1f}s {err}")

    res = pd.DataFrame(rows)
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    res.to_csv(out / "report.csv", index=False, encoding="utf-8-sig")

    gt, pr = res["gt"].astype(bool).to_numpy(), res["pred"].astype(bool).to_numpy()
    tp = int((gt & pr).sum()); fp = int((~gt & pr).sum())
    fn = int((gt & ~pr).sum()); tn = int((~gt & ~pr).sum())
    loc = res.loc[gt & pr, "loc_err"].dropna()
    print("\n=== Итог ===")
    print(f"видео: {len(res)}  TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"accuracy={(tp + tn) / max(len(res), 1):.3f}  recall={tp / max(tp + fn, 1):.3f}  "
          f"precision={tp / max(tp + fp, 1):.3f}")
    if len(loc):
        print(f"таймкод: медиана |ошибки|={loc.median():.1f} с, в ±{args.tol} с: {(loc <= args.tol).mean():.0%}")
    typed = res.loc[gt & pr & res["type_ok"].notna()]
    if len(typed):
        ok = typed["type_ok"].astype(bool)
        print(f"тип (по docs/labels_types.csv): верный в {ok.sum()} из {len(typed)} найденных нарушений; "
              f"неверный: {', '.join(typed.loc[~ok, 'video'] + ' ' + typed.loc[~ok, 'types'] + '≠' + typed.loc[~ok, 'gt_types'])}")
    print(f"время: среднее {res.sec.mean():.1f} с, максимум {res.sec.max():.1f} с (лимит 300 с)")
    if fn:
        print("ПРОПУЩЕНЫ:", ", ".join(res.loc[gt & ~pr, "video"]))
    if fp:
        print("ЛОЖНЫЕ:", ", ".join(res.loc[~gt & pr, "video"]))


if __name__ == "__main__":
    main()

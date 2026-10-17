"""Проверка VLM на размеченных моментах: позитивы (нарушения) и негативы (чистые видео).

    python scripts/probe_vlm.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.video import frame_at  # noqa: E402
from pipeline.vlm import ask_json, healthy  # noqa: E402
from scripts.eval import load_labels, norm_name  # noqa: E402

PROMPT = """These are 3 consecutive frames (1 second apart) from a ceiling CCTV camera in a bank cash room.
The cashier's workplace is a desk with a banknote counting machine and a laptop.
Look carefully and answer ONLY with JSON, no other text:
{
  "cashier_at_desk": true/false,
  "cashier_hands": "phone" | "food" | "drink" | "banknotes" | "documents" | "bag" | "nothing" | "other",
  "cashier_uses_mobile_phone": true/false,
  "cashier_eats_or_drinks": true/false,
  "desk_items_without_cashier": ["banknotes" | "cash bag" | "laptop with screen on" | "personal bag" | "clothes" | "food/drink" | ...],
  "other_person_on_cashier_side": true/false,
  "description": "1-2 short factual sentences about what the cashier is doing"
}"""

CASES = [  # (видео, t, что ожидаем)
    ("Х-20", 6.5, "телефон"), ("X-2", 12.0, "телефон?"), ("X-1", 21.5, "еда"), ("Х-46", 13.0, "напиток"),
    ("Х-26", 11.0, "деньги на столе, кассир ушла"), ("Х-22", 15.0, "ноутбук вкл., кассир ушла"),
    ("Х-15", 15.0, "сумка инкассатора, кассир ушла"), ("Х-40", 17.0, "личные вещи на столе"),
    ("Х-27", 24.0, "НОРМА: кассир ушла, стол чистый"), ("Х-3", 10.0, "НОРМА"), ("Х-21", 12.0, "НОРМА"),
    ("Х-10", 8.0, "НОРМА"), ("Х-12", 20.0, "НОРМА"), ("Х-16", 10.0, "НОРМА"),
]


def main() -> None:
    if not healthy():
        sys.exit("llama-server не отвечает на 127.0.0.1:8080")
    df = load_labels(Path("open")).set_index("key")
    for name, t, expect in CASES:
        path = str(df.loc[norm_name(name)].path)
        frames = [f for f in (frame_at(path, t + d) for d in (-1, 0, 1)) if f is not None]
        t0 = time.time()
        try:
            ans = ask_json(PROMPT, frames)
        except Exception as e:  # noqa: BLE001
            ans = {"error": repr(e)}
        print(f"\n## {norm_name(name)} @ {t}s — ожидаем: {expect}  ({time.time() - t0:.1f} с)")
        print(json.dumps(ans, ensure_ascii=False))


if __name__ == "__main__":
    main()

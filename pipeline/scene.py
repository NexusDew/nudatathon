"""Геометрия сцены: где стол кассира. Не зависит от ракурса — ищем стол детектором."""
from __future__ import annotations

import numpy as np

Box = tuple[int, int, int, int]


def locate_desk(frames: list[np.ndarray], detector) -> Box | None:
    """Устойчивый бокс стола: медиана лучших детекций 'desk' по нескольким кадрам.

    Если стол не найден — объединение ноутбуков/планшетов (оборудование стоит на столе).
    """
    H, W = frames[0].shape[:2]
    desks, equip = [], []
    for dets in detector(frames):
        # Мелкие «ноутбуки» — это отражения и техника за стеклом, их отсекаем по площади
        cand = [x for x in dets if x.cls in ("laptop", "tablet") and x.score > 0.3
                and (x.box[2] - x.box[0]) * (x.box[3] - x.box[1]) > 0.003 * W * H]
        # Есть уверенный ноутбук — слабые детекции (ложные на других поверхностях) не учитываем
        strong = [x for x in cand if x.score >= 0.6]
        eq = [x.box for x in (strong or cand)]
        equip += eq
        # Стол кассира — тот, на котором стоит оборудование (в кадре бывают и другие столы)
        d = [(x, sum(_inter(x.box, e) for e in eq)) for x in dets
             if x.cls == "desk" and (x.box[2] - x.box[0]) * (x.box[3] - x.box[1]) > 0.02 * W * H]
        d = [(x, ov / _area(x.box)) for x, ov in d if ov > 0]
        if d:  # доля площади стола под оборудованием: большой передний стол лишь краем задевает ноутбук
            desks.append(max(d, key=lambda p: p[1] * p[0].score)[0].box)
    if len(desks) >= max(2, len(frames) // 3):
        return tuple(int(v) for v in np.median(np.array(desks), axis=0))
    if equip:
        b = np.median(np.array(equip), axis=0)
        w, h = b[2] - b[0], b[3] - b[1]
        return clip((b[0] - 2 * w, b[1] - 0.5 * h, b[2] + w, b[3] + 1.5 * h), W, H)
    return None


def _area(b) -> float:
    return max(1.0, (b[2] - b[0]) * (b[3] - b[1]))


def _inter(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def clip(b, W: int, H: int) -> Box:
    x1, y1, x2, y2 = b
    return int(max(0, x1)), int(max(0, y1)), int(min(W, x2)), int(min(H, y2))


def expand(b: Box, W: int, H: int, left: float, top: float, right: float, bottom: float) -> Box:
    x1, y1, x2, y2 = b
    w, h = x2 - x1, y2 - y1
    return clip((x1 - left * w, y1 - top * h, x2 + right * w, y2 + bottom * h), W, H)


def workplace_box(desk: Box, W: int, H: int) -> Box:
    """Стол + место кассира вокруг: кассир может быть с любой стороны стола в зависимости от ракурса."""
    return expand(desk, W, H, 0.35, 1.0, 0.35, 0.8)


def desk_surface_box(desk: Box, W: int, H: int) -> Box:
    """Столешница с предметами, торчащими над ней (сумки, стаканы)."""
    return expand(desk, W, H, 0.1, 0.45, 0.1, -0.15)

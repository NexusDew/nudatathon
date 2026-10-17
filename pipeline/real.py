"""Пайплайн v1: детектор (геометрия сцены, люди) + VLM (состояния и проверки) + правила по таймлайну.

1. Сцена: детектор находит стол кассира (не зависит от ракурса).
2. Скан каждые STEP с: VLM смотрит на фрагмент «стол + кассир» (есть ли кассир)
   и на увеличенные фрагменты каждого человека у стола (что в руках).
3. Уходы с рабочего места: уточняем момент ухода, затем VLM осматривает опустевший стол.
4. Телефон / еда / напитки: кандидаты подтверждаются отдельным вопросом (в т.ч. «это кассир, а не клиент?»).
Описания собираются из фактов шаблонами — свободный текст модели наружу не идёт.
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import cv2
import numpy as np

from .scene import desk_surface_box, expand, locate_desk, workplace_box
from .types import EvidenceFrame, Violation
from .video import probe, to_jpeg_b64
from .vlm import ask_json
from .vlm import prompts as P

log = logging.getLogger("pipeline")

MIN_ABSENCE = 2     # уход засчитываем, если кассира нет >= 2 сканов подряд (или до конца видео)
# Бюджет на видео: лимит жюри 300 с считается с момента загрузки, плюс возможная очередь.
# Скан останавливается на SCAN_SHARE бюджета, остальное — на уточнения и проверки.
BUDGET_SEC = float(os.getenv("VIDEO_BUDGET_SEC", "150"))
SCAN_SHARE = 0.6
VLM_PARALLEL = int(os.getenv("VLM_PARALLEL", "4"))  # = числу слотов llama-server (-np)
CROP_SIDE = 640     # размер увеличенного фрагмента рабочего места для VLM
PERSON_SIDE = 448   # размер увеличенного фрагмента человека
MAX_PERSONS = 2     # сколько людей у стола проверяем на кадре

_detector = None


def _get_detector():
    global _detector
    if _detector is None:
        from .detect import Detector
        _detector = Detector(threshold=0.3)
    return _detector


def _step_for(duration: float) -> float:
    """Шаг скана: короткие видео — подробнее, длинные — реже, чтобы уложиться в бюджет времени."""
    # Шаг 2 с для коротких видео пробовали (v6): добавляет шум, точность падает с 0.71 до 0.67
    return 3.0 if duration <= 60 else 4.0


class _Video:
    """Доступ к кадрам по времени с кэшем (одни и те же моменты запрашиваются много раз)."""

    def __init__(self, path: str):
        self.info = probe(path)
        self.cap = cv2.VideoCapture(path)
        self.dur = self.info.duration_sec
        self._cache: dict[float, np.ndarray] = {}

    def clamp(self, t: float) -> float:
        return round(min(max(0.0, t), self.dur - 0.1), 2)

    def at(self, t: float) -> np.ndarray:
        t = self.clamp(t)
        if t not in self._cache:
            self.cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, f = self.cap.read()
            if not ok:
                raise ValueError(f"не удалось прочитать кадр {t} с")
            self._cache[t] = f
        return self._cache[t]


@dataclass
class _Scan:
    t: float
    present: bool
    workplace: dict
    persons: list[tuple[tuple, dict]] = field(default_factory=list)  # (бокс человека, ответ VLM)


def _crop(frame: np.ndarray, box, side: int = CROP_SIDE) -> np.ndarray:
    x1, y1, x2, y2 = box
    c = frame[y1:y2, x1:x2]
    s = side / max(c.shape[:2])
    return cv2.resize(c, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC if s > 1 else cv2.INTER_AREA)


_deadline = float("inf")  # жёсткий предел на видео; воркер один, поэтому достаточно модульной переменной


def _ask(prompt: str, frames: list[np.ndarray]) -> dict:
    if time.time() > _deadline:
        return {}
    try:
        return ask_json(prompt, frames)
    except Exception as e:  # noqa: BLE001 — один неудачный ответ не должен ронять анализ
        log.warning("VLM: %r", e)
        return {}


def _fmt(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def _evidence(v: _Video, items: list[tuple[float, tuple | None]]) -> list[EvidenceFrame]:
    """items: (время, бокс для увеличения или None для полного кадра)."""
    out = []
    for t, box in items[:3]:
        f = v.at(t)
        out.append(EvidenceFrame(v.clamp(t), to_jpeg_b64(_crop(f, box, 720) if box else f)))
    return out


def _persons_at_desk(frame: np.ndarray, desk) -> list[tuple]:
    """Люди, заметно перекрывающиеся со столом (кассир и клиенты). Люди за стеклом отсекаются."""
    H, W = frame.shape[:2]
    out = []
    for d in _get_detector()([frame])[0]:
        if d.cls != "person" or d.score < 0.5:
            continue
        x1, y1, x2, y2 = d.box
        ix = max(0.0, min(x2, desk[2]) - max(x1, desk[0]))
        iy = max(0.0, min(y2, desk[3]) - max(y1, desk[1]))
        if ix * iy > 0.1 * (x2 - x1) * (y2 - y1):
            out.append((d.score, expand(tuple(int(v) for v in d.box), W, H, 0.15, 0.1, 0.15, 0.05)))
    return [b for _, b in sorted(out, reverse=True)[:MAX_PERSONS]]


def analyze_real(path: str) -> list[Violation]:
    global _deadline
    t_start = time.time()
    _deadline = t_start + BUDGET_SEC
    v = _Video(path)
    H, W = v.info.height, v.info.width

    desk = locate_desk([v.at(t) for t in np.linspace(0.5, max(0.6, v.dur - 0.5), 8)], _get_detector())
    if desk is None:
        log.warning("стол не найден, анализ по полному кадру")
        desk = (0, 0, W, H)
    wp, surf = workplace_box(desk, W, H), desk_surface_box(desk, W, H)

    # Кадры и детекции — в основном потоке (cv2.VideoCapture и детектор не потокобезопасны),
    # запросы к VLM — параллельно: llama-server обрабатывает слоты одним батчем
    step = _step_for(v.dur)
    frames = [(float(t), v.at(float(t))) for t in np.arange(0.5, max(0.6, v.dur - 0.5), step)]
    jobs = [(t, f, _persons_at_desk(f, desk)) for t, f in frames]
    scan_deadline = t_start + BUDGET_SEC * SCAN_SHARE

    def scan_one(job) -> _Scan | None:
        t, f, boxes = job
        if time.time() > scan_deadline:
            return None
        a = _ask(P.SCAN, [_crop(f, wp)])
        s = _Scan(t, bool(a.get("cashier_at_desk", True)), a)
        s.persons = [(box, _ask(P.PERSON, [_crop(f, box, PERSON_SIDE)])) for box in boxes]
        log.debug("scan %.1f present=%s wp=%s persons=%s", t, s.present, a, [p[1] for p in s.persons])
        return s

    with ThreadPoolExecutor(VLM_PARALLEL) as pool:
        scans = [s for s in pool.map(scan_one, jobs) if s is not None]
    if len(scans) < len(jobs):
        log.warning("%s: бюджет времени исчерпан, просканировано %d из %d моментов", path, len(scans), len(jobs))

    violations = _departures(v, scans, step, wp, surf) + _hand_events(v, scans, step, wp)
    violations.sort(key=lambda x: x.timecode_sec)
    log.info("%s: %d сканов, %d событий, %.1f с", path, len(scans), len(violations), time.time() - t_start)
    return violations


def _laptop_box(frame: np.ndarray, near) -> tuple | None:
    """Самый уверенный ноутбук рядом со столом, с запасом по краям (экран бывает выше бокса)."""
    H, W = frame.shape[:2]
    best = None
    for d in _get_detector()([frame])[0]:
        if d.cls != "laptop" or d.score < 0.5:
            continue
        cx, cy = (d.box[0] + d.box[2]) / 2, (d.box[1] + d.box[3]) / 2
        if near[0] <= cx <= near[2] and near[1] <= cy <= near[3] and (best is None or d.score > best.score):
            best = d
    return expand(tuple(int(x) for x in best.box), W, H, 0.25, 0.25, 0.25, 0.1) if best else None


# --- уход с рабочего места ---

def _departures(v: _Video, scans: list[_Scan], step: float, wp, surf) -> list[Violation]:
    out: list[Violation] = []
    i = 0
    while i < len(scans):
        if scans[i].present:
            i += 1
            continue
        j = i
        while j + 1 < len(scans) and not scans[j + 1].present:
            j += 1
        if j - i + 1 >= MIN_ABSENCE or j == len(scans) - 1:
            out += _check_departure(v, scans, i, j, step, wp, surf)
        i = j + 1
    return out


def _check_departure(v: _Video, scans: list[_Scan], i: int, j: int, step: float, wp, surf) -> list[Violation]:
    t_abs = scans[i].t
    if i > 0:  # уточняем момент ухода бинарным поиском между последним «на месте» и первым «нет»
        lo, hi = scans[i - 1].t, t_abs
        for _ in range(2):
            mid = (lo + hi) / 2
            if _ask(P.PRESENCE, [_crop(v.at(mid), wp)]).get("cashier_at_desk", True):
                lo = mid
            else:
                hi = mid
        t_leave = lo
    else:
        t_leave = hi = t_abs

    t_end = min(scans[j].t + step, v.dur)
    checks = sorted({v.clamp(min(hi + 2.0, t_end)), v.clamp((hi + t_end) / 2)})
    found: dict[str, float] = {}
    for t in checks:
        a = _ask(P.DESK, [_crop(v.at(t), surf)])
        # Сумку модель часто называет «личной», даже если это инкассаторская — без кассира на столе любая сумка подозрительна
        for k in ("banknotes_or_cash", "coin_rolls_or_wrapped_cash", "cash_bag_or_sack",
                  "ledger_or_cash_documents", "personal_bag_or_clothes"):
            if a.get(k):
                found.setdefault(k, t)
        # Экран: горящий экран блокировки — норма, нарушение — открытое рабочее приложение
        if "laptop_screen_lit" not in found:
            lb = _laptop_box(v.at(t), surf)
            if lb and _ask(P.SCREEN, [_crop(v.at(t), lb, PERSON_SIDE)]).get("screen") == "application":
                found["laptop_screen_lit"] = t

    out = []
    kinds = (("banknotes_or_cash", "наличные денежные средства"),
             ("coin_rolls_or_wrapped_cash", "упакованные наличные (рулоны/пачки)"),
             ("cash_bag_or_sack", "инкассаторская сумка"),
             ("ledger_or_cash_documents", "кассовые документы/журнал"),
             ("personal_bag_or_clothes", "сумка"))
    valuables = [name for k, name in kinds if k in found]
    if "инкассаторская сумка" in valuables and "сумка" in valuables:
        valuables.remove("сумка")
    if valuables:
        t_seen = min(found[k] for k, _ in kinds if k in found)
        out.append(Violation(
            "unattended_valuables", t_leave,
            f"В {_fmt(t_leave)} кассир покидает рабочее место. На кадре {_fmt(t_seen)} кассира у стола нет, "
            f"а на столе видны {', '.join(valuables)}. Ценности оставлены без присмотра.",
            _evidence(v, [(t_leave, None), (t_seen, None), (t_seen, surf)]),
        ))
    if "laptop_screen_lit" in found:
        t_seen = found["laptop_screen_lit"]
        out.append(Violation(
            "unlocked_workstation", t_leave,
            f"В {_fmt(t_leave)} кассир покидает рабочее место. На кадре {_fmt(t_seen)} кассира у стола нет, "
            f"а на экране ноутбука открыто рабочее приложение — компьютер не заблокирован.",
            _evidence(v, [(t_leave, None), (t_seen, None), (t_seen, surf)]),
        ))
    return out


# --- кто из людей у стола кассир ---

def _center(b) -> tuple[float, float]:
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def _cashier_anchor(v: _Video, scans: list[_Scan], wp) -> tuple[float, float] | None:
    """Где сидит кассир: на 3 моментах с 2+ людьми у стола VLM выбирает кассира среди помеченных рамок.

    Клиенты тоже бывают с телефоном — без этого шага телефон клиента засчитывался бы кассиру.
    """
    multi = [s for s in scans if len(s.persons) >= 2]
    votes = []
    for s in multi[:: max(1, len(multi) // 3)][:3]:
        f = v.at(s.t).copy()
        for (b, _), lab, col in zip(s.persons, "AB", ((0, 0, 255), (255, 0, 0))):
            cv2.rectangle(f, b[:2], b[2:], col, 3)
            cv2.putText(f, lab, (b[0] + 5, b[1] + 30), cv2.FONT_HERSHEY_SIMPLEX, 1.1, col, 3)
        lab = str(_ask(P.ROLE, [_crop(f, wp)]).get("cashier", "")).strip().upper()[:1]
        if lab in ("A", "B") and "AB".index(lab) < len(s.persons):
            votes.append(_center(s.persons["AB".index(lab)][0]))
    if not votes:
        return None
    anchor = tuple(float(x) for x in np.median(np.array(votes), axis=0))
    log.debug("кассир: %s по %d голосам", anchor, len(votes))
    return anchor


def _is_cashier(box, persons, anchor) -> bool:
    if anchor is None:
        return True
    d = np.hypot(*np.subtract(_center(box), anchor))
    others = [np.hypot(*np.subtract(_center(o), anchor)) for o, _ in persons if o != box]
    if others:
        return d <= min(others)
    return d < (box[3] - box[1])  # один человек у стола: кассир, если он примерно на месте кассира


# --- уход клиента: наличные на его стороне стола, пересчёт после ухода ---

def _client_events(v: _Video, scans: list[_Scan], step: float, wp, anchor) -> list[Violation]:
    """Клиент ушёл, кассир остался: смотрим стол через несколько секунд.

    - банкноты лежат на стороне клиента дольше пары секунд → cash_left_in_client_zone;
    - кассир пересчитывает/закладывает в счётчик деньги уже без клиента → cash_count_without_client.
    """
    if anchor is None:
        return []
    has_client = [any(not _is_cashier(b, s.persons, anchor) for b, _ in s.persons) for s in scans]
    out: list[Violation] = []
    for j in range(len(scans) - 1):
        # конец визита: клиент был в двух сканах подряд, в следующем его нет, кассир на месте
        if not (has_client[j] and (j == 0 or has_client[j - 1]) and not has_client[j + 1] and scans[j + 1].present):
            continue
        t_dep = (scans[j].t + scans[j + 1].t) / 2
        checks = [t for t in (t_dep + 1.5, t_dep + 4.5) if t < v.dur - 1.5]
        if not checks:
            continue
        answers = [_ask(P.CLIENT_SIDE, [_marked_cashier(v, t, wp, anchor), _marked_cashier(v, t + 1.5, wp, anchor)])
                   for t in checks]
        log.debug("client left %.1f -> %s", t_dep, answers)
        if all(a.get("banknotes_on_client_side") for a in answers):
            t_seen = checks[-1]
            out.append(Violation(
                "cash_left_in_client_zone", t_dep,
                f"Около {_fmt(t_dep)} клиент уходит от стола. На кадрах {_fmt(checks[0])}–{_fmt(t_seen)} "
                f"на стороне клиента остаются лежать банкноты, а не убраны кассиром.",
                _evidence(v, [(t_dep, None), (t_seen, None), (t_seen, wp)]),
            ))
        if answers[0].get("cashier_counts_banknotes"):
            out.append(Violation(
                "cash_count_without_client", checks[0],
                f"Около {_fmt(t_dep)} клиент уходит от стола, а на кадре {_fmt(checks[0])} кассир пересчитывает "
                f"наличные или закладывает их в счётчик уже без клиента.",
                _evidence(v, [(t_dep, None), (checks[0], None), (checks[0], wp)]),
            ))
    return out


def _marked_cashier(v: _Video, t: float, wp, anchor) -> np.ndarray:
    """Фрагмент рабочего места с рамкой «C» вокруг кассира — чтобы модель знала, чья сторона стола клиентская."""
    f = v.at(t).copy()
    people = [d.box for d in _get_detector()([f])[0] if d.cls == "person" and d.score >= 0.5]
    if people:
        b = min(people, key=lambda p: np.hypot(*np.subtract(_center(p), anchor)))
        x1, y1, x2, y2 = map(int, b)
        cv2.rectangle(f, (x1, y1), (x2, y2), (0, 200, 255), 3)
        cv2.putText(f, "C", (x1 + 5, y1 + 30), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 200, 255), 3)
    return _crop(f, wp)


# --- телефон, еда, напитки ---

def _candidates(scans: list[_Scan], kind: str, anchor=None) -> list[tuple[float, tuple | None, bool]]:
    """(время, бокс человека, сильный?) — где скан рабочего места или фрагмент человека указал на событие.

    Сильный кандидат — «да» от увеличенного фрагмента человека; слабый — только от общего вида рабочего места.
    """
    out = []
    for s in scans:
        cashiers = [(b, a) for b, a in s.persons if _is_cashier(b, s.persons, anchor)]
        boxes = []
        for box, a in cashiers:
            hit = a.get("phone") if kind == "phone" else (a.get("eats") or a.get("drinks"))
            if hit:
                boxes.append(box)
        w = s.workplace
        wp_hit = w.get("phone") if kind == "phone" else w.get("eat_drink")
        if boxes:
            out += [(s.t, b, True) for b in boxes]
        elif wp_hit:  # рабочее место говорит «да», но фрагменты людей — нет: проверим кассира
            out += [(s.t, b, False) for b, _ in cashiers] or ([(s.t, None, False)] if not s.persons else [])
    return out


def _episodes(cands: list[tuple[float, tuple | None]], step: float) -> list[list[tuple[float, tuple | None]]]:
    eps: list[list] = []
    for c in cands:
        if eps and c[0] - eps[-1][-1][0] <= step * 1.5:
            eps[-1].append(c)
        else:
            eps.append([c])
    return eps


def _hand_events(v: _Video, scans: list[_Scan], step: float, wp) -> list[Violation]:
    out = []
    anchor = _cashier_anchor(v, scans, wp)
    for ep in _episodes(_candidates(scans, "phone", anchor), step):
        hit = _verify(v, ep, wp, P.PHONE, lambda a: a.get("phone"), lambda a: a.get("phone"))
        if hit:
            t, box, _ = hit
            out.append(Violation(
                "phone_use", t,
                f"С {_fmt(t)} кассир держит в руках мобильный телефон на рабочем месте.",
                _evidence(v, [(t, None), (t, box or wp)]),
            ))
    for ep in _episodes(_candidates(scans, "eat", anchor), step):
        hit = _verify(v, ep, wp, P.EAT, lambda a: a.get("eats") or a.get("drinks"),
                      lambda a: a.get("eats") or a.get("drinks"))
        if hit:
            t, box, a = hit
            what = " и ".join(x for x, k in (("ест", "eats"), ("пьёт", "drinks")) if a.get(k)) or "ест или пьёт"
            out.append(Violation(
                "food_drink", t,
                f"С {_fmt(t)} кассир {what} на рабочем месте, где совершаются операции с наличными.",
                _evidence(v, [(t, None), (t, box or wp)]),
            ))
    out += _client_events(v, scans, step, wp, anchor)
    return out


def _verify(v: _Video, ep, wp, prompt: str, ok, person_ok=None):
    """Подтверждение эпизода: до 3 кандидатов (сильные первыми), контекст рабочего места + 2 кадра человека."""
    ordered = sorted(ep, key=lambda c: (not c[2], c[0]))

    def check(t: float, b) -> dict:
        return _ask(prompt, [_crop(v.at(t), wp), _crop(v.at(t), b, PERSON_SIDE), _crop(v.at(t + 1), b, PERSON_SIDE)])

    for t, box, strong in ordered[:3]:
        b = box or wp
        if not strong and person_ok is not None:
            # Слабая подсказка (только общий вид): событие могло начаться между сканами — уплотняем 3 с вперёд
            ts = [t + k * 0.75 for k in range(1, 5) if t + k * 0.75 < v.dur - 1]
            crops = [_crop(v.at(t2), b, PERSON_SIDE) for t2 in ts]
            with ThreadPoolExecutor(VLM_PARALLEL) as pool:
                answers = list(pool.map(lambda c: _ask(P.PERSON, [c]), crops))
            log.debug("densify %.1f box=%s -> %s", t, box, answers)
            hits = [(t2, a2) for t2, a2 in zip(ts, answers) if person_ok(a2)]
            if hits:  # общий вид + крупный план человека — два независимых сигнала
                return hits[0][0], box, hits[0][1]
            continue
        if strong and person_ok is not None:
            # Фрагмент человека уже сказал «да» — подтверждаем тем же вопросом на соседнем кадре
            for t2 in (t + 0.75, t - 0.75):
                if 0 <= t2 < v.dur - 1:
                    a2 = _ask(P.PERSON, [_crop(v.at(t2), b, PERSON_SIDE)])
                    log.debug("repeat %.1f box=%s -> %s", t2, box, a2)
                    if person_ok(a2):
                        return min(t, t2), box, a2
            continue
        a = check(t, b)
        log.debug("verify %.1f box=%s -> %s", t, box, a)
        if not ok(a):
            continue
        # Второе, независимое подтверждение в соседний момент: один кадр слишком часто ошибается
        for t2 in (t + 0.75, t - 0.75):  # короткие события (откусить, отпить) длятся 2–3 с
            if 0 <= t2 < v.dur - 1 and ok(check(t2, b)):
                return min(t, t2), box, a
    return None
